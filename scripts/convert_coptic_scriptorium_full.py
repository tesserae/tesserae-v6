#!/usr/bin/env python3
"""
Full Sahidic ingest from Coptic SCRIPTORIUM v6.2.0.

Discovers every non-Bohairic, non-treebank corpus directory under
SCRIPTORIUM_DIR (default /tmp/coptic_scriptorium) and emits one or more
.tess files into texts/cop/, plus per-file lemma caches and an updated
global lemma table.

Special handling:
  - sahidica.nt  -> one .tess per NT book; Mark and 1 Corinthians are
                    skipped because we keep the richer-annotated standalone
                    sahidica.mark / sahidica.1corinthians.
  - sahidic.ot   -> one .tess per OT book; Jonah and Ruth skipped because
                    we use the dedicated sahidic.jonah / sahidic.ruth.
  - all others   -> one .tess per corpus (sequential sentence numbering).

Reuses parse_conllu / normalize_coptic from convert_coptic_scriptorium.py.
"""

import json
import os
import re
import sys
import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.convert_coptic_scriptorium import parse_conllu, normalize_coptic

SCRIPTORIUM_DIR = '/tmp/coptic_scriptorium'
TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'cop')
LEMMA_DIR = os.path.join(PROJECT_ROOT, 'data', 'lemma_tables')
CACHE_DIR = os.path.join(PROJECT_ROOT, 'cache', 'lemmas', 'cop')

SKIP_DIR_PREFIXES = ('bohairic', 'bible')  # bible/ is a placeholder dir
SKIP_DIR_EXACT = {'bohairic-treebank', 'coptic-treebank'}

# NT books we already have richer-annotated standalones for
NT_SKIP_BOOK_KEYS = {'mark', '1corinthians', '1_corinthians'}
# OT books we already have richer-annotated standalones for
OT_SKIP_BOOK_KEYS = {'jonah', 'ruth'}


def find_conllu_source(corpus_dir):
    """Return path to a directory containing .conllu files, extracting a zip if needed."""
    p = Path(corpus_dir)
    sub = list(p.glob('*_CONLLU'))
    sub = [s for s in sub if s.is_dir()]
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


def normalize_book_key(book_name):
    """Lowercase and strip parts to match skip lists."""
    return book_name.lower().replace('_', '')


def book_filename(prefix, book_name):
    """Produce a safe lowercase .tess basename for a book."""
    return f'{prefix}.{book_name.lower()}'


def emit_lines_for_sentences(sentences, ref_func):
    """Convert parsed sentences to (lines, lemma_pairs, cache_dict).

    ref_func(sent_idx, sent_id) -> (display_ref_str, cache_key)
    """
    lines = []
    lemma_pairs = []
    cache = {}
    for sent_idx, sent in enumerate(sentences, 1):
        display_text = sent['text']
        if not display_text:
            display_text = ' '.join(w[0] for w in sent['words'] if w[2] != 'PUNCT')
        display_text = re.sub(r'[\[\]]', '', display_text)
        display_text = re.sub(r'\s+', ' ', display_text).strip().rstrip(' .')
        if not display_text:
            continue

        display_ref, cache_key = ref_func(sent_idx, sent.get('sent_id', ''))
        lines.append(f'<{display_ref}>\t{display_text}')

        tokens = []
        lemmas = []
        for form, lemma, upos, feats, misc in sent['words']:
            if upos == 'PUNCT':
                continue
            norm_form = normalize_coptic(form)
            norm_lemma = normalize_coptic(lemma) if lemma != '_' else norm_form
            if norm_form:
                tokens.append(norm_form)
                lemmas.append(norm_lemma)
                lemma_pairs.append((norm_form, norm_lemma))

        cache[cache_key] = {'tokens': tokens, 'lemmas': lemmas}

    return lines, lemma_pairs, cache


