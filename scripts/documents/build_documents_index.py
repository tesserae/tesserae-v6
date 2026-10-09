#!/usr/bin/env python3
"""Stage 3b-1: build a SEPARATE per-language inverted index for the
documentary corpus, reusing the existing index-build code unchanged.

Reuses `scripts/build_inverted_index.py`'s own `build_index()` (same
`texts`/`postings`/`lines` schema, same `build_lemma_doc_freq()`) and
`backend/lemma_cache.py`'s own `rebuild_lemma_cache()`, by pointing their
module-level `TEXTS_DIR`/`INDEX_DIR`/`CACHE_DIR` globals at a SCRATCH
location for the duration of one language's build, then moving the
finished db into place under --index-dir as `<lang>_documents_index.db`
(never `<lang>_index.db` -- see `FORBIDDEN_DB_BASENAMES` below, enforced
in code, not just by convention). This keeps `lemma_doc_freq` scoped to
the documentary corpus alone (the reason for a separate index at all:
computing it over literature + documents together would shift every
literary lemma's rarity, see the stage 3b-1 spec's architecture note 1).

Adds one table on top of the reused schema: `doc_meta(doc_id PRIMARY KEY,
text_id, first_ref, last_ref)`, derived from the just-built `lines` table
(no separate manifest from `write_document_tess.py` is needed: a
document's own id is always the text before the first space in its
ref -- "<ID>" for a short document, "<ID LINE>" for a long one's own
line -- and a document's lines are always written contiguously within
their bucket file, so grouping consecutive same-prefix refs by
insertion order recovers first_ref/last_ref exactly).

SAFETY: before touching anything, resolves --index-dir and every path
derived from it with `os.path.realpath` and refuses if that resolves
under `/var/www` (production), or if any file this script is about to
write or open-for-write has the exact basename `la_index.db`,
`grc_index.db`, or `en_index.db` (the literary indexes). These checks
are the actual code path, not a comment -- see `_assert_safe_dir` and
`_assert_not_literary_index`.

Usage (one language per invocation, per the memory rules -- run each
through ~/bin/tess-job, one at a time):

    python3 build_documents_index.py --language la \\
        --texts-root ~/tesserae-docs/stage3/texts_documents \\
        --index-dir <worktree>/data/inverted_index \\
        --cache-root <worktree>/cache/lemmas_documents
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import sqlite3
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import build_inverted_index as bii  # noqa: E402
import backend.lemma_cache as lemma_cache_mod  # noqa: E402
from backend.text_processor import TextProcessor  # noqa: E402

FORBIDDEN_DB_BASENAMES = {"la_index.db", "grc_index.db", "en_index.db",
                          "ar_index.db", "fa_index.db", "he_index.db",
                          "cop_index.db", "ur_index.db"}


def _assert_not_literary_index(path: str):
    if os.path.basename(path) in FORBIDDEN_DB_BASENAMES:
        raise RuntimeError(
            f"refusing to write/open the literary index file {path!r}; "
            "this script only ever writes <lang>_documents_index.db")


def _assert_safe_dir(path: str, label: str):
    real = os.path.realpath(path)
    if real.startswith("/var/www"):
        raise RuntimeError(
            f"refusing to use {label}={path!r} (resolves to {real!r} under "
            "/var/www): never touch production")


def build_doc_meta(db_path: str) -> int:
    """Populate doc_meta from the already-built lines table. Returns the
    number of documents recorded."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS doc_meta ("
        "doc_id TEXT PRIMARY KEY, text_id INTEGER, "
        "first_ref TEXT, last_ref TEXT)"
    )
    cur = conn.cursor()
    cur.execute("SELECT text_id FROM texts")
    text_ids = [row[0] for row in cur.fetchall()]
    n = 0
    for text_id in text_ids:
        refs = [r[0] for r in conn.execute(
            "SELECT ref FROM lines WHERE text_id = ? ORDER BY rowid", (text_id,)
        ).fetchall()]
        cur_doc = None
        first_ref = None
        last_ref = None
        for ref in refs:
            doc_id = ref.split(" ", 1)[0]
            if doc_id != cur_doc:
                if cur_doc is not None:
                    conn.execute(
                        "INSERT OR REPLACE INTO doc_meta (doc_id, text_id, first_ref, last_ref) "
                        "VALUES (?, ?, ?, ?)", (cur_doc, text_id, first_ref, last_ref))
                    n += 1
                cur_doc = doc_id
                first_ref = ref
            last_ref = ref
        if cur_doc is not None:
            conn.execute(
                "INSERT OR REPLACE INTO doc_meta (doc_id, text_id, first_ref, last_ref) "
                "VALUES (?, ?, ?, ?)", (cur_doc, text_id, first_ref, last_ref))
            n += 1
    conn.commit()
    conn.close()
    return n


