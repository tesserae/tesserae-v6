#!/usr/bin/env python3
"""Shared safety helpers for scripts under scripts/corpus/ and
scripts/translations/ that write to a .tess file, an index, a cache, or
anything else under data/.

docs/DATA_OPERATIONS.md states the house rule for exactly these scripts:
"each [script] with a dry run by default, a dated backup beside the file it
replaces, and a copy-and-rename swap so the live app never reads a
half-written file." This module is the one place that rule is implemented,
so a script gets it by importing three functions instead of hand-rolling
them (and, per the code audit of 2026-09-21, hand-rolling them is exactly
where scripts have skipped a step).

    add_apply_argument(parser)   -- adds --apply; a dry run is the default
    backup(path, tag=...)        -- copies path to a stamped, collision-safe
                                     <path>.bak-<tag>-<timestamp> beside it
    atomic_write(path, data)     -- writes beside path and renames over it,
                                     with NO line-ending or encoding
                                     translation in either direction

Survey, 2026-09-21 (scripts under scripts/corpus/ and scripts/translations/
that write to a .tess file, an index/cache file, or anything under data/;
scripts that only write to an external personal workspace such as
~/perseus_trans/ are out of scope for this table -- that is finding #11 of
the same audit, a separate problem). Columns: dry run by default / dated
backup / atomic (write-beside-and-rename) swap / prints what it will change
before doing it.

  scripts/corpus/
    add_texts_to_index.py            n/a*  n/a*  n/a*  yes   *always writes
        directly to the --db it is given, but its own docstring requires
        that --db be a COPY of the live index, with the swap into place
        (cp / mv / mv) done by the operator afterwards, outside the script
        -- the convention is met one level up, not inside this script.
    apply_lucretius_lucan_editions.py  yes   yes   yes   yes  already correct
    apply_paradise_lost_numbering.py   yes   yes   yes   yes  already correct
    apply_passage_rows.py              n/a*  yes   yes   yes  *no dry run:
        every call embeds and either appends or replaces; count asserts
        before/after stand in for a preview. Worth a --apply flag in a
        follow-up, not attempted here (touches embeddings.npy directly).
    apply_prelude_books.py             yes   yes   yes   yes  already correct
    apply_whole_vs_parts_refs.py       yes   yes   yes   yes  already correct
        (the model this module is built to match)
    batch2_to_tess.py                  no    no    no    yes  writes fresh
        per-work .tess files to --out from HTML; NOT converted here, see
        the PR body for why
    batch3_to_tess.py                  no    no    no    yes  same as batch2
    build_batch_windows.py             no    no    no    yes  writes a JSON
        + optional window_texts.db upsert (own docstring: "Always back up
        window_texts.db first" -- manual, not automatic); NOT converted
    check_whole_vs_parts.py            --    --    --    --   read-only,
        no writes; out of scope
    describe_windows.py                --    --    --    --   calls an HTTP
        endpoint and appends to a sidecar JSONL as records finish (that is
        its OWN crash-safety design, not a full rewrite); out of scope
    drop_stale_index_entries.py        yes   yes   yes   yes  already correct
    fix_hebrew_clitic_spacing.py       NO    NO    NO    partial  CONVERTED
        in this PR (finding #2's named example)
    latinlibrary_to_tess.py            no    no    no    yes  writes fresh
        per-work .tess files to --out from scraped HTML; NOT converted here
    rebuild_bigrams.py                 n/a*  yes   yes   yes  *no --apply
        flag, but it is invoked as one step of a larger pipeline script,
        not interactively; backup + atomic swap already present
    rebuild_docfreq.py                 yes   yes   yes   yes  already correct
        (the OTHER model this module is built to match)
    rekey_verity_paradise_lost.py      --    --    --    --   reads its
        source read-only and writes ONLY a separate output path, never the
        file it read; the safe pattern by construction, nothing to add
    renumber_paradise_lost.py          BACKWARDS  no  no  yes  writes are
        the DEFAULT and --dry-run must be passed to avoid them, opposite of
        the convention; NOT converted here, see the PR body for why
    repair_lactantius_placidus.py      no*   no    no    yes  *has a
        --report-only flag, but writing is the default; CONVERTED in this
        PR
    repair_part_file_defects_2026-09-21.py  yes  no(**)  yes  yes  dry run
        and atomic swap already present; (**) no backup call today -- one
        of the two scripts this module is built to be adoptable by later
    repair_ref_tags.py                 yes   yes   yes   yes  already correct
    validate_tess.py                   --    --    --    --   read-only
        validator, no writes; out of scope
    wikisource_africa_to_tess.py       no    no    no    yes  writes one
        fresh .tess file from wikitext to --out; NOT converted here

  scripts/translations/ (47 files; all but the five below write only to an
  external personal workspace, ~/perseus_trans/, never to anything under
  this repository's data/ -- out of scope for the corpus-data convention,
  though it is its own risk, audit finding #11)
    compact_for_serving.py             no    no    no    yes  rewrites every
        *.json file in its target directory in place; that directory is
        normally a scratch build directory (its own $TESSERAE_TRANS_OUT
        default), not production data/translations/, but nothing stops it
        being pointed at the live directory; NOT converted here, flagged
        for owner attention since it is the least contained of this group
    match_works_by_title.py, proper_names.py, tei_extract.py,
    tei_extract_base.py, verify_work_identity.py    --  --  --  --  write
        only under ~/perseus_trans/ (or an explicit $TESSERAE_* override),
        never under this repo's data/; out of scope
    realign_silvae.py                  --    --    --    --   reads --json
        read-only, writes ONLY --out (a separate path, e.g. /tmp/...); safe
        by construction, matching rekey_verity_paradise_lost.py's pattern
    remap_sblgnt.py                    no    no    no    yes  writes brand
        new per-book files under data/translations/ (a work name the
        legacy pipeline never used, so nothing existing is at risk today);
        NOT converted here, see the PR body for why
    repair_book_openings.py            --    --    --    --   same safe
        read-only-in/--out-only pattern as realign_silvae.py
    repair_gap_pages.py                --    --    --    --   same

This module has no test-suite dependency on the corpus; see
tests/test_corpus_safety.py for its own tests, which use only a temp
directory.
"""
import argparse
import os
import shutil
import time