def write_outputs(output_name, ref_prefix, lines, cache):
    """Write .tess + lemma cache files."""
    if not lines:
        return 0
    tess_path = os.path.join(TEXTS_DIR, f'{output_name}.tess')
    with open(tess_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    cache_path = os.path.join(CACHE_DIR, f'{output_name}.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

    return len(lines)


def convert_chapter_corpus(conllu_dir, output_name, ref_prefix):
    """Single corpus split by chapter (used for sahidica.mark, sahidica.1corinthians).

    File naming: BookName_ChNN.conllu OR NN_BookName_ChNN.conllu
    Refs: <ref_prefix.CH.SENT>
    """
    files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not files:
        return 0, []

    all_lines = []
    all_pairs = []
    all_cache = {}

    for f in files:
        m = re.search(r'_(\d+)(?=\.conllu)', f.name)
        ch_num = int(m.group(1)) if m else 0
        sentences = parse_conllu(str(f))

        def ref_func(sent_idx, _sid, ch=ch_num, prefix=ref_prefix):
            ref = f'{prefix}.{ch}.{sent_idx}'
            return ref, ref

        lines, pairs, cache = emit_lines_for_sentences(sentences, ref_func)
        all_lines.extend(lines)
        all_pairs.extend(pairs)
        all_cache.update(cache)

    written = write_outputs(output_name, ref_prefix, all_lines, all_cache)
    if written:
        print(f"    -> {output_name}.tess: {written} lines")
    return written, all_pairs


def convert_flat_corpus(conllu_dir, output_name, ref_prefix):
    """Whole-corpus single-stream sentence numbering (hagiographies, pseudo-, etc.).

    Refs: <ref_prefix.SENT>
    """
    files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not files:
        return 0, []

    all_lines = []
    all_pairs = []
    all_cache = {}
    counter = [0]

    def ref_func(_sent_idx, _sid, prefix=ref_prefix):
        counter[0] += 1
        ref = f'{prefix}.{counter[0]}'
        return ref, ref

    for f in files:
        sentences = parse_conllu(str(f))
        lines, pairs, cache = emit_lines_for_sentences(sentences, ref_func)
        all_lines.extend(lines)
        all_pairs.extend(pairs)
        all_cache.update(cache)

    written = write_outputs(output_name, ref_prefix, all_lines, all_cache)
    if written:
        print(f"    -> {output_name}.tess: {written} lines")
    return written, all_pairs


def split_by_book(conllu_dir, prefix, skip_books):
    """Split a multi-book corpus (NT, OT) by book, one .tess per book.

    File naming convention: NN_BookName_ChNN.conllu (NN = book number with optional zero pad).
    Output: {prefix}.{book_lower}.tess  (slashes/spaces replaced with _)
    Each book gets chapter.sentence refs.

    skip_books: set of normalized book keys to skip.

    Returns list of (output_name, lines_written, lemma_pairs).
    """
    files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not files:
        return []

    books = {}  # book_name -> [(chapter, file_path)]
    for f in files:
        # Try NN_BookName_ChNN  or BookName_ChNN
        m = re.match(r'^\d+_(.+)_(\d+)\.conllu$', f.name)
        if not m:
            m = re.match(r'^(.+)_(\d+)\.conllu$', f.name)
        if not m:
            # Oddballs like 23_Isaiah_0Subscriptio.conllu
            m_odd = re.match(r'^\d+_(.+)_0?[A-Za-z][A-Za-z0-9]*\.conllu$', f.name)
            if m_odd:
                book_name = m_odd.group(1)
                ch_num = 0
                books.setdefault(book_name, []).append((ch_num, f, f.name))
            continue
        book_name = m.group(1)
        ch_num = int(m.group(2))
        books.setdefault(book_name, []).append((ch_num, f, f.name))

    results = []
    for book_name, chapter_files in sorted(books.items()):
        if normalize_book_key(book_name) in skip_books:
            print(f"    -> skipping {book_name} (richer standalone exists)")
            continue

        book_lower = book_name.lower()
        # Sanitize: e.g. "Acts_of_the_Apostles" stays as is; "I_Samuel" stays as is
        output_name = f'{prefix}.{book_lower}'
        ref_prefix = output_name

        chapter_files.sort(key=lambda x: (x[0], x[2]))

        all_lines = []
        all_pairs = []
        all_cache = {}

        for ch_num, fpath, fname in chapter_files:
            sentences = parse_conllu(str(fpath))

            def ref_func(sent_idx, _sid, ch=ch_num, prefix_=ref_prefix):
                ref = f'{prefix_}.{ch}.{sent_idx}'
                return ref, ref

            lines, pairs, cache = emit_lines_for_sentences(sentences, ref_func)
            all_lines.extend(lines)
            all_pairs.extend(pairs)
            all_cache.update(cache)

        written = write_outputs(output_name, ref_prefix, all_lines, all_cache)
        if written:
            print(f"    -> {output_name}.tess: {written} lines ({len(chapter_files)} chapters)")
            results.append((output_name, written, all_pairs))

    return results


def discover_corpora():
    """Yield (corpus_dir_name, role) for every eligible upstream corpus.

    role is one of: 'nt-split', 'ot-split', 'flat', 'chapter'.
    """
    root = Path(SCRIPTORIUM_DIR)
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        if name in SKIP_DIR_EXACT:
            continue
        if any(name.startswith(p) for p in SKIP_DIR_PREFIXES):
            continue
        if name == 'sahidica.nt':
            yield (name, 'nt-split')
        elif name == 'sahidic.ot':
            yield (name, 'ot-split')
        elif name in ('sahidica.mark', 'sahidica.1corinthians', 'sahidic.jonah', 'sahidic.ruth'):
            yield (name, 'chapter')
        else:
            yield (name, 'flat')


def main():
    os.makedirs(TEXTS_DIR, exist_ok=True)
    os.makedirs(LEMMA_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    all_lemma_pairs = []
    total_lines = 0
    total_files_emitted = 0

    print(f"Scanning {SCRIPTORIUM_DIR}...\n")

    for corpus_name, role in discover_corpora():
        corpus_dir = os.path.join(SCRIPTORIUM_DIR, corpus_name)
        conllu = find_conllu_source(corpus_dir)
        if not conllu:
            print(f"  {corpus_name}: SKIPPED (no CoNLL-U source found)")
            continue

        print(f"  {corpus_name} [{role}]:")

        if role == 'nt-split':
            books = split_by_book(conllu, prefix='sahidica', skip_books=NT_SKIP_BOOK_KEYS)
            for output_name, lines, pairs in books:
                total_lines += lines
                total_files_emitted += 1
                all_lemma_pairs.extend(pairs)

        elif role == 'ot-split':
            books = split_by_book(conllu, prefix='sahidic', skip_books=OT_SKIP_BOOK_KEYS)
            for output_name, lines, pairs in books:
                total_lines += lines
                total_files_emitted += 1
                all_lemma_pairs.extend(pairs)

        elif role == 'chapter':
            # output name = name of corpus (e.g. sahidica.mark)
            output_name = corpus_name
            ref_prefix = corpus_name
            lines, pairs = convert_chapter_corpus(str(conllu), output_name, ref_prefix)
            if lines:
                total_lines += lines
                total_files_emitted += 1
                all_lemma_pairs.extend(pairs)

        else:  # flat
            # Output name = CONLLU prefix (often differs from dir name).
            # e.g. dir 'AP' but CONLLU prefix 'apophthegmata.patrum'
            conllu_prefix = Path(conllu).name.replace('_CONLLU', '')
            output_name = conllu_prefix
            ref_prefix = conllu_prefix
            lines, pairs = convert_flat_corpus(str(conllu), output_name, ref_prefix)
            if lines:
                total_lines += lines
                total_files_emitted += 1
                all_lemma_pairs.extend(pairs)

    # Build / extend global lemma table (preserve any existing entries)
    print(f"\nUpdating global lemma table from {len(all_lemma_pairs):,} word occurrences...")
    lemma_path = os.path.join(LEMMA_DIR, 'coptic_lemmas.json')

    lemma_table = {}
    if os.path.exists(lemma_path):
        with open(lemma_path, 'r', encoding='utf-8') as f:
            lemma_table = json.load(f)
        print(f"  loaded {len(lemma_table):,} existing entries")

    new_count = 0
    for form, lemma in all_lemma_pairs:
        if form not in lemma_table:
            lemma_table[form] = lemma
            new_count += 1

    with open(lemma_path, 'w', encoding='utf-8') as f:
        json.dump(lemma_table, f, ensure_ascii=False, indent=0)

    print(f"  +{new_count:,} new forms")
    print(f"  total: {len(lemma_table):,} forms -> {lemma_path}")
    print(f"\n{total_files_emitted} .tess files written, {total_lines:,} lines total")
    print(f"Texts directory: {TEXTS_DIR}")


if __name__ == '__main__':
    main()
