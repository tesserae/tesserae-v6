"""Rebuild the entity mention store from scratch and print its counts.

    venv/bin/python scripts/build_entity_index.py --entities-json KEYS.json \
        [--passage-dir data/passage_index] [--out data/entity_index/entities.sqlite] \
        [--review-csv merge_review.csv] [--no-stoplist] [--matcher stem|lemma] [--no-audit-fixes]
    venv/bin/python scripts/build_entity_index.py --check

KEYS.json is the proper-name list as entity rows (id, greek, latin, english, type, pleiades),
the join of backend/proper_names to the Pleiades gazetteer. Run it after any passage-index
change, in the same chain as build_window_names.py, build_desc_fts.py and
build_desc_vocab.py. Build to a new file, then swap in. Under 6 GB; run it inside
`tess-job --fg NAME 6`. --check reports the store as stale when the counted-window count or
the names store's window count differs from what the store was built against.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend import entity_index as ei  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--entities-json')
    ap.add_argument('--passage-dir', default=os.path.join(ROOT, 'data', 'passage_index'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'entity_index', 'entities.sqlite'))
    ap.add_argument('--review-csv')
    ap.add_argument('--no-stoplist', action='store_true')
    ap.add_argument('--matcher', choices=('stem', 'lemma'), default='stem',
                    help='stem: name stems plus case endings (default). lemma: lemmas of the names.')
    ap.add_argument('--no-audit-fixes', action='store_true',
                    help='lemma matcher only: skip the stage 1c drops and overrides (the stage 1b table).')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        problems = ei.check_lockstep(a.out, a.passage_dir)
        if problems:
            print('ENTITY STORE OUT OF STEP:')
            for p in problems:
                print(' ', p)
            print('  rebuild: scripts/build_entity_index.py (after build_window_names.py)')
            return 1
        print('entity store in step with the passage index')
        return 0
    if not a.entities_json:
        ap.error('--entities-json is required for a build')
    keys = json.load(open(a.entities_json, encoding='utf-8'))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    counts, _rows, _ents = ei.build_store(keys, a.passage_dir, a.out, review_csv=a.review_csv,
                                          apply_stoplist=not a.no_stoplist, matcher=a.matcher,
                                          lemma_fixes=not a.no_audit_fixes)
    print('entities by type', counts['entities_list_by_type'], 'names', counts['name_entities'])
    print('mentions by language', counts['list_mentions_by_language'])
    print('windows covered', counts['windows_with_mentions'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
