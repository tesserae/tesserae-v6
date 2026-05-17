#!/usr/bin/env python3
"""
Convert Coptic SCRIPTORIUM CoNLL-U files to Tesserae .tess format.

Also builds:
  - data/lemma_tables/coptic_lemmas.json  (word-form -> lemma mapping)
  - cache/lemmas/cop/*.json               (pre-computed per-file lemma caches)

The CoNLL-U format has:
  - # text = <unsegmented Coptic text>    (bound groups, the display form)
  - # sent_id = <corpus-chapter_sNNNN>    (sentence reference)
  - Multi-word token lines: N-M <form> _ _ _ ...
  - Word lines: N <form> <lemma> <UPOS> <XPOS> <feats> ...
  - OrigLang=grc tag in MISC column marks Greek loanwords

We use the bound-group (multi-word token) forms for the .tess surface text,
and collect lemmas from the word-level lines for the lemma table.
"""

import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SCRIPTORIUM_DIR = '/tmp/coptic_scriptorium'
TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'cop')
LEMMA_DIR = os.path.join(PROJECT_ROOT, 'data', 'lemma_tables')
CACHE_DIR = os.path.join(PROJECT_ROOT, 'cache', 'lemmas', 'cop')


def normalize_coptic(text):
    """Normalize Coptic text: NFC, strip combining marks, lowercase."""
    text = unicodedata.normalize('NFC', text)
    # Map legacy block characters
    legacy_map = {
        '\u03E2': '\u2CB2', '\u03E3': '\u2CB3', '\u03E4': '\u2CB4', '\u03E5': '\u2CB5',
        '\u03E6': '\u2CB6', '\u03E7': '\u2CB7', '\u03E8': '\u2CB8', '\u03E9': '\u2CB9',
        '\u03EA': '\u2CBA', '\u03EB': '\u2CBB', '\u03EC': '\u2CBC', '\u03ED': '\u2CBD',
        '\u03EE': '\u2CBE', '\u03EF': '\u2CBF',
    }
    for legacy, primary in legacy_map.items():
        text = text.replace(legacy, primary)
    text = re.sub(r'[\u0300-\u036F]', '', text)
    return text.lower()


def parse_conllu(filepath):
    """Parse a CoNLL-U file into sentences.

    Returns list of sentences, each sentence is a dict:
    {
        'sent_id': str,
        'text': str (original Coptic text),
        'text_en': str (English translation, if available),
        'bound_groups': [(form, lemmas)],  # multi-word tokens with their sub-word lemmas
        'words': [(form, lemma, upos, feats)],  # individual words
    }
    """
    sentences = []
    current = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')

            if line.startswith('# sent_id'):
                if current and current.get('words'):
                    sentences.append(current)
                parts = line.split('=', 1)
                current = {
                    'sent_id': parts[1].strip() if len(parts) > 1 else '',
                    'text': '',
                    'text_en': '',
                    'bound_groups': [],
                    'words': [],
                    '_mwt_ranges': {},  # track multi-word token ranges
                }
            elif line.startswith('# text_en') and current:
                parts = line.split('=', 1)
                current['text_en'] = parts[1].strip() if len(parts) > 1 else ''
            elif line.startswith('# text =') and current:
                current['text'] = line.split('=', 1)[1].strip()
            elif line.startswith('#') or not line.strip():
                continue
            elif current:
                fields = line.split('\t')
                if len(fields) < 10:
                    continue

                token_id = fields[0]
                form = fields[1]
                lemma = fields[2]
                upos = fields[3]

                if '-' in token_id:
                    # Multi-word token line: record the bound group form
                    start, end = token_id.split('-')
                    current['_mwt_ranges'][(int(start), int(end))] = form
                elif '.' not in token_id:
                    # Regular word line
                    feats = fields[5] if len(fields) > 5 else '_'
                    head = fields[6] if len(fields) > 6 else '_'
                    deprel = fields[7] if len(fields) > 7 else '_'
                    misc = fields[9] if len(fields) > 9 else '_'
                    current['words'].append((form, lemma, upos, feats, misc))
                    current.setdefault('syntax', []).append((form, lemma, upos, head, deprel))

    if current and current.get('words'):
        sentences.append(current)

    return sentences


