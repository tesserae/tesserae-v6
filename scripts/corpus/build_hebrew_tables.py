#!/usr/bin/env python3
"""Build the Hebrew lookup tables from BHSA, keyed by pointed form as well as
by consonants, with homographs told apart.

Why (issue #483). The old tables (scripts/extract_bhsa_hebrew.py) keyed every
word by its consonants and kept the first lemma seen, so words that share a
spelling collapsed into one lemma: אל is the preposition "to", the negative
"not" and the noun "God"; עם is "with" and "people"; מלך is "king" and "he
reigned". Measured on BHSA's 420,102 word occurrences, 5.2% received the
wrong lemma that way. Our texts are pointed (the Miqra according to the
Masorah, via Sefaria), and the vowel points settle four fifths of those
cases, so the lemmatizer now looks a word up by its pointed form first and
falls back to the consonants.

What this writes, all under data/lemma_tables/:
  hebrew_lemmas_pointed.json   pointed key -> lemma
  hebrew_pos_pointed.json      pointed key -> BHSA part of speech
  hebrew_lemmas.json           consonantal form -> lemma   (the fallback)
  hebrew_pos.json              consonantal form -> part of speech
  hebrew_homographs.json       lemma -> BHSA lexeme, vocalized lexeme, gloss,
                               part of speech, frequency, for every lemma that
                               shares its consonants with another

The lemma for a BHSA lexeme is its consonantal spelling. When several lexemes
share one spelling, the most frequent keeps the bare spelling and the others
carry a superscript number in order of frequency: אל (to), אל² (not),
אל³ (God); עם (people), עם² (with); מלך (king), מלך² (be king). The number is
part of the lemma string wherever lemmas are stored or compared; strip it
with backend.hebrew.processor.base_lemma to get the consonants back, which
the cross-language dictionaries, keyed by consonants, rely on.

A table value is the lemma (or tag) of the most frequent lexeme among the
occurrences of that key, so the consonantal fallback now gives the majority
reading rather than the first one BHSA happened to list.

The pointed key is backend.hebrew.processor.pointed_key: vowel points kept,
accents, meteg and rafe dropped, dagesh dropped, holam-for-waw and qamats
qatan folded into their plain marks, and a holam written before a waw moved
after it, which is how Sefaria writes it. With that key a table built here
finds 99.3% of the 328,822 words in texts/he by pointed form (measured
2026-10-01); the rest fall back to consonants.

    venv/bin/python scripts/corpus/build_hebrew_tables.py [--out data/lemma_tables]

Needs Text-Fabric and the ETCBC/BHSA data (downloaded on first use, ~260 MB,
CC BY-NC: see data/lemma_tables/HEBREW_MORPHOLOGY_LICENSE.txt). Peak memory
about 3 GB; run it under ~/bin/tess-job with a 6 GB cap.
"""
import argparse
import collections
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.hebrew.processor import normalize_hebrew, pointed_key, SUPERSCRIPTS  # noqa: E402


def lexeme_consonants(lex_utf8):
    """The consonantal spelling of a BHSA lexeme, its homograph and
    part-of-speech marks (= / [ ) removed."""
    return re.sub(r'[/=\[\]()]', '', normalize_hebrew(lex_utf8 or '')).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'data', 'lemma_tables'))
    args = ap.parse_args()

    from tf.app import use
    A = use('ETCBC/bhsa', silent='deep')
    F = A.api.F

    # Pass 1: every lexeme, with its frequency, gloss, part of speech and
    # vocalized form, grouped by consonantal spelling.
    lexemes = {}
    for w in F.otype.s('word'):
        lex = F.lex.v(w)
        if not lex or lex in lexemes:
            continue
        lexemes[lex] = {
            'consonants': lexeme_consonants(F.lex_utf8.v(w)),
            'voc': F.voc_lex_utf8.v(w) or '',
            'gloss': F.gloss.v(w) or '',
            'sp': F.sp.v(w) or '',
            'freq': F.freq_lex.v(w) or 0,
        }
    by_consonants = collections.defaultdict(list)
    for lex, info in lexemes.items():
        if info['consonants']:
            by_consonants[info['consonants']].append(lex)

    lemma_of = {}
    homographs = {}
    for cons, lexs in by_consonants.items():
        lexs.sort(key=lambda l: (-lexemes[l]['freq'], l))
        for n, lex in enumerate(lexs):
            if n >= len(SUPERSCRIPTS) + 1:
                # More homographs than numerals (none in BHSA today); the tail
                # shares the last numeral rather than failing the build.
                suffix = SUPERSCRIPTS[-1]
            else:
                suffix = '' if n == 0 else SUPERSCRIPTS[n - 1]
            lemma_of[lex] = cons + suffix
        if len(lexs) > 1:
            for lex in lexs:
                info = lexemes[lex]
                homographs[lemma_of[lex]] = {'lex': lex, 'voc': info['voc'], 'gloss': info['gloss'],
                                             'sp': info['sp'], 'freq': info['freq']}

    # Pass 2: every word occurrence, counted under its pointed key and its
    # consonantal key.
    pointed = collections.defaultdict(collections.Counter)
    consonantal = collections.defaultdict(collections.Counter)
    occurrences = 0
    for w in F.otype.s('word'):
        g = F.g_word_utf8.v(w)
        lex = F.lex.v(w)
        if not g or not lex or lex not in lemma_of:
            continue
        occurrences += 1
        p = pointed_key(g)
        c = normalize_hebrew(g).strip()
        if p:
            pointed[p][lex] += 1
        if c:
            consonantal[c][lex] += 1

    def tables(counts):
        lemma_table, pos_table = {}, {}
        for key, counter in counts.items():
            lex = counter.most_common(1)[0][0]
            lemma_table[key] = lemma_of[lex]
            pos_table[key] = lexemes[lex]['sp']
        return lemma_table, pos_table

    lemmas_p, pos_p = tables(pointed)
    lemmas_c, pos_c = tables(consonantal)

    os.makedirs(args.out, exist_ok=True)

    def dump(name, obj):
        path = os.path.join(args.out, name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=0)
        print(f'{name}: {len(obj)} entries')

    dump('hebrew_lemmas_pointed.json', dict(sorted(lemmas_p.items())))
    dump('hebrew_pos_pointed.json', dict(sorted(pos_p.items())))
    dump('hebrew_lemmas.json', dict(sorted(lemmas_c.items())))
    dump('hebrew_pos.json', dict(sorted(pos_c.items())))
    dump('hebrew_homographs.json', dict(sorted(homographs.items(), key=lambda kv: (kv[0].rstrip(SUPERSCRIPTS), -kv[1]['freq']))))

    ambiguous_cons = sum(1 for c in consonantal.values() if len(c) > 1)
    ambiguous_pointed = sum(1 for c in pointed.values() if len(c) > 1)
    minority_cons = sum(sum(c.values()) - max(c.values()) for c in consonantal.values())
    minority_pointed = sum(sum(c.values()) - max(c.values()) for c in pointed.values())
    print(f'{occurrences} word occurrences, {len(lexemes)} lexemes, '
          f'{len(homographs)} lemmas in homograph groups')
    print(f'consonantal keys ambiguous: {ambiguous_cons}, occurrences the majority reading gets wrong: {minority_cons}')
    print(f'pointed keys ambiguous: {ambiguous_pointed}, occurrences the majority reading gets wrong: {minority_pointed}')


if __name__ == '__main__':
    main()
