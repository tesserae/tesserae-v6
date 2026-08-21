#!/usr/bin/env python3
"""Lemmatize all aligned Hebrew <-> Septuagint book pairs once and cache to a pickle,
so dictionary-building and benchmarking can iterate without re-lemmatizing Greek (slow).

Stores per book: he = [(chapter.verse, [hebrew content lemmas])],
                  lxx = [(chapter.verse, [normalized greek content lemmas])].
"""
import os, sys, re, pickle, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.text_processor import TextProcessor
from backend.hebrew import register as reg_he
reg_he()
from backend.fusion import _STOPLISTS
from backend.synonym_dict import CROSSLINGUAL_STOPLIST_GREEK
HE_STOP = _STOPLISTS.get('he', set())

# Hebrew book -> Septuagint book (chapter:verse aligned; heavily-reordered books excluded)
MAP = {
    'genesis': 'genesis', 'exodus': 'exodus', 'leviticus': 'levitikon',
    'numbers': 'arithmoi', 'deuteronomy': 'deuteronomion',
    'joshua': 'josue', 'judges': 'kritai', 'ruth': 'ruth',
    '1_samuel': 'basileion_a', '2_samuel': 'basileion_b',
    '1_kings': 'basileion_g', '2_kings': 'basileion_d',
    'isaiah': 'isaias', 'ezekiel': 'ezechiel',
    'hosea': 'osee', 'joel': 'joel', 'amos': 'amos', 'obadiah': 'abdias',
    'jonah': 'jonas', 'micah': 'michaeas', 'nahum': 'nahum', 'habakkuk': 'habacuc',
    'zephaniah': 'sophonias', 'haggai': 'aggaeus', 'zechariah': 'zacharias', 'malachi': 'malachias',
}

def norm_gr(s):
    s = unicodedata.normalize('NFD', str(s).strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('ς', 'σ')

def chv(ref):
    m = re.search(r'(\d+)[.:](\d+)\s*$', str(ref))
    return f'{m.group(1)}.{m.group(2)}' if m else None

def main():
    tp = TextProcessor()
    out = {}
    for i, (he_book, lxx_book) in enumerate(MAP.items(), 1):
        he_fp = os.path.join(ROOT, 'texts/he', f'hebrew_bible.{he_book}.tess')
        lxx_fp = os.path.join(ROOT, 'texts/grc', f'septuaginta.{lxx_book}.tess')
        if not (os.path.exists(he_fp) and os.path.exists(lxx_fp)):
            print(f'[{i}/{len(MAP)}] {he_book}: MISSING, skip', flush=True); continue
        he = []
        for u in tp.process_file(he_fp, 'he', 'line'):
            r = chv(u.get('ref'))
            if r:
                he.append((r, [l for l in u.get('lemmas', []) if l and l not in HE_STOP]))
        lxx = []
        for u in tp.process_file(lxx_fp, 'grc', 'line'):
            r = chv(u.get('ref'))
            if r:
                gs = [norm_gr(l) for l in u.get('lemmas', []) if l]
                gs = [g for g in gs if len(g) >= 3 and g not in CROSSLINGUAL_STOPLIST_GREEK]
                lxx.append((r, gs))
        out[he_book] = {'lxx_book': lxx_book, 'he': he, 'lxx': lxx}
        print(f'[{i}/{len(MAP)}] {he_book} <-> {lxx_book}: he {len(he)} / lxx {len(lxx)} verses', flush=True)
    dest = os.path.join(ROOT, 'research/languages/hebrew/hegrc_lemmas.pkl')
    with open(dest, 'wb') as f:
        pickle.dump(out, f)
    print(f'CACHED {len(out)} book pairs -> {dest}', flush=True)
    print('CACHE DONE', flush=True)

if __name__ == '__main__':
    main()
