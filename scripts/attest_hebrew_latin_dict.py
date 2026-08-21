#!/usr/bin/env python3
"""Precision check for the bridged Hebrew->Latin dictionary using the Vulgate as
ground truth. The Vulgate is the actual Latin translation of the Hebrew Bible, so
Hebrew and Latin lemmas that co-occur in aligned verses are translation-equivalent
evidence. For each bridged (he,la) pair, count co-occurrences across aligned verses
of well-versified books, then report the attestation rate and write a high-precision
subset (attested >= 2). We do NOT replace the full bridge (it must serve the whole
Latin corpus, not only the Vulgate); the subset is an optional high-precision variant.
"""
import os, sys, csv
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.text_processor import TextProcessor
from backend.hebrew import register as register_hebrew
register_hebrew()

# well-versified books (skip Psalms: He/Vulgate numbering offset)
BOOKS = ['genesis', 'exodus', 'deuteronomy', 'joshua', 'judges', '1_samuel', '2_samuel', '1_kings']

def vulgate_path(book):
    import glob
    hits = glob.glob(os.path.join(ROOT, 'texts', 'la', f'jerome.vulgate.part.*.{book}.tess'))
    return hits[0] if hits else None

def vkey(ref):
    # last two dot-separated numeric fields = chapter.verse
    parts = [p for p in str(ref).replace(' ', '.').split('.') if p.isdigit()]
    return '.'.join(parts[-2:]) if len(parts) >= 2 else None

def lu(v):
    return v.lower().replace('v', 'u').replace('j', 'i')

def main():
    tp = TextProcessor()
    cooccur = Counter()
    aligned_verses = 0
    for book in BOOKS:
        he_fp = os.path.join(ROOT, 'texts', 'he', f'hebrew_bible.{book}.tess')
        la_fp = vulgate_path(book)
        if not (os.path.exists(he_fp) and la_fp):
            print(f"skip {book} (missing)", flush=True); continue
        he = tp.process_file(he_fp, 'he', 'line')
        la = tp.process_file(la_fp, 'la', 'line')
        he_by = {}
        for u in he:
            k = vkey(u.get('ref'))
            if k: he_by.setdefault(k, set()).update(x for x in u.get('lemmas', []) if x)
        la_by = {}
        for u in la:
            k = vkey(u.get('ref'))
            if k: la_by.setdefault(k, set()).update(lu(x) for x in u.get('lemmas', []) if x)
        shared = set(he_by) & set(la_by)
        aligned_verses += len(shared)
        for k in shared:
            for h in he_by[k]:
                for l in la_by[k]:
                    cooccur[(h, l)] += 1
        print(f"{book}: he {len(he)} la {len(la)} aligned {len(shared)}", flush=True)

    # load bridged pairs
    bridged = []
    with open(os.path.join(ROOT, 'backend', 'synonymy', 'v6_additions', 'hebrew_latin.csv'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            p = line.split(',')
            if len(p) >= 2:
                bridged.append((p[0].strip(), lu(p[1].strip())))
    bridged = list(dict.fromkeys(bridged))

    a1 = [p for p in bridged if cooccur.get(p, 0) >= 1]
    a2 = [p for p in bridged if cooccur.get(p, 0) >= 2]
    print(f"\naligned verses total: {aligned_verses}")
    print(f"bridged distinct pairs: {len(bridged)}")
    print(f"Vulgate-attested >=1: {len(a1)} ({100*len(a1)/len(bridged):.1f}%)")
    print(f"Vulgate-attested >=2: {len(a2)} ({100*len(a2)/len(bridged):.1f}%)")
    # note: attestation only covers biblical vocab of these 8 books, so this is a LOWER bound
    out = os.path.join(ROOT, 'backend', 'synonymy', 'v6_additions', 'hebrew_latin.attested.csv')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# High-precision subset of hebrew_latin.csv: pairs co-occurring in >=2 aligned\n')
        f.write('# Hebrew/Vulgate verses across genesis,exodus,deuteronomy,joshua,judges,1-2sam,1kings.\n')
        f.write('# Optional variant; the full hebrew_latin.csv remains the shipped dict (wider recall).\n')
        for h, l in sorted(a2):
            f.write(f'{h},{l}\n')
    print(f"wrote {out}")
    # show a few pairs the bridge has that are strongly attested, and a few unattested (likely noise)
    top = sorted(((cooccur[p], p) for p in a2), reverse=True)[:12]
    print("\nstrongly attested sample:", [(p[1], c) for c, p in top])

if __name__ == '__main__':
    main()
