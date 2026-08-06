#!/usr/bin/env python3
"""Build syntax_coptic.db from upstream Coptic Scriptorium CoNLL-U files.

Unlike Latin/Greek (which run Stanza), Coptic data already ships with
hand-curated UD parses (heads, deprels) in the CoNLL-U files at
/tmp/coptic_scriptorium/. The Sahidic NT specifically needs the
TT-derived CoNLL-U at /tmp/sahidica_nt_conllu — see scripts/tt_to_conllu.py.

This script walks every relevant upstream CoNLL-U source, parses out
the syntax annotations sentence-by-sentence using the same ref/text-name
scheme the .tess converter uses, and writes them into a syntax DB whose
schema matches syntax_greek.db / syntax_latin.db.

Usage:
    python scripts/build_coptic_syntax_db.py [--limit N] [--corpus NAME]
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.convert_coptic_scriptorium import parse_conllu, normalize_coptic
from scripts.convert_coptic_scriptorium_full import (
    SCRIPTORIUM_DIR, SKIP_DIR_PREFIXES, SKIP_DIR_EXACT,
    NT_SKIP_BOOK_KEYS, OT_SKIP_BOOK_KEYS,
    normalize_book_key,
)

# Override Sahidica NT source to use our TT-derived CoNLL-U.
SAHIDICA_NT_OVERRIDE = '/tmp/sahidica_nt_conllu'

DB_PATH = os.path.join(PROJECT_ROOT, "data", "inverted_index", "syntax_coptic.db")


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS syntax_source (
            parser TEXT DEFAULT 'coptic_scriptorium',
            model TEXT DEFAULT 'ud',
            build_date TEXT,
            total_texts INTEGER DEFAULT 0,
            total_lines INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS texts (
            text_id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS syntax (
            text_id INTEGER NOT NULL,
            ref TEXT NOT NULL,
            tokens TEXT,
            lemmas TEXT,
            upos TEXT,
            heads TEXT,
            deprels TEXT,
            feats TEXT,
            PRIMARY KEY (text_id, ref),
            FOREIGN KEY (text_id) REFERENCES texts(text_id)
        )
    """)
    conn.commit()
    return conn


def find_conllu_source_for_corpus(corpus_dir):
    """Locate (or extract) the CoNLL-U directory for a corpus."""
    p = Path(corpus_dir)
    sub = [s for s in p.glob('*_CONLLU') if s.is_dir()]
    if sub:
        return sub[0]
    extracted = list(p.glob('*_CONLLU_extracted'))
    if extracted:
        return extracted[0]
    zips = list(p.glob('*_CONLLU.zip'))
    if zips:
        target = p / (zips[0].stem + '_extracted')
        if not target.exists():
            with zipfile.ZipFile(zips[0]) as zf:
                zf.extractall(target)
        return target
    return None


def discover_corpora():
    """Yield (corpus_name, role, conllu_dir, prefix) tuples covering Sahidic + Bohairic.

    role in {'nt-split', 'ot-split', 'chapter', 'flat'}.
    """
    root = Path(SCRIPTORIUM_DIR)
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        if name in SKIP_DIR_EXACT:
            continue
        if name == '.git':
            continue
        # Skip the placeholder 'bible/' but keep bohairic.* corpora.
        if name == 'bible' or name.startswith('bible.'):
            continue

        if name == 'sahidica.nt':
            # Use TT-derived CoNLL-U for the full NT.
            if os.path.isdir(SAHIDICA_NT_OVERRIDE):
                yield (name, 'nt-split', SAHIDICA_NT_OVERRIDE, 'sahidica', NT_SKIP_BOOK_KEYS)
            continue
        if name == 'bohairic.nt':
            conllu = find_conllu_source_for_corpus(str(d))
            if conllu:
                yield (name, 'nt-split', conllu, 'bohairic', set())
            continue
        if name == 'sahidic.ot':
            conllu = find_conllu_source_for_corpus(str(d))
            if conllu:
                yield (name, 'ot-split', conllu, 'sahidic', OT_SKIP_BOOK_KEYS)
            continue
        if name == 'bohairic.ot':
            conllu = find_conllu_source_for_corpus(str(d))
            if conllu:
                yield (name, 'ot-split', conllu, 'bohairic', set())
            continue
        if name in ('sahidica.mark', 'sahidica.1corinthians', 'sahidic.jonah', 'sahidic.ruth'):
            conllu = find_conllu_source_for_corpus(str(d))
            if conllu:
                yield (name, 'chapter', conllu, name, None)
            continue
        if name == 'bohairic.mark' or name == 'bohairic.1corinthians':
            # We do not currently emit dedicated .tess for these (Bohairic
            # standalone richer-annotated chapters); skip to avoid a
            # syntax DB entry without a corresponding .tess.
            continue
        if any(name.startswith(p) for p in ('bohairic-',)):
            # Bohairic single-corpus directories (bohairic-habakkuk etc.).
            # Skip — no .tess equivalents exist yet.
            continue

        # Default: flat corpus
        conllu = find_conllu_source_for_corpus(str(d))
        if conllu:
            yield (name, 'flat', conllu, name, None)


