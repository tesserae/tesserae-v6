#!/usr/bin/env python3
"""
Cross-language recall benchmark: a Latin work against Homer, gold pairs from a CSV.

A generalization of benchmark_knauer_crosslingual.py. Each CSV row names a Latin
line (latin_line_start of latin_book) and a Homeric passage (homer_book, lines
homer_line_start to homer_line_end). For each row, every line of that one Homer
book is ranked by its fused cross-language score with the Latin line (the scoring
is shared with the Knauer script, in crosslingual_common.py). Two measures:

  exact      the Knauer measure: the gold Homer line (for a range, the best line
             of the range) ranks within the top K, rank = 1 + the number of other
             lines scoring strictly higher.
  tolerance  the gold line counts as found when it lies within --tolerance lines
             of one of the K highest-scoring lines (a range is found when any
             line of it does).

Usage:
    python evaluation/scripts/benchmark_juhnke_crosslingual.py \\
        --gold path/to/parallels.csv --latin-work all --homer-work both \\
        --top-k 50 --tolerance 3 --min-confidence high --out results.json

The CSV columns used: latin_work, latin_book, latin_line_start, latin_line_end,
homer_work, homer_book, homer_line_start, homer_line_end, mark, sources,
confidence, resolved. Latin text is the whole-work file in texts/la/ (for
example statius.thebaid.tess); Homer text is the per-book file in texts/grc/
(homer.iliad.part.N.tess).
"""

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crosslingual_common import TEXTS_DIR, make_fused_scorer, normalize_ref  # noqa: E402

LATIN_WORKS = ['statius.thebaid', 'statius.achilleid', 'silius_italicus.punica']
HOMER_WORKS = ['homer.iliad', 'homer.odyssey']
CUTOFFS = (10, 50, 100)
CONFIDENCE_ORDER = {'doubtful': 0, 'high': 1}


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def count_scholars(sources):
    """Rough count of distinct sigla in a sources string (the scan text is noisy)."""
    sigla = set()
    for tok in re.findall(r"\b[A-Z][A-Za-z]{0,4}\b", sources or ''):
        if re.fullmatch(r"[IVXLC]+", tok) or tok in {'Ubers', 'Uber'}:
            continue
        sigla.add(tok)
    return len(sigla)


