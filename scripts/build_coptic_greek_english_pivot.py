#!/usr/bin/env python3
"""
Build Coptic-Greek dictionary for native Egyptian words using sentence-level
English translations as a pivot.

SCRIPTORIUM CoNLL-U files include:
  # text_en = <English translation of each sentence>

For each native Egyptian lemma (no OrigLang=grc), we collect the English words
that appear in translations of sentences containing that lemma. We then match
these English words against the Perseus Greek-English dictionary to find the
Greek equivalents.

This is an English-pivot approach, but using sentence-aligned translations
(not separate dictionary glosses), which is more precise because the English
is a direct translation of the Coptic.

Combined with the existing loanword dictionary, this gives coverage of both
the ~40% Greek-borrowed and ~60% native Egyptian vocabulary.
"""

import csv
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SCRIPTORIUM_DIR = '/tmp/coptic_scriptorium'


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


def normalize_english(word):
    return re.sub(r'[^a-z]', '', word.lower())


# Common English stopwords to exclude from pivot
ENGLISH_STOPS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'shall', 'can', 'this', 'that',
    'these', 'those', 'it', 'its', 'he', 'she', 'they', 'them', 'his',
    'her', 'their', 'my', 'your', 'our', 'i', 'you', 'we', 'me', 'him',
    'us', 'who', 'which', 'what', 'when', 'where', 'how', 'why', 'if',
    'not', 'no', 'nor', 'so', 'as', 'than', 'too', 'very', 'just',
    'about', 'up', 'out', 'into', 'over', 'after', 'before', 'then',
    'there', 'here', 'all', 'each', 'every', 'both', 'few', 'more',
    'most', 'other', 'some', 'any', 'such', 'only', 'own', 'same',
    'also', 'back', 'even', 'still', 'now', 'well', 'upon',
}