def syntax_record_from_sentence(sent):
    """Build (tokens, lemmas, upos, heads, deprels, feats) lists from a parsed sentence.

    Mirrors emit_lines_for_sentences token filtering: drops PUNCT, normalizes Coptic.
    """
    tokens, lemmas, upos, heads, deprels = [], [], [], [], []
    for form, lemma, pos, head, deprel in sent.get('syntax', []):
        if pos == 'PUNCT':
            continue
        norm_form = normalize_coptic(form)
        norm_lemma = normalize_coptic(lemma) if lemma != '_' else norm_form
        if not norm_form:
            continue
        tokens.append(norm_form)
        lemmas.append(norm_lemma)
        upos.append(pos or 'X')
        try:
            heads.append(int(head))
        except (TypeError, ValueError):
            heads.append(0)
        deprels.append(deprel or 'dep')
    return tokens, lemmas, upos, heads, deprels


def insert_text_rows(conn, filename, ref_to_syntax):
    """Insert one text + all its syntax rows. Skips empty refs."""
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO texts (filename) VALUES (?)", (filename,))
    cur.execute("SELECT text_id FROM texts WHERE filename = ?", (filename,))
    text_id = cur.fetchone()[0]

    rows = []
    for ref, (tokens, lemmas, upos, heads, deprels) in ref_to_syntax.items():
        if not tokens:
            continue
        rows.append((
            text_id, ref,
            json.dumps(tokens, ensure_ascii=False),
            json.dumps(lemmas, ensure_ascii=False),
            json.dumps(upos, ensure_ascii=False),
            json.dumps(heads),
            json.dumps(deprels, ensure_ascii=False),
            json.dumps([""] * len(tokens), ensure_ascii=False),
        ))
    if rows:
        cur.executemany(
            "INSERT OR REPLACE INTO syntax (text_id, ref, tokens, lemmas, upos, heads, deprels, feats) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    conn.commit()
    return len(rows)


def collect_split_book_syntax(conllu_dir, prefix, skip_books):
    """For an NT/OT-split corpus: yield (filename, {ref: syntax}) per book."""
    files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not files:
        return

    books = {}
    for f in files:
        m = re.match(r'^\d+_(.+)_(\d+)\.conllu$', f.name)
        if not m:
            m = re.match(r'^(.+)_(\d+)\.conllu$', f.name)
        if not m:
            m_odd = re.match(r'^\d+_(.+)_0?[A-Za-z][A-Za-z0-9]*\.conllu$', f.name)
            if m_odd:
                books.setdefault(m_odd.group(1), []).append((0, f, f.name))
            continue
        books.setdefault(m.group(1), []).append((int(m.group(2)), f, f.name))

    for book_name, chapter_files in sorted(books.items()):
        if normalize_book_key(book_name) in skip_books:
            continue
        output_name = f'{prefix}.{book_name.lower()}'
        ref_prefix = output_name
        chapter_files.sort(key=lambda x: (x[0], x[2]))

        ref_to_syntax = {}
        for ch_num, fpath, _ in chapter_files:
            sentences = parse_conllu(str(fpath))
            for sent_idx, sent in enumerate(sentences, 1):
                rec = syntax_record_from_sentence(sent)
                if not rec[0]:
                    continue
                ref = f'{ref_prefix}.{ch_num}.{sent_idx}'
                ref_to_syntax[ref] = rec
        yield output_name, ref_to_syntax


def collect_chapter_corpus_syntax(conllu_dir, output_name):
    files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not files:
        return None
    ref_to_syntax = {}
    for f in files:
        m = re.search(r'_(\d+)(?=\.conllu)', f.name)
        ch_num = int(m.group(1)) if m else 0
        sentences = parse_conllu(str(f))
        for sent_idx, sent in enumerate(sentences, 1):
            rec = syntax_record_from_sentence(sent)
            if not rec[0]:
                continue
            ref = f'{output_name}.{ch_num}.{sent_idx}'
            ref_to_syntax[ref] = rec
    return ref_to_syntax


def collect_flat_corpus_syntax(conllu_dir):
    files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not files:
        return None, None
    # Output name = CONLLU prefix (Path.name with _CONLLU stripped)
    output_name = Path(conllu_dir).name.replace('_CONLLU_extracted', '').replace('_CONLLU', '')
    ref_prefix = output_name
    counter = 0
    ref_to_syntax = {}
    for f in files:
        sentences = parse_conllu(str(f))
        for sent in sentences:
            rec = syntax_record_from_sentence(sent)
            if not rec[0]:
                continue
            counter += 1
            ref = f'{ref_prefix}.{counter}'
            ref_to_syntax[ref] = rec
    return output_name, ref_to_syntax


def main():
    ap = argparse.ArgumentParser(description="Build syntax_coptic.db from CoNLL-U files")
    ap.add_argument("--corpus", help="Only process the named corpus (e.g. sahidica.nt)")
    ap.add_argument("--limit", type=int, default=0, help="Max corpora to process")
    ap.add_argument("--rebuild", action="store_true", help="Delete and rebuild the DB")
    args = ap.parse_args()

    if args.rebuild and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = init_db(DB_PATH)
    print(f"DB: {DB_PATH}")

    total_texts = 0
    total_lines = 0

    corpora = list(discover_corpora())
    if args.corpus:
        corpora = [c for c in corpora if c[0] == args.corpus]
    if args.limit:
        corpora = corpora[:args.limit]

    print(f"Processing {len(corpora)} corpora\n")

    for corpus_name, role, conllu_dir, prefix, skip_books in corpora:
        print(f"  {corpus_name} [{role}] -> {conllu_dir}")

        if role in ('nt-split', 'ot-split'):
            for output_name, ref_to_syntax in collect_split_book_syntax(
                conllu_dir, prefix, skip_books or set()
            ):
                tess_path = os.path.join(PROJECT_ROOT, 'texts', 'cop', output_name + '.tess')
                if not os.path.exists(tess_path):
                    print(f"    skip {output_name}: no .tess present")
                    continue
                n = insert_text_rows(conn, output_name + '.tess', ref_to_syntax)
                if n:
                    total_texts += 1
                    total_lines += n
                    print(f"    {output_name}: {n} lines")

        elif role == 'chapter':
            ref_to_syntax = collect_chapter_corpus_syntax(conllu_dir, prefix)
            if ref_to_syntax:
                tess_path = os.path.join(PROJECT_ROOT, 'texts', 'cop', prefix + '.tess')
                if os.path.exists(tess_path):
                    n = insert_text_rows(conn, prefix + '.tess', ref_to_syntax)
                    if n:
                        total_texts += 1
                        total_lines += n
                        print(f"    {prefix}: {n} lines")

        elif role == 'flat':
            output_name, ref_to_syntax = collect_flat_corpus_syntax(conllu_dir)
            if output_name and ref_to_syntax:
                tess_path = os.path.join(PROJECT_ROOT, 'texts', 'cop', output_name + '.tess')
                if os.path.exists(tess_path):
                    n = insert_text_rows(conn, output_name + '.tess', ref_to_syntax)
                    if n:
                        total_texts += 1
                        total_lines += n
                        print(f"    {output_name}: {n} lines")
                else:
                    print(f"    skip {output_name}: no .tess present")

    cur = conn.cursor()
    cur.execute("DELETE FROM syntax_source")
    cur.execute(
        "INSERT INTO syntax_source (parser, model, build_date, total_texts, total_lines) "
        "VALUES ('coptic_scriptorium', 'ud', datetime('now'), ?, ?)",
        (total_texts, total_lines),
    )
    conn.commit()
    conn.close()

    print(f"\nDone. {total_texts} texts, {total_lines:,} lines -> {DB_PATH}")


if __name__ == "__main__":
    main()
