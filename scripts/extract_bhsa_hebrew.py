#!/usr/bin/env python3
"""
Extract Hebrew lemma table and demo .tess files from BHSA via Text-Fabric.

Produces:
  - data/lemma_tables/hebrew_lemmas.json  (word-form -> lemma mapping)
  - texts/he/*.tess                        (biblical books in .tess format)
"""

import json
import os
import re
import sys
import unicodedata

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def normalize_hebrew(text):
    """Strip nikkud/cantillation, NFC normalize."""
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[\u0591-\u05BD\u05BF-\u05C7]', '', text)
    text = text.replace('\u05BE', ' ')  # maqaf -> space
    text = text.replace('\u05C3', '')   # sof pasuq
    return text.strip()


def main():
    print("Loading BHSA via Text-Fabric...")
    from tf.app import use

    # This downloads BHSA data on first run (~120MB)
    A = use('ETCBC/bhsa', hoist=globals(), silent='deep')
    api = A.api
    F = api.F
    L = api.L
    T = api.T

    # =========================================================================
    # 1. Extract lemma table
    # =========================================================================
    print("Extracting lemma table...")
    lemma_table = {}
    word_count = 0

    for word in F.otype.s('word'):
        # Get Hebrew UTF-8 text and lemma
        g_word_utf8 = F.g_word_utf8.v(word)  # full word with nikkud in Hebrew UTF-8
        lex_utf8 = F.lex_utf8.v(word)        # lemma in Hebrew UTF-8

        if not lex_utf8 or not g_word_utf8:
            continue

        # Normalize both form and lemma (strip nikkud)
        form = normalize_hebrew(g_word_utf8)
        lemma = normalize_hebrew(lex_utf8)

        # Also strip trailing special chars from BHSA lemmas (e.g., / = [ )
        lemma = re.sub(r'[/=\[\]()]', '', lemma).strip()

        if form and lemma:
            # If multiple lemmas for same form, keep the first (most common)
            if form not in lemma_table:
                lemma_table[form] = lemma
            word_count += 1

    lemma_path = os.path.join(PROJECT_ROOT, 'data', 'lemma_tables', 'hebrew_lemmas.json')
    os.makedirs(os.path.dirname(lemma_path), exist_ok=True)
    with open(lemma_path, 'w', encoding='utf-8') as f:
        json.dump(lemma_table, f, ensure_ascii=False, indent=0)
    print(f"Lemma table: {len(lemma_table)} unique forms from {word_count} word occurrences -> {lemma_path}")

    # =========================================================================
    # 2. Extract demo texts as .tess files
    # =========================================================================
    texts_dir = os.path.join(PROJECT_ROOT, 'texts', 'he')
    os.makedirs(texts_dir, exist_ok=True)

    # Books to extract (BHSA name, output filename, chapter ranges or None=full)
    # BHSA uses Latin names: Deuteronomium, Samuel_I, Reges_I, Jesaia, Psalmi, etc.
    demo_books = [
        ('Genesis', 'genesis', [(1, 3)]),              # Genesis 1-3 (Creation)
        ('Exodus', 'exodus', [(15, 15)]),              # Exodus 15 (Song of the Sea)
        ('Deuteronomium', 'deuteronomy', [(32, 32)]),  # Deut 32 (Song of Moses)
        ('Samuel_I', '1_samuel', None),                # Full book
        ('Samuel_II', '2_samuel', None),               # Full book
        ('Reges_I', '1_kings', None),                  # Full book
        ('Jesaia', 'isaiah', [(1, 12)]),               # Isaiah 1-12
        ('Psalmi', 'psalms', [(1, 30)]),               # Psalms 1-30
        ('Daniel', 'daniel', None),                    # Full book
        ('Ruth', 'ruth', None),                        # Full book (short)
        ('Chronica_I', '1_chronicles', None),          # For Samuel/Kings parallels
    ]

    for book_name, file_base, chapter_ranges in demo_books:
        print(f"  Extracting {book_name}...")

        # Find the book node
        book_nodes = [b for b in F.otype.s('book') if F.book.v(b) == book_name]
        if not book_nodes:
            print(f"    WARNING: Book '{book_name}' not found in BHSA, skipping")
            continue

        book_node = book_nodes[0]

        # Get chapters
        chapters = L.d(book_node, 'chapter')
        if chapter_ranges:
            selected_chapters = []
            for ch_start, ch_end in chapter_ranges:
                for ch in chapters:
                    ch_num = F.chapter.v(ch)
                    if ch_start <= ch_num <= ch_end:
                        selected_chapters.append(ch)
        else:
            selected_chapters = list(chapters)

        if not selected_chapters:
            print(f"    WARNING: No chapters found for {book_name}")
            continue

        # Determine part numbering
        if chapter_ranges and len(chapter_ranges) == 1:
            ch_start, ch_end = chapter_ranges[0]
            if ch_start == ch_end:
                part_suffix = f'.part.{ch_start}'
            else:
                part_suffix = f'.part.{ch_start}_{ch_end}'
        elif chapter_ranges:
            parts = '_'.join(f'{s}_{e}' for s, e in chapter_ranges)
            part_suffix = f'.part.{parts}'
        else:
            part_suffix = ''

        filename = f'hebrew_bible.{file_base}{part_suffix}.tess'
        filepath = os.path.join(texts_dir, filename)

        lines = []
        for ch in selected_chapters:
            ch_num = F.chapter.v(ch)
            verses = L.d(ch, 'verse')
            for verse in verses:
                v_num = F.verse.v(verse)
                words = L.d(verse, 'word')
                # Get the full Hebrew text of the verse in UTF-8
                word_texts = []
                for w in words:
                    g_word_utf8 = F.g_word_utf8.v(w)
                    if g_word_utf8:
                        word_texts.append(g_word_utf8)
                if word_texts:
                    verse_text = ' '.join(word_texts)
                    ref = f'<hebrew_bible.{file_base}.{ch_num}.{v_num}>'
                    lines.append(f'{ref}\t{verse_text}')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        print(f"    -> {filename}: {len(lines)} verses")

    print("\nDone!")
    print(f"Lemma table: {lemma_path}")
    print(f"Texts: {texts_dir}/")


if __name__ == '__main__':
    main()
