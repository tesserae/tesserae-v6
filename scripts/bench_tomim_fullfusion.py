#!/usr/bin/env python3
"""T'OMIM (narrative, 554 near-verbatim Chronicles<->Samuel/Kings parallels) through the
REAL production mono fusion (run_fusion_search: all 9 channels + fused scoring), not the
best-of-3 5%FP proxy in perseus_trans/tomim_full.py.

Metric (production-realistic): for each known T'OMIM pair whose both verses are in the
corpus, run the actual fusion between the two Hebrew books and check (a) whether the tool
returns that verse pair at all (recall@all) and (b) whether the true target verse is the
top-ranked match for its source verse (R@1, per-source-verse). Reports both + median rank.
"""
import os, sys, re
from collections import defaultdict
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.hebrew import register as reg_he
reg_he()
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import run_fusion_search

BOOK = {'1 Sam':'1_samuel','2 Sam':'2_samuel','1 Kgs':'1_kings','2 Kgs':'2_kings',
        '1 Chr':'1_chronicles','2 Chr':'2_chronicles'}

def parse(ref):
    m = re.match(r'([12]\s+\w+)\s+(\d+):(\d+)', str(ref))
    if not m: return None
    b = BOOK.get(m.group(1))
    return (b, f'{m.group(2)}.{m.group(3)}') if b else None

def chv_of(unit_ref):
    m = re.search(r'\.(\d+)\.(\d+)\s*$', str(unit_ref)) or re.search(r'(\d+)[.:](\d+)\s*$', str(unit_ref))
    return f'{m.group(1)}.{m.group(2)}' if m else None

def get_ref(d, side):
    for k in (f'{side}_ref', f'{side}_locus', f'{side}Ref'):
        if k in d: return d[k]
    idx = d.get(f'{side}_idx', d.get(f'{side}_index'))
    return idx

def main():
    tp = TextProcessor()
    matcher, scorer = Matcher(), Scorer()
    d = pd.read_parquet('/home/ncoffee/perseus_trans/tomim_narrative_pairs_verse.parquet')
    # group T'OMIM pairs by (source_book, target_book)
    groups = defaultdict(list)
    for sref, tref in zip(d['source_ref'], d['target_ref']):
        sp, tp_ = parse(sref), parse(tref)
        if sp and tp_ and sp[0] and tp_[0]:
            groups[(sp[0], tp_[0])].append((sp[1], tp_[1]))
    print(f"T'OMIM narrative pairs mapped: {sum(len(v) for v in groups.values())} in {len(groups)} book-pairs", flush=True)

    units_cache = {}
    def units(book):
        if book not in units_cache:
            fp = os.path.join(ROOT, 'texts/he', f'hebrew_bible.{book}.tess')
            units_cache[book] = (tp.process_file(fp, 'he', 'line'), fp) if os.path.exists(fp) else (None, None)
        return units_cache[book]

    tot_found = tot_r1 = tot_n = 0
    ranks = []
    printed_keys = False
    print(f'{"book-pair":<26}{"pairs":>6}{"found":>7}{"R@1":>7}', flush=True)
    print('-'*46, flush=True)
    for (sb, tb), pairs in sorted(groups.items()):
        su, sfp = units(sb); tu, tfp = units(tb)
        if not su or not tu:
            print(f'{sb+"->"+tb:<26} (book missing, skip)', flush=True); continue
        results = run_fusion_search(su, tu, matcher, scorer,
                                    f'hebrew_bible.{sb}.tess', f'hebrew_bible.{tb}.tess',
                                    language='he', mode='merged', max_results=0,
                                    source_path=sfp, target_path=tfp)
        # corpus chv sets (which pairs are testable)
        s_chv = {chv_of(u.get('ref')) for u in su}
        t_chv = {chv_of(u.get('ref')) for u in tu}
        # ranked results: (source ref, target ref) -> global rank + per-source ranking
        present = {}
        by_src = defaultdict(list)
        for rank, r in enumerate(results):
            sc = chv_of(r.get('source', {}).get('ref'))
            tc = chv_of(r.get('target', {}).get('ref'))
            if sc is None or tc is None: continue
            score = r.get('fused_score', r.get('overall_score', r.get('score', 0.0)))
            present.setdefault((sc, tc), rank)
            by_src[sc].append((score, tc))
        n = found = r1 = 0
        for (sc, tc) in pairs:
            if sc not in s_chv or tc not in t_chv: continue
            n += 1
            if (sc, tc) in present:
                found += 1; ranks.append(present[(sc, tc)])
            cand = sorted(by_src.get(sc, []), reverse=True)
            if cand and cand[0][1] == tc: r1 += 1
        tot_found += found; tot_r1 += r1; tot_n += n
        print(f'{sb+"->"+tb:<26}{n:>6}{(found/n if n else 0):>7.2f}{(r1/n if n else 0):>7.2f}', flush=True)
    med = sorted(ranks)[len(ranks)//2] if ranks else -1
    print('-'*46, flush=True)
    print(f'{"OVERALL":<26}{tot_n:>6}{(tot_found/tot_n if tot_n else 0):>7.2f}{(tot_r1/tot_n if tot_n else 0):>7.2f}', flush=True)
    print(f"\nfound = fraction of known T'OMIM pairs the real fusion returns (recall);"
          f" R@1 = true target is the top match for its source verse; median global rank of found pairs = {med}.", flush=True)
    print('TOMIM FULLFUSION DONE', flush=True)

if __name__ == '__main__':
    main()