def build_one_language(language: str, texts_root: str, index_dir: str,
                        cache_root: str, scratch_root: str,
                        fast_greek: bool = True, resume: bool = False,
                        verbose: bool = True, skip_cache: bool = False) -> dict:
    _assert_safe_dir(index_dir, "--index-dir")
    _assert_safe_dir(scratch_root, "--scratch-root")
    _assert_safe_dir(cache_root, "--cache-root")

    final_db = os.path.join(index_dir, f"{language}_documents_index.db")
    _assert_not_literary_index(final_db)

    scratch_dir = os.path.join(scratch_root, f"_scratch_{language}")
    os.makedirs(scratch_dir, exist_ok=True)
    # build_index() (reused unmodified) always names its output
    # '<language>_index.db', e.g. 'la_index.db' -- the SAME basename the
    # literary index uses. That is fine and expected here, because
    # `_assert_safe_dir` above already confirmed scratch_dir is not under
    # /var/www and scratch_root's own default (data/_documents_index_scratch)
    # never coincides with data/inverted_index; the basename guard is only
    # meaningful for the FINAL path (checked below), where it would catch a
    # future edit that accidentally dropped the '_documents' suffix.
    scratch_db = os.path.join(scratch_dir, f"{language}_index.db")
    if not resume and os.path.exists(scratch_db):
        os.remove(scratch_db)

    lang_dir = os.path.join(texts_root, language)
    if not os.path.isdir(lang_dir):
        raise RuntimeError(f"no {lang_dir!r}: run write_document_tess.py first")

    text_processor = TextProcessor()

    # Monkeypatch the reused module's own globals for the duration of this
    # call. Both modules compute these from `__file__` at import time
    # (repo-root-relative), so this is the intended override point, not a
    # hack around missing parameters.
    orig_bii = (bii.TEXTS_DIR, bii.INDEX_DIR)
    bii.TEXTS_DIR = texts_root
    bii.INDEX_DIR = scratch_dir
    try:
        fast_mode = fast_greek if language == "grc" else False
        t0 = time.time()
        bii.build_index(language, text_processor, verbose=verbose,
                         resume=resume, force=not resume,
                         use_syntax_db=False, fast_mode=fast_mode)
        build_elapsed = time.time() - t0
    finally:
        bii.TEXTS_DIR, bii.INDEX_DIR = orig_bii

    if not os.path.exists(scratch_db):
        raise RuntimeError(f"build_index did not produce {scratch_db!r}")

    os.makedirs(index_dir, exist_ok=True)
    if os.path.exists(final_db):
        os.remove(final_db)
    shutil.move(scratch_db, final_db)

    t0 = time.time()
    n_docs = build_doc_meta(final_db)
    doc_meta_elapsed = time.time() - t0

    if skip_cache:
        cache_result = {"skipped": True, "reason": "built separately (sharded)"}
        cache_elapsed = 0.0
    else:
        orig_cache = (lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR)
        lemma_cache_mod.TEXTS_DIR = texts_root
        lemma_cache_mod.CACHE_DIR = cache_root
        try:
            t0 = time.time()
            # fast_mode (computed above) is the SAME flag the index build
            # just used, so when it was applied for Greek, the cache uses
            # the identical table-only lookup and the two agree on every
            # lemma (the fix this follow-up round asked for).
            cache_result = lemma_cache_mod.rebuild_lemma_cache(
                language, text_processor,
                fast_greek=bool(fast_mode) if language == "grc" else False,
                build_phrase_units=False)
            cache_elapsed = time.time() - t0
        finally:
            lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR = orig_cache

    conn = sqlite3.connect(final_db)
    n_texts = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
    n_lines = conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0]
    n_postings = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    n_lemmas = conn.execute("SELECT COUNT(DISTINCT lemma) FROM postings").fetchone()[0]
    conn.close()

    peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "language": language,
        "final_db": final_db,
        "db_size_mb": round(os.path.getsize(final_db) / (1024 * 1024), 1),
        "fast_mode_greek": fast_mode if language == "grc" else None,
        "texts": n_texts,
        "lines": n_lines,
        "postings": n_postings,
        "unique_lemmas": n_lemmas,
        "doc_meta_rows": n_docs,
        "build_index_elapsed_s": round(build_elapsed, 1),
        "doc_meta_elapsed_s": round(doc_meta_elapsed, 1),
        "lemma_cache_elapsed_s": round(cache_elapsed, 1),
        "lemma_cache_result": cache_result,
        "self_reported_peak_rss_mb": round(peak_rss_kb / 1024, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", required=True, choices=["la", "grc"])
    ap.add_argument("--texts-root", default=os.path.expanduser(
        "~/tesserae-docs/stage3/texts_documents"))
    ap.add_argument("--index-dir", default=os.path.join(REPO_ROOT, "data", "inverted_index"))
    ap.add_argument("--cache-root", default=os.path.join(REPO_ROOT, "cache", "lemmas_documents"))
    ap.add_argument("--scratch-root", default=os.path.join(REPO_ROOT, "data", "_documents_index_scratch"))
    ap.add_argument("--no-fast-greek", action="store_true",
                     help="use CLTK for Greek too instead of the table-only fast mode")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--skip-cache", action="store_true",
                     help="skip the lemma-cache rebuild here (e.g. because it is "
                          "being built separately, sharded, by build_lemma_cache_shard.py)")
    ap.add_argument("--summary-out", default=None)
    args = ap.parse_args(argv)

    result = build_one_language(
        args.language, args.texts_root, args.index_dir, args.cache_root,
        args.scratch_root, fast_greek=not args.no_fast_greek,
        resume=args.resume, verbose=not args.quiet, skip_cache=args.skip_cache,
    )
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as f:
            f.write(out)
    print(out, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
