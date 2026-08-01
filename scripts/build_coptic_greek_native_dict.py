#!/usr/bin/env python3
"""
Build a Coptic-Greek dictionary for NATIVE Egyptian words (not just loanwords).

The existing coptic_greek.csv covers only Greek loanwords in Coptic (~40% of
vocabulary). This script adds mappings for native Egyptian words by:

1. Extracting all native Egyptian lemmas from SCRIPTORIUM (words NOT tagged OrigLang=grc)
2. For each Egyptian lemma, finding the Greek lemma it most often co-occurs with
   in parallel biblical verses (Sahidic Mark ↔ Greek Mark, Sahidic 1 Cor ↔ Greek 1 Cor)
3. Using PMI (pointwise mutual information) to separate real translations from noise

This is verse-level statistical word alignment applied to Coptic-Greek parallel texts.

Output: Merged into backend/synonymy/v6_additions/coptic_greek.csv
"""

import csv
import math
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SCRIPTORIUM_DIR = '/tmp/coptic_scriptorium'

# Register handlers
from backend.coptic import register as register_coptic
register_coptic()
from backend.text_processor import TextProcessor


def normalize_coptic(text):
    text = unicodedata.normalize('NFC', text)
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


def strip_greek_accents(s):
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def parse_conllu_with_origin(filepath):
    """Parse CoNLL-U extracting lemmas with their language of origin."""
    sentences = []
    current_words = []
    current_id = ''

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('# sent_id'):
                if current_words:
                    sentences.append((current_id, current_words))
                current_id = line.split('=', 1)[1].strip()
                current_words = []
            elif line.startswith('#') or not line.strip():
                continue
            else:
                fields = line.split('\t')
                if len(fields) < 10:
                    continue
                token_id = fields[0]
                if '-' in token_id or '.' in token_id:
                    continue
                form = fields[1]
                lemma = fields[2]
                upos = fields[3]
                misc = fields[9]

                if upos == 'PUNCT':
                    continue

                is_greek = 'OrigLang=grc' in misc
                norm_lemma = normalize_coptic(lemma) if lemma != '_' else normalize_coptic(form)
                if norm_lemma and len(norm_lemma) > 1:
                    current_words.append({
                        'lemma': norm_lemma,
                        'is_greek': is_greek,
                    })

    if current_words:
        sentences.append((current_id, current_words))
    return sentences


def extract_verse_ref_from_sent_id(sent_id):
    """Extract (chapter, sentence_num) from SCRIPTORIUM sent_id."""
    m = re.search(r's(\d+)', sent_id)
    sent_num = int(m.group(1)) if m else 0
    # Chapter from the sent_id pattern like Mark_01_s0005
    ch_m = re.search(r'_(\d+)_s', sent_id)
    ch = int(ch_m.group(1)) if ch_m else 0
    return (ch, sent_num)