def main():
    # =========================================================================
    # Step 1: Collect Coptic lemma -> English word associations from SCRIPTORIUM
    # =========================================================================
    print("Step 1: Scanning SCRIPTORIUM for native Egyptian lemma -> English associations...")

    # For each native Egyptian lemma, count which English words co-occur
    cop_eng_cooccur = Counter()  # (cop_lemma, eng_word) -> count
    cop_freq = Counter()         # cop_lemma -> count in sentences with English
    eng_freq = Counter()         # eng_word -> count in sentences

    conllu_files = list(Path(SCRIPTORIUM_DIR).rglob('*.conllu'))
    n_sentences = 0
    n_with_english = 0

    for filepath in conllu_files:
        current_english = ''
        current_words = []

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')

                if line.startswith('# text_en') and '=' in line:
                    # Flush previous sentence
                    if current_english and current_words:
                        _process_sentence(current_words, current_english,
                                         cop_eng_cooccur, cop_freq, eng_freq)
                        n_with_english += 1
                    current_english = line.split('=', 1)[1].strip()
                    current_words = []
                    n_sentences += 1
                elif line.startswith('# sent_id'):
                    if current_english and current_words:
                        _process_sentence(current_words, current_english,
                                         cop_eng_cooccur, cop_freq, eng_freq)
                        n_with_english += 1
                    current_english = ''
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
                    lemma = fields[2]
                    upos = fields[3]
                    misc = fields[9]
                    if upos == 'PUNCT':
                        continue
                    is_greek = 'OrigLang=grc' in misc
                    if not is_greek:
                        norm = normalize_coptic(lemma) if lemma != '_' else normalize_coptic(fields[1])
                        if norm and len(norm) > 1:
                            current_words.append(norm)

        # Flush last sentence
        if current_english and current_words:
            _process_sentence(current_words, current_english,
                             cop_eng_cooccur, cop_freq, eng_freq)
            n_with_english += 1

    print(f"  Sentences: {n_sentences}, with English: {n_with_english}")
    print(f"  Native Egyptian lemmas seen: {len(cop_freq)}")
    print(f"  English words seen: {len(eng_freq)}")
    print(f"  Co-occurrence pairs: {len(cop_eng_cooccur)}")

    # =========================================================================
    # Step 2: Load Perseus Greek-English dictionary
    # =========================================================================
    print("\nStep 2: Loading Greek-English dictionary...")
    grc_eng_path = os.path.join(PROJECT_ROOT, 'data', 'perseus_lexicon', 'extracted', 'greek_english.csv')

    grc_by_eng = defaultdict(set)  # english_word -> set of greek_lemmas
    with open(grc_eng_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) < 2:
                continue
            grc_word = strip_greek_accents(row[0])
            eng_senses = row[1].lower() if len(row) > 1 else ''
            # Split into individual words
            for word in re.split(r'[,;/\s]+', eng_senses):
                word = normalize_english(word)
                if word and len(word) > 2 and word not in ENGLISH_STOPS:
                    grc_by_eng[word].add(grc_word)

    print(f"  Greek-English entries: {len(grc_by_eng)} English words -> Greek lemmas")

    # =========================================================================
    # Step 3: Pivot: Coptic -> English -> Greek
    # =========================================================================
    print("\nStep 3: Building Coptic-Greek pairs via English pivot...")

    pair_scores = defaultdict(float)
    for (cop, eng), count in cop_eng_cooccur.items():
        if count < 3:  # require at least 3 co-occurrences
            continue
        if eng not in grc_by_eng:
            continue
        # Score: frequency of co-occurrence, penalized by ambiguity
        for grc in grc_by_eng[eng]:
            # Weight by how specific the association is
            specificity = count / (cop_freq[cop] * len(grc_by_eng[eng]))
            pair_scores[(cop, grc)] += specificity

    # Filter by score
    good_pairs = [(cop, grc, score) for (cop, grc), score in pair_scores.items()
                  if score >= 0.01]
    good_pairs.sort(key=lambda x: -x[2])
    print(f"  Pivot pairs (score >= 0.01): {len(good_pairs)}")

    # =========================================================================
    # Step 4: Merge with existing loanword dictionary
    # =========================================================================
    print("\nStep 4: Merging with existing loanword dictionary...")
    existing_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions', 'coptic_greek.csv')
    existing_pairs = set()
    if os.path.exists(existing_path):
        with open(existing_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    existing_pairs.add((row[0], row[1]))

    pivot_set = set((cop, grc) for cop, grc, _ in good_pairs)
    merged = existing_pairs | pivot_set
    print(f"  Existing loanword pairs: {len(existing_pairs)}")
    print(f"  New pivot pairs: {len(pivot_set)}")
    print(f"  Overlap: {len(existing_pairs & pivot_set)}")
    print(f"  Merged total: {len(merged)}")

    # Write merged dictionary
    with open(existing_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for cop, grc in sorted(merged):
            writer.writerow([cop, grc])
    print(f"  Written to {existing_path}")

    # Print top 30 new native Egyptian -> Greek pairs
    new_native = [(c, g, s) for c, g, s in good_pairs if (c, g) not in existing_pairs]
    print(f"\nTop 30 NEW native Egyptian -> Greek pairs:")
    for cop, grc, score in new_native[:30]:
        print(f"  {cop:15s} <-> {grc:15s} (score={score:.4f})")


def _process_sentence(cop_words, english_text, cop_eng_cooccur, cop_freq, eng_freq):
    """Process one sentence: record co-occurrences between Coptic lemmas and English words."""
    # Extract English content words
    eng_words = set()
    for word in re.split(r'[\s,;.!?\'\"()\[\]]+', english_text.lower()):
        word = normalize_english(word)
        if word and len(word) > 2 and word not in ENGLISH_STOPS:
            eng_words.add(word)

    if not eng_words:
        return

    cop_lemmas = set(cop_words)
    for cl in cop_lemmas:
        cop_freq[cl] += 1
        for ew in eng_words:
            cop_eng_cooccur[(cl, ew)] += 1

    for ew in eng_words:
        eng_freq[ew] += 1


if __name__ == '__main__':
    main()
