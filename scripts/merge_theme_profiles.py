"""Merge the slices written by profile_theme_search.py into one stage table.

    python scripts/merge_theme_profiles.py OUT.json A.json B.json ...
"""
import json
import statistics
import sys

out, parts = sys.argv[1], sys.argv[2:]
per_query, queries, nondet = {}, [], []
for p in parts:
    d = json.load(open(p))
    per_query.update(d['per_query'])
    queries += d['queries']
    nondet += d['nondeterministic_between_runs']
stages = ['total'] + sorted({k for r in per_query.values() for run in r for k in run if k != 'total'})
table = {}
for st in stages:
    meds = [statistics.median([run.get(st, 0.0) for run in runs]) for runs in per_query.values()]
    table[st] = {'median_s': round(statistics.median(meds), 4), 'mean_s': round(statistics.mean(meds), 4)}
json.dump({'queries': queries, 'table': table, 'per_query': per_query, 'nondeterministic': nondet},
          open(out, 'w'), indent=1)
for st in stages:
    print(f'{table[st]["median_s"]:8.3f} {table[st]["mean_s"]:8.3f}  {st}')
print('nondeterministic:', sorted(set(nondet)))
