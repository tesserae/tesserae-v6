#!/usr/bin/env python3
"""Add the Attic Inscriptions Online documents to the document_mentions table of a COPY of the People
& Places store, with the Attic rules of backend/attic_mentions.py. Added rows only: every row the table
already holds stays byte for byte, and the new rows carry document ids that start with 'aio:'. The
table is never rebuilt (a rebuild drops the rows of promoted entities and adds rows nobody reviewed).

    venv/bin/python scripts/entities/add_aio_mentions.py --store LIVE_STORE_COPY_SOURCE \
        --documents-dir DIR_WITH_grc_documents_index.db --out NEW_STORE \
        [--report report.json] [--sample-out sample.csv --sample-size 100 --seed 20]

--store is read only; --out is a copy of it that receives the rows. Refuses an --out under /var/www and
an --out that equals --store. Under 3 GB; run it inside `tess-job --fg NAME 4`.

The report lists, for each rule, the rows before and after it (rows are one per entity and document, as
in the table), the rows the demotic, god and Athens tables add, the archon names left unlinked and the
final rows, documents and entities.
"""
import argparse
import collections
import csv
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from backend import attic_mentions as am  # noqa: E402
from backend import entity_extras as ex  # noqa: E402


def table_digest(db, upto_rowid):
    h = hashlib.sha256()
    for r in db.execute('select eid, doc_id, language, form, kind, adjective from document_mentions '
                        'where rowid <= ? order by rowid', (upto_rowid,)):
        h.update(repr(r).encode())
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--store', required=True)
    ap.add_argument('--documents-dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--prefix', default='aio:')
    ap.add_argument('--formula-dir', default=None)
    ap.add_argument('--common-forms-json', required=True)
    ap.add_argument('--report', default=None)
    ap.add_argument('--sample-out', default=None)
    ap.add_argument('--sample-size', type=int, default=100)
    ap.add_argument('--seed', type=int, default=20)
    a = ap.parse_args(argv)
    if os.path.realpath(a.out).startswith('/var/www') or os.path.realpath(a.out) == os.path.realpath(a.store):
        print('refusing: --out must be a new file outside /var/www', file=sys.stderr)
        return 2
    shutil.copyfile(a.store, a.out)
    db = sqlite3.connect(a.out)
    old_max = db.execute('select coalesce(max(rowid), 0) from document_mentions').fetchone()[0]
    old_digest = table_digest(db, old_max)
    if db.execute('select count(*) from document_mentions where doc_id like ?', (a.prefix + '%',)).fetchone()[0]:
        print('refusing: the table already holds rows for', a.prefix, file=sys.stderr)
        return 2

    formulas = ex.formula_forms(a.formula_dir or os.path.join(ROOT, 'data', 'documents'))
    common = ex.common_forms(None, cache_path=a.common_forms_json)
    excluded = {lg: formulas[lg] | common[lg] for lg in ('la', 'grc')}
    candidates = []
    ex.build_document_mentions(a.out, a.documents_dir, log=print, excluded_forms=excluded,
                               doc_prefix=a.prefix, rows_out=candidates)
    cand_pairs = {(r[1], r[0]) for r in candidates}

    ents = ex._load_entities(db)
    exact, stems, _n = ex.build_maps(ents, log=print)
    labels = {r[0]: r[1] for r in db.execute('select eid, description from entity_labels')}
    matcher = am.AtticMatcher(ents, exact, stems, labels, skip=excluded['grc'])

    src = sqlite3.connect(f"file:{os.path.join(a.documents_dir, 'grc_documents_index.db')}?mode=ro&immutable=1", uri=True)
    docs = src.execute("select ref, content from lines where ref like ? escape '\\' order by ref",
                       (a.prefix.replace('_', '\\_').replace('%', '\\%') + '%',)).fetchall()
    src.close()

    per_doc = {}           # doc -> {eid: [drop indexes]}  (builder candidates)
    added_per_doc = {}     # doc -> {eid: [drop indexes]}  (rows the tables add)
    kept_rows = []
    word_of = {}
    archon_unlinked = 0
    archon_by_doc = collections.Counter()
    unresolved = 0
    for doc, content in docs:
        occ, unl = matcher.read_document(content)
        archon_unlinked += unl
        if unl:
            archon_by_doc[doc] = unl
        unresolved += sum(1 for o in occ if o[5] == 'athena_or_athens')
        kept, drops = am.aggregate(occ)
        base = {}
        added = {}
        for eid, kind, adj, f, i, why, is_added in occ:
            (added if is_added else base).setdefault(eid, []).append(am.RULES.index(why) if why else len(am.RULES))
        per_doc[doc], added_per_doc[doc] = base, added
        for eid, row in kept.items():
            kept_rows.append((row[0], doc, 'grc', row[1], row[2], row[3]))
            word_of[(doc, eid)] = row[4]

    # the builder's candidate set and ours must be the same set (same matches, before any rule)
    mine = {(d, e) for d, m in per_doc.items() for e in m}
    same = mine == cand_pairs
    only_builder = sorted(cand_pairs - mine)
    only_scan = sorted(mine - cand_pairs)
    stage = []
    total = len(mine)
    left = total
    for k, rule in enumerate(am.RULES):
        after = sum(1 for d, m in per_doc.items() for e, v in m.items() if max(v) > k)
        # rows lost to this rule and not to an earlier one
        stage.append({'rule': rule, 'rows_before': left, 'rows_after': after, 'dropped': left - after})
        left = after
    added_stage = collections.Counter()
    added_final = collections.Counter()
    for d, m in added_per_doc.items():
        for e, v in m.items():
            if max(v) == len(am.RULES):
                ent = ents[e]
                added_final[(ent['source'], ent['type'])] += 1
            added_stage['added_candidates'] += 1
    final = len(kept_rows)
    report = {'documents': len(docs), 'builder_candidate_rows': len(candidates),
              'builder_candidate_entities': len({r[0] for r in candidates}),
              'occurrence_scan_equals_builder': same, 'candidates_only_in_builder': len(only_builder),
              'candidates_only_in_scan': len(only_scan),
              'examples_only_in_builder': [[d, ents[e]['id']] for d, e in only_builder[:5]],
              'examples_only_in_scan': [[d, ents[e]['id']] for d, e in only_scan[:5]], 'rules': stage,
              'rows_from_builder_after_rules': left, 'rows_added_by_tables_final': sum(added_final.values()),
              'archon_names_left_unlinked': archon_unlinked, 'archon_documents': len(archon_by_doc),
              'athenai_athenas_without_accent_left_unlinked': unresolved,
              'final_rows': final, 'final_documents': len({r[1] for r in kept_rows}),
              'final_entities': len({r[0] for r in kept_rows}),
              'final_rows_by_type': dict(collections.Counter(f"{ents[r[0]]['source']}/{ents[r[0]]['type']}" for r in kept_rows))}

    db.executemany('insert into document_mentions values (?,?,?,?,?,?)', kept_rows)
    meta = dict(db.execute('select key, value from meta'))
    dm = json.loads(meta.get('document_mentions', '{}'))
    dm['aio_rows_added'] = final
    dm['rows'] = db.execute('select count(*) from document_mentions').fetchone()[0]
    dm['entities_with_documents'] = db.execute('select count(distinct eid) from document_mentions').fetchone()[0]
    db.execute("delete from meta where key in ('document_mentions', 'documents_fingerprint', 'aio_mentions')")
    db.execute("insert into meta values ('document_mentions', ?)", (json.dumps(dm),))
    db.execute("insert into meta values ('documents_fingerprint', ?)", (ex.documents_fingerprint(a.documents_dir),))
    db.execute("insert into meta values ('aio_mentions', ?)", (json.dumps(report),))
    db.commit()
    check = table_digest(db, old_max)
    report['existing_rows'] = old_max
    report['existing_rows_unchanged'] = (check == old_digest)
    new_total = db.execute('select count(*) from document_mentions').fetchone()[0]
    report['rows_after'] = new_total
    report['rows_added'] = new_total - old_max
    report['integrity'] = db.execute('pragma integrity_check').fetchone()[0]

    if a.sample_out:
        rnd = random.Random(a.seed)
        pick = rnd.sample(sorted(kept_rows, key=lambda r: (r[1], r[0])), min(a.sample_size, len(kept_rows)))
        content_of = dict(docs)
        wcache = {}
        labels_grc = {r[0]: r[1] for r in db.execute('select eid, display_label_grc from entity_labels')}
        os.makedirs(os.path.dirname(os.path.abspath(a.sample_out)), exist_ok=True)
        with open(a.sample_out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['n', 'doc_id', 'entity_id', 'entity_label', 'entity_type', 'entity_source', 'greek_label',
                        'entity_description', 'form', 'kind', 'text_around_the_word', 'delegate_grade', 'delegate_note',
                        'lead_grade', 'lead_note'])
            for n, r in enumerate(pick, 1):
                eid, doc, _lang, form, kind, _adj = r
                ws = wcache.setdefault(doc, am.words(content_of[doc]))
                idx = word_of.get((doc, eid), 0)
                lo, hi = max(0, idx - 9), min(len(ws), idx + 10)
                ctx = ' '.join(('[[' + x[0] + ']]' if j == idx else x[0]) for j, x in enumerate(ws[lo:hi], lo))
                e = ents[eid]
                w.writerow([n, doc, e['id'], e['label'], e['type'], e['source'], labels_grc.get(eid) or '',
                            labels.get(eid) or '', form, kind, ctx, '', '', '', ''])
    db.close()
    out = json.dumps(report, indent=1, ensure_ascii=False)
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            f.write(out)
    print(out)
    return 0 if report['existing_rows_unchanged'] and report['integrity'] == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())