def add_apply_argument(parser, help_text=None):
    """Add ``--apply`` to an argparse parser. Its absence is a dry run
    (the convention's default); passing it authorizes writing.
    """
    parser.add_argument(
        '--apply', action='store_true',
        help=help_text or 'write changes (default: dry run, report only)')
    return parser


def make_parser(description=None):
    """An ArgumentParser pre-wired with --apply, for a script whose only
    other arguments are its own. Using this (or add_apply_argument on your
    own parser) is required by the convention in docs/DATA_OPERATIONS.md.
    """
    ap = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    add_apply_argument(ap)
    return ap


def backup(path, tag=None):
    """Copy ``path`` to a dated backup beside it and return the backup's
    path, or None if ``path`` does not exist (nothing to back up).

    The name is ``<path>.bak-<tag>-<YYYYmmdd-HHMMSS>`` (or, with no tag,
    ``<path>.bak-<YYYYmmdd-HHMMSS>``). Stamped to the second, per the
    convention -- but a rerun inside the same second must never overwrite
    an earlier backup, so a numeric suffix (``-1``, ``-2``, ...) is added
    until the name is free.
    """
    if not os.path.exists(path):
        return None
    stamp = time.strftime('%Y%m%d-%H%M%S')
    suffix = f'{tag}-{stamp}' if tag else stamp
    dest = f'{path}.bak-{suffix}'
    n = 1
    while os.path.exists(dest):
        dest = f'{path}.bak-{suffix}-{n}'
        n += 1
    shutil.copy2(path, dest)
    return dest


def read_text_preserving_eol(path, encoding='utf-8'):
    """Read ``path`` as a single string with its line endings intact.

    Python's default text mode ("universal newlines") silently rewrites
    every ``\\r\\n`` to ``\\n`` on read, and a naive write then emits ``\\n``
    for all of it -- a corpus file with Windows line endings loses them the
    moment a script touches it. ``newline=''`` disables that translation.
    """
    with open(path, encoding=encoding, newline='') as fh:
        return fh.read()


def read_lines_preserving_eol(path, encoding='utf-8'):
    """Read ``path`` as a list of lines, each keeping its own original line
    ending exactly as it is on disk (see read_text_preserving_eol)."""
    with open(path, encoding=encoding, newline='') as fh:
        return fh.readlines()


def atomic_write(path, data, encoding='utf-8'):
    """Write ``data`` beside ``path`` and rename over it.

    ``data`` is a string, or an iterable of strings (e.g. a list of lines --
    each must already carry whatever line ending it needs; this function
    never adds, strips, or translates one). Written with ``newline=''``, so
    a string that already contains ``\\r\\n`` is written as ``\\r\\n``, not
    translated to the platform default.

    The write happens on a temp file in the same directory as ``path`` (so
    the final ``os.replace`` is a same-filesystem rename, atomic on POSIX),
    and that temp file is removed if the write raises. ``path`` itself is
    only ever replaced by ``os.replace``, once the new content is fully and
    successfully written -- a failure midway leaves the original untouched.
    """
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    tmp = os.path.join(directory, f'.{os.path.basename(path)}.tmp-{os.getpid()}-{time.time_ns()}')
    try:
        with open(tmp, 'w', encoding=encoding, newline='') as fh:
            if isinstance(data, str):
                fh.write(data)
            else:
                fh.writelines(data)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    os.replace(tmp, path)