def extract_verse_ref(sent_id, chapter_file):
    """Try to extract a chapter.verse reference from the sent_id."""
    # Pattern: sahidica_mark-Mark_01_s0001 -> Mark.1.1
    # Or: sahidica.1corinthians-1Cor_02_s0012 -> 1Cor.2.12
    m = re.search(r's(\d+)', sent_id)
    sent_num = int(m.group(1)) if m else 0

    # Get chapter number from filename
    ch_m = re.search(r'_(\d+)', chapter_file)
    ch_num = int(ch_m.group(1)) if ch_m else 0

    return ch_num, sent_num


def convert_corpus(corpus_name, conllu_dir, output_name, ref_prefix):
    """Convert a set of CoNLL-U files into a single .tess file.

    Returns (lemma_pairs, line_count) where lemma_pairs is list of (form, lemma).
    """
    conllu_files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not conllu_files:
        print(f"  WARNING: No .conllu files found in {conllu_dir}")
        return [], 0

    all_lines = []
    all_lemma_pairs = []
    file_lemma_cache = {}  # ref -> {tokens, lemmas} for cache file

    for conllu_file in conllu_files:
        sentences = parse_conllu(conllu_file)
        ch_num, _ = extract_verse_ref('', conllu_file.stem)

        for sent_idx, sent in enumerate(sentences, 1):
            # Build the display text from the original text or bound groups
            display_text = sent['text']
            if not display_text:
                # Fallback: reconstruct from word forms
                display_text = ' '.join(w[0] for w in sent['words'] if w[2] != 'PUNCT')

            # Clean up: remove brackets, extra spaces
            display_text = re.sub(r'[\[\]]', '', display_text)
            display_text = re.sub(r'\s+', ' ', display_text).strip()
            # Remove trailing punctuation for cleaner display
            display_text = display_text.rstrip(' .')

            if not display_text:
                continue

            # Build reference
            ref = f'<{ref_prefix}.{ch_num}.{sent_idx}>'

            all_lines.append(f'{ref}\t{display_text}')

            # Collect lemma pairs from word-level annotations
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
                    all_lemma_pairs.append((norm_form, norm_lemma))

            file_lemma_cache[f'{ref_prefix}.{ch_num}.{sent_idx}'] = {
                'tokens': tokens,
                'lemmas': lemmas,
            }

    if not all_lines:
        return [], 0

    # Write .tess file
    tess_path = os.path.join(TEXTS_DIR, f'{output_name}.tess')
    with open(tess_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_lines) + '\n')
    print(f"    -> {output_name}.tess: {len(all_lines)} lines")

    # Write lemma cache
    cache_path = os.path.join(CACHE_DIR, f'{output_name}.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(file_lemma_cache, f, ensure_ascii=False)

    return all_lemma_pairs, len(all_lines)


def convert_non_chapter_corpus(corpus_name, conllu_dir, output_name, ref_prefix):
    """Convert corpora that aren't split by chapter (e.g., Apophthegmata)."""
    conllu_files = sorted(Path(conllu_dir).glob('*.conllu'))
    if not conllu_files:
        print(f"  WARNING: No .conllu files found in {conllu_dir}")
        return [], 0

    all_lines = []
    all_lemma_pairs = []
    file_lemma_cache = {}
    global_sent = 0

    for conllu_file in conllu_files:
        sentences = parse_conllu(conllu_file)
        # Use filename stem as section identifier
        section = conllu_file.stem.replace('.', '_')

        for sent_idx, sent in enumerate(sentences, 1):
            global_sent += 1
            display_text = sent['text']
            if not display_text:
                display_text = ' '.join(w[0] for w in sent['words'] if w[2] != 'PUNCT')
            display_text = re.sub(r'[\[\]]', '', display_text)
            display_text = re.sub(r'\s+', ' ', display_text).strip().rstrip(' .')
            if not display_text:
                continue

            ref = f'<{ref_prefix}.{global_sent}>'
            all_lines.append(f'{ref}\t{display_text}')

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
                    all_lemma_pairs.append((norm_form, norm_lemma))

            file_lemma_cache[f'{ref_prefix}.{global_sent}'] = {
                'tokens': tokens,
                'lemmas': lemmas,
            }

    if not all_lines:
        return [], 0

    tess_path = os.path.join(TEXTS_DIR, f'{output_name}.tess')
    with open(tess_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_lines) + '\n')
    print(f"    -> {output_name}.tess: {len(all_lines)} lines")

    cache_path = os.path.join(CACHE_DIR, f'{output_name}.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(file_lemma_cache, f, ensure_ascii=False)

    return all_lemma_pairs, len(all_lines)


def main():
    os.makedirs(TEXTS_DIR, exist_ok=True)
    os.makedirs(LEMMA_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    all_lemma_pairs = []
    total_lines = 0

    # Demo corpora to convert
    corpora = [
        # (display_name, conllu_dir, output_filename, ref_prefix, chapter_based)
        ('Gospel of Mark (Sahidic)',
         os.path.join(SCRIPTORIUM_DIR, 'sahidica.mark', 'sahidica.mark_CONLLU'),
         'sahidica.mark', 'sahidica.mark', True),
        ('1 Corinthians (Sahidic)',
         os.path.join(SCRIPTORIUM_DIR, 'sahidica.1corinthians', 'sahidica.1corinthians_CONLLU'),
         'sahidica.1corinthians', 'sahidica.1corinthians', True),
        ('Apophthegmata Patrum',
         os.path.join(SCRIPTORIUM_DIR, 'AP', 'apophthegmata.patrum_CONLLU'),
         'apophthegmata.patrum', 'apophthegmata.patrum', False),
    ]

    # Check for Shenoute texts
    shenoute_dirs = [
        ('Shenoute - Abraham',
         os.path.join(SCRIPTORIUM_DIR, 'abraham', 'shenoute.abraham_CONLLU'),
         'shenoute.abraham', 'shenoute.abraham', False),
        ('Shenoute - Eagerness',
         os.path.join(SCRIPTORIUM_DIR, 'shenoute-eagerness',
                      'shenoute.eagerness_CONLLU' if os.path.isdir(
                          os.path.join(SCRIPTORIUM_DIR, 'shenoute-eagerness', 'shenoute.eagerness_CONLLU'))
                      else ''),
         'shenoute.eagerness', 'shenoute.eagerness', False),
    ]
    for item in shenoute_dirs:
        if os.path.isdir(item[1]):
            corpora.append(item)

    # Look for more Shenoute texts
    for d in Path(SCRIPTORIUM_DIR).iterdir():
        if d.is_dir() and d.name.startswith('shenoute') and d.name not in ('shenoute-eagerness',):
            conllu_subdir = list(d.glob('*_CONLLU'))
            if conllu_subdir:
                name = d.name.replace('-', '_')
                already = any(c[2].replace('.', '_') == name for c in corpora)
                if not already:
                    corpora.append((
                        f'Shenoute - {d.name}',
                        str(conllu_subdir[0]),
                        f'shenoute.{d.name.replace("shenoute-", "")}',
                        f'shenoute.{d.name.replace("shenoute-", "")}',
                        False,
                    ))

    print(f"Converting {len(corpora)} Coptic corpora from SCRIPTORIUM...\n")

    for display_name, conllu_dir, output_name, ref_prefix, chapter_based in corpora:
        print(f"  {display_name}:")
        if not os.path.isdir(conllu_dir):
            print(f"    SKIPPED (directory not found: {conllu_dir})")
            continue

        if chapter_based:
            pairs, lines = convert_corpus(display_name, conllu_dir, output_name, ref_prefix)
        else:
            pairs, lines = convert_non_chapter_corpus(display_name, conllu_dir, output_name, ref_prefix)

        all_lemma_pairs.extend(pairs)
        total_lines += lines

    # Build global lemma table
    print(f"\nBuilding lemma table from {len(all_lemma_pairs)} word occurrences...")
    lemma_table = {}
    for form, lemma in all_lemma_pairs:
        if form not in lemma_table:
            lemma_table[form] = lemma

    lemma_path = os.path.join(LEMMA_DIR, 'coptic_lemmas.json')
    with open(lemma_path, 'w', encoding='utf-8') as f:
        json.dump(lemma_table, f, ensure_ascii=False, indent=0)

    print(f"Lemma table: {len(lemma_table)} unique forms -> {lemma_path}")
    print(f"Total lines across all texts: {total_lines}")
    print(f"Texts directory: {TEXTS_DIR}")


if __name__ == '__main__':
    main()
