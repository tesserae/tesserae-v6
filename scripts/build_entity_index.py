"""Rebuild the entity mention store from scratch and print its counts.

    venv/bin/python scripts/build_entity_index.py --entities-json KEYS.json \
        [--passage-dir data/passage_index] [--out data/entity_index/entities.sqlite] \
        [--review-csv merge_review.csv] [--no-stoplist] [--matcher stem|lemma] [--no-audit-fixes]
    venv/bin/python scripts/build_entity_index.py --lines [--out STORE] [--passage-dir DIR]
    venv/bin/python scripts/build_entity_index.py --documents [--out STORE] [--documents-dir DIR]
    venv/bin/python scripts/build_entity_index.py --catalog [--out STORE]
    venv/bin/python scripts/build_entity_index.py --check [--documents-dir DIR]
    venv/bin/python scripts/build_entity_index.py --works STEMS.txt --store LIVE_STORE --out NEW_STORE \
        --entities-json KEYS.json [--decisions FILE]... [--token-blocks FILE] [--report report.json] [--cache FILE]

KEYS.json is the proper-name list as entity rows (id, greek, latin, english, type, pleiades),
the join of backend/proper_names to the Pleiades gazetteer. Run it after any passage-index
change, in the same chain as build_window_names.py, build_desc_fts.py and
build_desc_vocab.py. Build to a new file, then swap in. Under 6 GB; run it inside
`tess-job --fg NAME 6`. --check reports the store as stale when the counted-window count or
the names store's window count differs from what the store was built against, or when the
stage 2b tables are missing. --catalog (the search catalog stored as a table, run last) and --lines (about the line of each mention, so overlapping windows that
hold one line count once) and --documents (the inscriptions and papyri that name each entity)
add their tables to the store given by --out in place; run them after a build, on a copy, then
swap in. --documents reads the production documents index read-only. Under 4 GB.
--works adds the mention rows of works added after the store was built (STEMS.txt: one work stem a line,
such as plotinus.enneades, which covers its .part.N windows) to a COPY of the store, --store, written to
--out. Existing rows are never rebuilt, so the hand passes stay (see backend/entity_new_works.py). Under
6 GB; run it inside `tess-job --fg NAME 6`. Refuses an --out under /var/www.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend import entity_index as ei  # noqa: E402


def run_works(a):
    import pickle
    from backend import entity_new_works as nw
    if not (a.store and a.entities_json and a.out):
        print('--works needs --store, --entities-json and --out', file=sys.stderr)
        return 2
    if os.path.realpath(a.out).startswith('/var/www'):
        print('refusing: --out must be outside /var/www', file=sys.stderr)
        return 2
    stems = [s.strip() for s in open(a.works, encoding='utf-8') if s.strip() and not s.startswith('#')]
    if a.cache and os.path.exists(a.cache):
        cands = pickle.load(open(a.cache, 'rb'))
        print('candidates read from', a.cache)
    else:
        keys = json.load(open(a.entities_json, encoding='utf-8'))
        cands = nw.scan_new_works(keys, a.passage_dir, stems, a.decisions, a.token_blocks)
        if a.cache:
            pickle.dump(cands, open(a.cache, 'wb'), protocol=4)
    filed = nw.file_candidates(cands, a.store, a.passage_dir, stems)
    now = ei.fingerprint(os.path.join(a.passage_dir, 'ids.json'), os.path.join(a.passage_dir, 'window_names.db'))
    stats = nw.add_works(a.store, a.out, filed, filed['wmeta'], a.passage_dir, now, a.report)
    stats.update({k: filed[k] for k in ('abbreviations', 'abbreviation_rows_dropped', 'own_entity_rows',
                                        'list_counts', 'name_counts', 'skipped_built_works')})
    if a.report:
        json.dump(stats, open(a.report, 'w'), ensure_ascii=False, indent=1, default=list)
    print(json.dumps({k: v for k, v in stats.items() if k not in ('new_entities', 'abbreviations',
                                                                   'abbreviation_rows_dropped')}, indent=1, default=str))
    print('works skipped because the store already holds them', filed['skipped_built_works'])
    print('new entities', len(stats['new_entities']), 'list', filed['list_counts'], 'names', filed['name_counts'])
    return 0


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
    ap.add_argument('--works', help='file with one work stem a line: add the mentions of these works to a copy of --store')
    ap.add_argument('--store', help='--works: the store to copy (read only)')
    ap.add_argument('--decisions', action='append', default=[],
                    help='--works: lemma judgment files of the model passes (repeat; the last answer for a pair wins)')
    ap.add_argument('--token-blocks', default=None, help='--works: token_blocks.json of fix pass 4b')
    ap.add_argument('--report', default=None, help='--works: write the report here as JSON')
    ap.add_argument('--cache', default=None, help='--works: pickle of the candidates, reused when it exists')
    ap.add_argument('--lines', action='store_true')
    ap.add_argument('--documents', action='store_true')
    ap.add_argument('--catalog', action='store_true')
    ap.add_argument('--max-form-documents', type=int, default=0,
                    help='--documents: drop forms found in more documents than this (default 0: keep all)')
    ap.add_argument('--formula-dir', default=None,
                    help='--documents: folder with formula_words_la.txt and formula_words_grc.txt '
                         '(default: data/documents)')
    ap.add_argument('--common-forms-json', default=None,
                    help='--documents: cache of the forms that are mostly lower case in the literary '
                         'corpus (built from the passage index when absent; takes minutes)')
    ap.add_argument('--documents-dir', default=None,
                    help='folder with la_documents_index.db and grc_documents_index.db '
                         '(default: data/inverted_index)')
    a = ap.parse_args()
    docs_dir = a.documents_dir or os.path.join(ROOT, 'data', 'inverted_index')
    if a.lines or a.documents or a.catalog:
        import time
        import resource
        from backend import entity_extras as ex
        t0 = time.time()
        if a.lines:
            stats = ex.add_line_refs(a.out, os.path.join(a.passage_dir, 'window_texts.db'))
            print('line refs', stats)
        if a.documents:
            formulas = ex.formula_forms(a.formula_dir or os.path.join(ROOT, 'data', 'documents'))
            common = ex.common_forms(a.passage_dir, cache_path=a.common_forms_json)
            excluded = {lg: formulas[lg] | common[lg] for lg in ('la', 'grc')}
            print('excluded forms: formulas', {k: len(v) for k, v in formulas.items()},
                  'mostly lower case', {k: len(v) for k, v in common.items()})
            stats = ex.build_document_mentions(a.out, docs_dir, max_form_documents=a.max_form_documents,
                                               excluded_forms=excluded)
            print(json.dumps(stats, indent=1))
        if a.catalog:
            print('catalog entities', ex.write_catalog(a.out))
        print(f'seconds {time.time() - t0:.0f}, peak {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6:.2f} GB')
        return 0
    if a.works:
        return run_works(a)
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