def load_rows(args):
    rows = []
    with open(args.gold, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['resolved'] != 'yes':
                continue
            if CONFIDENCE_ORDER.get(r['confidence'], -1) < CONFIDENCE_ORDER[args.min_confidence]:
                continue
            if args.latin_work != 'all' and r['latin_work'] != args.latin_work:
                continue
            if args.homer_work != 'both' and r['homer_work'] != args.homer_work:
                continue
            if r['latin_work'] not in LATIN_WORKS or r['homer_work'] not in HOMER_WORKS:
                continue
            row = {
                'latin_work': r['latin_work'], 'latin_book': to_int(r['latin_book']),
                'latin_start': to_int(r['latin_line_start']),
                'latin_end': to_int(r['latin_line_end']),
                'homer_work': r['homer_work'], 'homer_book': to_int(r['homer_book']),
                'homer_start': to_int(r['homer_line_start']),
                'homer_end': to_int(r['homer_line_end']),
                'mark': r['mark'], 'sources': r['sources'],
            }
            if None in (row['latin_book'], row['latin_start'], row['homer_book'], row['homer_start']):
                continue
            if row['latin_end'] is None:
                row['latin_end'] = row['latin_start']
            if row['homer_end'] is None:
                row['homer_end'] = row['homer_start']
            rows.append(row)
    return rows


def index_units(units):
    """Map (book, line) -> unit index, and keep each unit's line number."""
    idx = {}
    for i, u in enumerate(units):
        key = normalize_ref(u.get('ref', ''))
        if key is not None and key not in idx:
            idx[key] = i
    return idx


def evaluate_group(tp, load_embeddings, latin_cache, latin_work, homer_work, homer_book,
                   rows, top_k_max, tolerance):
    lat_path = TEXTS_DIR / 'la' / f'{latin_work}.tess'
    grc_path = TEXTS_DIR / 'grc' / f'{homer_work}.part.{homer_book}.tess'
    if not grc_path.exists():
        for r in rows:
            r['status'] = 'homer_file_missing'
        return
    if latin_work not in latin_cache:
        units = tp.process_file(str(lat_path), 'la')
        emb = load_embeddings(str(lat_path), 'la')
        if emb is None:
            raise SystemExit(f'No embeddings for {lat_path}')
        if emb.shape[0] != len(units):
            raise SystemExit(f'{latin_work}: {emb.shape[0]} embedding rows but {len(units)} units')
        latin_cache[latin_work] = (units, emb, index_units(units))
    lat_units, lat_emb, lat_index = latin_cache[latin_work]

    grc_units = tp.process_file(str(grc_path), 'grc')
    grc_emb = load_embeddings(str(grc_path), 'grc')
    if grc_emb is None:
        raise SystemExit(f'No embeddings for {grc_path}')
    if grc_emb.shape[0] != len(grc_units):
        raise SystemExit(f'{grc_path.name}: {grc_emb.shape[0]} embedding rows but {len(grc_units)} units')
    grc_index = index_units(grc_units)
    grc_lines = [normalize_ref(u.get('ref', '')) for u in grc_units]

    # Resolve each row to a Latin unit and the Homer units of its range.
    needed = set()
    for r in rows:
        lat_i = None
        for ln in range(r['latin_start'], r['latin_end'] + 1):
            lat_i = lat_index.get((r['latin_book'], ln))
            if lat_i is not None:
                break
        homer_is = [grc_index[(homer_book, ln)]
                    for ln in range(r['homer_start'], r['homer_end'] + 1)
                    if (homer_book, ln) in grc_index]
        r['_lat_i'], r['_homer_is'] = lat_i, homer_is
        if lat_i is None:
            r['status'] = 'latin_line_not_found'
        elif not homer_is:
            r['status'] = 'homer_line_not_found'
        else:
            r['status'] = 'ok'
            needed.add(lat_i)

    if not needed:
        return
    print(f'  {len(grc_units)} Greek x {len(lat_units)} Latin units, {len(needed)} Latin lines to score')
    fused_score, n_syntax = make_fused_scorer(
        grc_path, lat_path, grc_units, lat_units, grc_emb, lat_emb,
        lat_indices=sorted(needed), verbose=False)

    score_cache = {}
    for r in rows:
        if r['status'] != 'ok':
            continue
        lat_i = r['_lat_i']
        if lat_i not in score_cache:
            score_cache[lat_i] = [fused_score(g, lat_i) for g in range(len(grc_units))]
        scores = score_cache[lat_i]
        # exact: best rank among the range lines, rank = 1 + strictly higher others
        best_rank = None
        for h in r['_homer_is']:
            gold = scores[h]
            rank = 1 + sum(1 for g, s in enumerate(scores) if g != h and s > gold)
            if best_rank is None or rank < best_rank:
                best_rank = rank
        r['rank_exact'] = best_rank
        # tolerance: nearest top-K line to any gold line, ranked by sorted order
        order = sorted(range(len(scores)), key=lambda g: -scores[g])
        gold_lines = [grc_lines[h][1] for h in r['_homer_is']]
        best_pos = None
        for pos, g in enumerate(order[:max(top_k_max, 200)]):
            line = grc_lines[g][1] if grc_lines[g] else None
            if line is not None and any(abs(line - gl) <= tolerance for gl in gold_lines):
                best_pos = pos + 1
                break
        r['rank_tolerance'] = best_pos  # None when not within the first 200


def recall(rows, key, cutoff):
    ok = [r for r in rows if r['status'] == 'ok']
    if not ok:
        return None
    hit = sum(1 for r in ok if r.get(key) is not None and r[key] <= cutoff)
    return hit, len(ok)


def summarize(rows, label, cutoffs):
    ok = [r for r in rows if r['status'] == 'ok']
    out = {'label': label, 'pairs': len(rows), 'scored': len(ok)}
    for key in ('rank_exact', 'rank_tolerance'):
        for k in cutoffs:
            res = recall(rows, key, k)
            out[f'{key}@{k}'] = None if res is None else round(res[0] / res[1], 4)
    return out


def tables(rows, cutoffs):
    ok_rows = rows

    def group_by(fn):
        groups = defaultdict(list)
        for r in ok_rows:
            for g in fn(r):
                groups[g].append(r)
        return [summarize(v, str(k), cutoffs) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))]

    def is_range(r):
        return r['latin_start'] != r['latin_end'] or r['homer_start'] != r['homer_end']

    return {
        'overall': [summarize(rows, 'all', cutoffs)],
        'by_latin_work': group_by(lambda r: [r['latin_work']]),
        'by_latin_book': group_by(lambda r: [f"{r['latin_work']} {r['latin_book']:02d}"]),
        'by_homer_poem': group_by(lambda r: [r['homer_work']]),
        'by_mark_token': group_by(lambda r: [t if t else 'none' for t in r['mark'].split('+')] or ['none']),
        'by_mark_combination': group_by(lambda r: [r['mark'] or 'none']),
        'by_scholars': group_by(lambda r: ['1 or fewer' if count_scholars(r['sources']) <= 1 else '2 or more']),
        'by_range': group_by(lambda r: ['range' if is_range(r) else 'single line']),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--gold', required=True, help='CSV of Latin-Homer pairs')
    ap.add_argument('--latin-work', default='all', choices=LATIN_WORKS + ['all'])
    ap.add_argument('--homer-work', default='both', choices=HOMER_WORKS + ['both'])
    ap.add_argument('--top-k', type=int, default=50)
    ap.add_argument('--tolerance', type=int, default=3)
    ap.add_argument('--min-confidence', default='high', choices=list(CONFIDENCE_ORDER))
    ap.add_argument('--out', required=True, help='JSON file for per-pair results and tables')
    args = ap.parse_args()

    rows = load_rows(args)
    print(f'{len(rows)} gold rows selected from {args.gold}')
    cutoffs = sorted({10, args.top_k, 100})

    from backend.text_processor import TextProcessor
    from backend.embedding_storage import load_embeddings
    tp = TextProcessor()

    groups = defaultdict(list)
    for r in rows:
        groups[(r['latin_work'], r['homer_work'], r['homer_book'])].append(r)

    latin_cache = {}
    t0 = time.time()
    for n, (key, grp) in enumerate(sorted(groups.items()), 1):
        t1 = time.time()
        print(f'[{n}/{len(groups)}] {key[0]} vs {key[1]} book {key[2]}: {len(grp)} rows')
        evaluate_group(tp, load_embeddings, latin_cache, *key, grp, args.top_k, args.tolerance)
        print(f'  {time.time() - t1:.1f}s')
        sys.stdout.flush()
    elapsed = time.time() - t0

    for r in rows:
        r.pop('_lat_i', None)
        r.pop('_homer_is', None)
        r['is_range'] = r['latin_start'] != r['latin_end'] or r['homer_start'] != r['homer_end']
        r['scholars'] = count_scholars(r['sources'])

    status = defaultdict(int)
    for r in rows:
        status[r['status']] += 1
    result = {
        'args': vars(args), 'seconds': round(elapsed, 1), 'status_counts': dict(status),
        'tables': tables(rows, cutoffs), 'pairs': rows,
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f'\nStatus: {dict(status)}')
    for name in ('overall', 'by_latin_work', 'by_homer_poem'):
        for t in result['tables'][name]:
            print(name, t)
    print(f'Wrote {args.out} in {elapsed:.0f}s')


if __name__ == '__main__':
    main()