def main():
    # Coptic stopwords
    from backend.coptic.stopwords import COPTIC_STOP_WORDS
    cop_stops = COPTIC_STOP_WORDS

    grc_stops = {
        'ο', 'η', 'το', 'και', 'εν', 'δε', 'τον', 'την', 'του', 'τησ',
        'των', 'τοισ', 'ταισ', 'αυτοσ', 'αυτη', 'αυτο', 'αυτων', 'αυτοισ',
        'εισ', 'εκ', 'εξ', 'απο', 'προσ', 'επι', 'κατα', 'μετα', 'περι',
        'παρα', 'δια', 'υπο', 'υπερ', 'συν', 'αντι', 'ωσ', 'ειμι', 'γαρ',
        'μεν', 'ουν', 'τε', 'τισ', 'τι', 'ου', 'ουκ', 'ουχ', 'μη',
        'εγω', 'συ', 'ημεισ', 'υμεισ', 'αλλα', 'ει', 'αν', 'οτι',
    }

    # =========================================================================
    # Step 1: Verse-aligned Coptic-Greek from parallel biblical texts
    # =========================================================================
    print("Step 1: Building verse-aligned dictionary from parallel biblical texts...")

    # Parallel text pairs: Coptic SCRIPTORIUM chapter files <-> Greek corpus
    parallel_sets = [
        {
            'name': 'Gospel of Mark',
            'coptic_dir': os.path.join(SCRIPTORIUM_DIR, 'sahidica.mark', 'sahidica.mark_CONLLU'),
            'greek_file': os.path.join(PROJECT_ROOT, 'texts', 'grc', 'novum_testamentum.secundum_marcum.tess'),
        },
        {
            'name': '1 Corinthians',
            'coptic_dir': os.path.join(SCRIPTORIUM_DIR, 'sahidica.1corinthians', 'sahidica.1corinthians_CONLLU'),
            'greek_file': os.path.join(PROJECT_ROOT, 'texts', 'grc', 'novum_testamentum.pauli_ad_corinthios_prior.tess'),
        },
    ]

    tp = TextProcessor()
    cooccur = Counter()
    cop_freq = Counter()
    grc_freq = Counter()
    n_aligned = 0
    native_egyptian_lemmas = set()

    for ps in parallel_sets:
        cop_dir = ps['coptic_dir']
        grc_file = ps['greek_file']

        if not os.path.isdir(cop_dir):
            print(f"  SKIP: {ps['name']} - Coptic dir not found: {cop_dir}")
            continue
        if not os.path.exists(grc_file):
            print(f"  SKIP: {ps['name']} - Greek file not found: {grc_file}")
            # Try alternate naming
            alt = grc_file.replace('novum_testamentum.', '')
            if os.path.exists(alt):
                grc_file = alt
                print(f"    Found alternate: {alt}")
            else:
                continue

        print(f"  Aligning {ps['name']}...")

        # Load Greek text units by verse reference
        grc_units = {}
        units = tp.process_file(grc_file, 'grc', 'line')
        for unit in units:
            ref = unit.get('ref', '')
            nums = [p for p in ref.split('.') if p.isdigit()]
            if len(nums) >= 2:
                cv = (int(nums[-2]), int(nums[-1]))
                grc_units[cv] = unit

        print(f"    Greek verses: {len(grc_units)}")

        # Load Coptic sentences with origin tags, grouped by chapter
        conllu_files = sorted(Path(cop_dir).glob('*.conllu'))
        cop_by_chapter_sent = {}

        for cf in conllu_files:
            # Extract chapter number from filename (e.g., Mark_01.conllu)
            ch_m = re.search(r'_(\d+)', cf.stem)
            ch_num = int(ch_m.group(1)) if ch_m else 0

            sentences = parse_conllu_with_origin(cf)
            for sent_idx, (sent_id, words) in enumerate(sentences, 1):
                cop_by_chapter_sent[(ch_num, sent_idx)] = words
                for w in words:
                    if not w['is_greek']:
                        native_egyptian_lemmas.add(w['lemma'])

        print(f"    Coptic sentences: {len(cop_by_chapter_sent)}, native lemmas: {len(native_egyptian_lemmas)}")

        # Align by chapter.verse -> chapter.sentence
        # The Coptic sentence numbering within a chapter roughly corresponds to verses
        for (ch, sent_num), cop_words in cop_by_chapter_sent.items():
            # Try to match with Greek verse (ch, sent_num)
            grc_unit = grc_units.get((ch, sent_num))
            if not grc_unit:
                continue

            # Get native Egyptian Coptic lemmas (exclude Greek loanwords)
            cop_lemmas = set()
            for w in cop_words:
                if not w['is_greek'] and w['lemma'] not in cop_stops and len(w['lemma']) > 1:
                    cop_lemmas.add(w['lemma'])

            grc_lemmas = set()
            for gl in grc_unit.get('lemmas', []):
                stripped = strip_greek_accents(gl)
                if stripped and stripped not in grc_stops and len(stripped) > 1:
                    grc_lemmas.add(stripped)

            if not cop_lemmas or not grc_lemmas:
                continue

            n_aligned += 1
            for cl in cop_lemmas:
                cop_freq[cl] += 1
                for gl in grc_lemmas:
                    cooccur[(cl, gl)] += 1
            for gl in grc_lemmas:
                grc_freq[gl] += 1

    print(f"\nAligned verse pairs: {n_aligned}")
    print(f"Raw co-occurrence pairs: {len(cooccur)}")

    # Score by PMI
    alignment_pairs = []
    if n_aligned > 0:
        for (cl, gl), count in cooccur.items():
            if count < 2:
                continue
            p_joint = count / n_aligned
            p_cop = cop_freq[cl] / n_aligned
            p_grc = grc_freq[gl] / n_aligned
            if p_cop > 0 and p_grc > 0:
                pmi = math.log2(p_joint / (p_cop * p_grc))
                if pmi > 0:
                    alignment_pairs.append((cl, gl, pmi, count))

        alignment_pairs.sort(key=lambda x: (-x[2], -x[3]))
        print(f"PMI-filtered native alignment pairs: {len(alignment_pairs)}")

    # =========================================================================
    # Step 2: Merge with existing loanword dictionary
    # =========================================================================
    print("\nStep 2: Merging with existing loanword dictionary...")

    existing_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions', 'coptic_greek.csv')
    existing_pairs = set()
    if os.path.exists(existing_path):
        with open(existing_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    existing_pairs.add((row[0], row[1]))
        print(f"  Existing loanword pairs: {len(existing_pairs)}")

    # Merge
    alignment_set = set((cl, gl) for cl, gl, _, _ in alignment_pairs)
    merged = existing_pairs | alignment_set
    print(f"  Alignment pairs: {len(alignment_set)}")
    print(f"  Merged total: {len(merged)}")
    print(f"  Overlap: {len(existing_pairs & alignment_set)}")

    # Write merged dictionary
    with open(existing_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for cl, gl in sorted(merged):
            writer.writerow([cl, gl])
    print(f"  Written to {existing_path}")

    # Write detailed version
    detail_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'coptic_greek_alignment.csv')
    with open(detail_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['coptic', 'greek', 'pmi', 'count', 'source'])
        for cl, gl, pmi, count in alignment_pairs:
            src = 'alignment+loanword' if (cl, gl) in existing_pairs else 'alignment'
            writer.writerow([cl, gl, f'{pmi:.3f}', count, src])
        for cl, gl in existing_pairs:
            if (cl, gl) not in alignment_set:
                writer.writerow([cl, gl, '', '', 'loanword_only'])
    print(f"  Detailed version: {detail_path}")

    # Print top 30 new alignment pairs (native Egyptian -> Greek)
    new_native = [(cl, gl, pmi, n) for cl, gl, pmi, n in alignment_pairs if (cl, gl) not in existing_pairs]
    print(f"\nTop 30 NEW native Egyptian-Greek pairs (not loanwords):")
    for cl, gl, pmi, count in new_native[:30]:
        print(f"  {cl:15s} <-> {gl:15s} (PMI={pmi:.2f}, n={count})")


if __name__ == '__main__':
    main()
