"""Rebuild the entity mention store from scratch and print its counts.

    venv/bin/python scripts/build_entity_index.py --entities-json KEYS.json \
        [--passage-dir data/passage_index] [--out data/entity_index/entities.sqlite] \
        [--review-csv merge_review.csv] [--no-stoplist] [--matcher stem|lemma] [--no-audit-fixes]
    venv/bin/python scripts/build_entity_index.py --lines [--out STORE] [--passage-dir DIR]
    venv/bin/python scripts/build_entity_index.py --documents [--out STORE] [--documents-dir DIR]
    venv/bin/python scripts/build_entity_index.py --check [--documents-dir DIR]

KEYS.json is the proper-name list as entity rows (id, greek, latin, english, type, pleiades),
the join of backend/proper_names to the Pleiades gazetteer. Run it after any passage-index
change, in the same chain as build_window_names.py, build_desc_fts.py and
build_desc_vocab.py. Build to a new file, then swap in. Under 6 GB; run it inside
`tess-job --fg NAME 6`. --check reports the store as stale when the counted-window count or
the names store's window count differs from what the store was built against, or when the
stage 2b tables are missing. --lines (about the line of each mention, so overlapping windows that
hold one line count once) and --documents (the inscriptions and papyri that name each entity)
add their tables to the store given by --out in place; run them after a build, on a copy, then
swap in. --documents reads the production documents index read-only. Under 4 GB.
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
    ap.add_argument('--lines', action='store_true')
    ap.add_argument('--documents', action='store_true')
    ap.add_argument('--max-form-documents', type=int, default=0,
                    help='--documents: drop forms found in more documents than this (default 0: keep all)')
    ap.add_argument('--documents-dir', default=None,
                    help='folder with la_documents_index.db and grc_documents_index.db '
                         '(default: data/inverted_index)')
    a = ap.parse_args()
    docs_dir = a.documents_dir or os.path.join(ROOT, 'data', 'inverted_index')
    if a.lines or a.documents:
        import time
        import resource
        from backend import entity_extras as ex
        t0 = time.time()
        if a.lines:
            stats = ex.add_line_refs(a.out, os.path.join(a.passage_dir, 'window_texts.db'))
            print('line refs', stats)
        if a.documents:
            stats = ex.build_document_mentions(a.out, docs_dir, max_form_documents=a.max_form_documents)
            print(json.dumps(stats, indent=1))
        print(f'seconds {time.time() - t0:.0f}, peak {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6:.2f} GB')
        return 0
    if a.check:
        from backend import entity_extras as ex
        problems = ei.check_lockstep(a.out, a.passage_dir) + (ex.extras_problems(a.out, docs_dir) if os.path.exists(a.out) else [])
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
