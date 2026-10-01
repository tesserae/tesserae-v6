#!/usr/bin/env python3
"""Take a text out of the server once its licence ends.

data/restricted_texts.json names texts held under an indexing-and-search-only
licence (the first from the Packard Humanities Institute). The licence may be
ended in writing, after which the text must come out of the index and its
copies must be deleted -- not just untracked, actually removed from the
server's disk. This script is that removal, in one place rather than five
manual steps someone has to remember in order:

    1. the work's .tess files under texts/<lang>/ (whole file and book parts)
    2. its lemma cache files under cache/lemmas/<lang>/
    3. its rows in each language's inverted index (data/inverted_index/)
    4. its windows in the passage index (data/passage_index/)
    5. its entry in data/restricted_texts.json

Dry run by default, like every script under scripts/corpus/ that writes to
data/ (the convention in docs/DATA_OPERATIONS.md, implemented in
corpus_safety.py). PLANNING is separated from APPLYING on purpose: `plan_removal`
only reads, so it can run against a toy fixture in a test with no risk, and
is what `--apply` then acts on. The index and passage-index removal reuse the
same approach as drop_stale_index_entries.py and drop_whole_file_windows.py:
copy, modify the copy, verify, then swap by rename, with a dated backup kept
of whatever the swap replaced.

    venv/bin/python scripts/corpus/remove_restricted_text.py heldwork.history
    venv/bin/python scripts/corpus/remove_restricted_text.py heldwork.history --apply --root /var/www/tesseraev6_flask

THIS HAS NEVER BEEN RUN AGAINST REAL DATA. No text has actually been removed
under a licence yet; this script was written and tested against fixtures
only, ahead of ever needing it.
"""
import argparse
import glob
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from backend.work_names import base_work  # noqa: E402
from scripts.corpus.corpus_safety import add_apply_argument, backup, atomic_write  # noqa: E402

LANGUAGES = ['la', 'grc', 'en', 'cop', 'he', 'it', 'gmh', 'fro']


# ---------------------------------------------------------------------------
# PLANNING -- read-only, safe against a fixture or the real server alike.
# ---------------------------------------------------------------------------
def load_registry(root):
    path = os.path.join(root, 'data', 'restricted_texts.json')
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f).get('texts', {}), path
    except (OSError, ValueError):
        return {}, path


def find_text_files(text_id, root):
    """Every (language, filename) under texts/<lang>/ belonging to this
    work: the whole file, if any, and every book part."""
    found = []
    for lang in LANGUAGES:
        lang_dir = os.path.join(root, 'texts', lang)
        if not os.path.isdir(lang_dir):
            continue
        for fn in sorted(os.listdir(lang_dir)):
            if fn.endswith('.tess') and base_work(fn[:-len('.tess')]) == text_id:
                found.append((lang, fn))
    return found


def find_lemma_cache_files(text_id, root):
    """Every cache/lemmas/<lang>/<...>.json belonging to this work."""
    found = []
    for lang in LANGUAGES:
        lang_dir = os.path.join(root, 'cache', 'lemmas', lang)
        if not os.path.isdir(lang_dir):
            continue
        for fn in sorted(os.listdir(lang_dir)):
            if fn.endswith('.json') and base_work(fn[:-len('.json')]) == text_id:
                found.append((lang, fn))
    return found


def plan_index_rows(text_id, root, text_files):
    """How many rows of each language's inverted index belong to this work,
    keyed by the db's own text_id (not necessarily this script's text_id: the
    db may key rows by filename). {} entries mean "index not present on this
    checkout" -- true of every dev checkout, since the index is not in git.
    """
    languages = sorted({lang for lang, _ in text_files}) or LANGUAGES
    plan = {}
    for lang in languages:
        db_path = os.path.join(root, 'data', 'inverted_index', f'{lang}_index.db')
        if not os.path.exists(db_path):
            plan[lang] = {'db_path': db_path, 'present': False}
            continue
        con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        try:
            rows = con.execute('select text_id, filename, line_count from texts').fetchall()
        finally:
            con.close()
        matches = [(t, f, n) for t, f, n in rows
                   if f.endswith('.tess') and base_work(f[:-len('.tess')]) == text_id]
        plan[lang] = {'db_path': db_path, 'present': True,
                      'matching_text_ids': [t for t, _, _ in matches],
                      'line_count': sum(n for _, _, n in matches)}
    return plan


def plan_passage_windows(text_id, root):
    """How many passage-index windows belong to this work. None of the three
    files means "passage index not present on this checkout" (true of every
    dev checkout, since it is not in git)."""
    index_dir = os.path.join(root, 'data', 'passage_index')
    ids_path = os.path.join(index_dir, 'ids.json')
    desc_path = os.path.join(index_dir, 'descriptions.jsonl')
    if not os.path.exists(ids_path) or not os.path.exists(desc_path):
        return {'present': False, 'index_dir': index_dir}
    ids = json.load(open(ids_path, encoding='utf-8'))
    works = {}
    with open(desc_path, encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('id'):
                works[r['id']] = r.get('work')
    matching_rows = [n for n, wid in enumerate(ids)
                     if base_work(works.get(wid) or wid.split(':', 1)[0]) == text_id]
    return {'present': True, 'index_dir': index_dir, 'window_count': len(matching_rows),
            'rows': matching_rows}


def plan_removal(text_id, root='.'):
    """Everything removing `text_id` would touch. Read-only."""
    registry, registry_path = load_registry(root)
    text_files = find_text_files(text_id, root)
    return {
        'text_id': text_id,
        'root': root,
        'registry_entry': registry.get(text_id),
        'registry_path': registry_path,
        'text_files': text_files,
        'lemma_cache_files': find_lemma_cache_files(text_id, root),
        'index': plan_index_rows(text_id, root, text_files),
        'passage_windows': plan_passage_windows(text_id, root),
    }


def format_plan(plan):
    lines = [f"Removal plan for '{plan['text_id']}' (root: {plan['root']})", '']
    if not plan['registry_entry']:
        lines.append(f"  WARNING: not in the registry ({plan['registry_path']}). "
                      "Removing it anyway only touches files/index rows; nothing "
                      "will un-restrict it, because it was never restricted.")
    else:
        lines.append(f"  registry: holder={plan['registry_entry'].get('holder')!r}, "
                      f"added={plan['registry_entry'].get('added')}")
    lines.append(f"  text files ({len(plan['text_files'])}):")
    for lang, fn in plan['text_files']:
        lines.append(f"    texts/{lang}/{fn}")
    lines.append(f"  lemma cache files ({len(plan['lemma_cache_files'])}):")
    for lang, fn in plan['lemma_cache_files']:
        lines.append(f"    cache/lemmas/{lang}/{fn}")
    lines.append('  inverted index:')
    for lang, info in plan['index'].items():
        if not info.get('present'):
            lines.append(f"    {lang}: index not present on this checkout ({info['db_path']})")
        else:
            lines.append(f"    {lang}: {info['line_count']} line(s) across "
                          f"{len(info['matching_text_ids'])} db text_id(s)")
    pw = plan['passage_windows']
    if not pw.get('present'):
        lines.append(f"  passage index: not present on this checkout ({pw['index_dir']})")
    else:
        lines.append(f"  passage index: {pw['window_count']} window(s)")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# APPLYING -- writes, only with --apply. Never run against real data by this
# script's own tests; see tests/test_remove_restricted_text.py for what IS
# tested (plan_removal, on a fixture).
# ---------------------------------------------------------------------------
def apply_removal(plan, tag=None):
    tag = tag or time.strftime('removed-%Y%m%d')
    root = plan['root']
    report = []

    for lang, fn in plan['text_files']:
        path = os.path.join(root, 'texts', lang, fn)
        b = backup(path, tag=tag)
        os.remove(path)
        report.append(f"removed texts/{lang}/{fn} (backup: {b})")

    for lang, fn in plan['lemma_cache_files']:
        path = os.path.join(root, 'cache', 'lemmas', lang, fn)
        b = backup(path, tag=tag)
        os.remove(path)
        report.append(f"removed cache/lemmas/{lang}/{fn} (backup: {b})")

    for lang, info in plan['index'].items():
        if not info.get('present') or not info.get('matching_text_ids'):
            continue
        db_path = info['db_path']
        ids = info['matching_text_ids']
        marks = ','.join('?' * len(ids))
        new_path = db_path + '.new'
        import shutil
        shutil.copy2(db_path, new_path)
        con = sqlite3.connect(new_path)
        con.execute(f'delete from lines where text_id in ({marks})', ids)
        con.execute(f'delete from postings where text_id in ({marks})', ids)
        con.execute(f'delete from texts where text_id in ({marks})', ids)
        con.commit()
        assert con.execute('pragma integrity_check').fetchone()[0] == 'ok'
        con.execute('VACUUM')
        con.close()
        b = backup(db_path, tag=tag)
        os.replace(new_path, db_path)
        report.append(f"{lang}_index.db: removed {len(ids)} text_id(s), "
                      f"{info['line_count']} line(s) (backup: {b})")

    pw = plan['passage_windows']
    if pw.get('present') and pw.get('window_count'):
        index_dir = pw['index_dir']
        drop = set(pw['rows'])
        ids = json.load(open(os.path.join(index_dir, 'ids.json'), encoding='utf-8'))
        kept_ids = [i for n, i in enumerate(ids) if n not in drop]
        backup(os.path.join(index_dir, 'ids.json'), tag=tag)
        atomic_write(os.path.join(index_dir, 'ids.json'),
                     json.dumps(kept_ids, ensure_ascii=False))

        desc_path = os.path.join(index_dir, 'descriptions.jsonl')
        backup(desc_path, tag=tag)
        kept_set = set(kept_ids)
        new_lines = []
        with open(desc_path, encoding='utf-8') as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get('id') in kept_set:
                    new_lines.append(line if line.endswith('\n') else line + '\n')
        atomic_write(desc_path, new_lines)

        emb_path = os.path.join(index_dir, 'embeddings.npy')
        if os.path.exists(emb_path):
            import numpy as np
            emb = np.load(emb_path)
            keep_rows = [n for n in range(len(ids)) if n not in drop]
            backup(emb_path, tag=tag)
            np.save(emb_path, emb[keep_rows])
        report.append(f"passage index: removed {pw['window_count']} window(s)")

    registry, registry_path = load_registry(root)
    if plan['text_id'] in registry:
        backup(registry_path, tag=tag)
        del registry[plan['text_id']]
        atomic_write(registry_path, json.dumps({'_comment': (
            'Texts licensed for indexing and search only, never for '
            'redistribution. See backend/restricted_texts.py.'),
            'texts': registry}, indent=2, ensure_ascii=False) + '\n')
        report.append(f"removed '{plan['text_id']}' from {registry_path}")

    return report


def data_operations_lines(plan, report):
    """What to paste into docs/DATA_OPERATIONS.md for this removal."""
    date = time.strftime('%Y-%m-%d')
    return (
        f"- {date}: removed restricted text '{plan['text_id']}' "
        f"({len(plan['text_files'])} file(s)) from texts/, the lemma cache, "
        "the inverted index, and the passage index, and dropped its entry "
        "from data/restricted_texts.json, following the licence's end. "
        f"Backups kept beside each file replaced.\n"
        + '\n'.join(f"  - {line}" for line in report)
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('text_id', help='Registry id to remove, e.g. heldwork.history')
    ap.add_argument('--root', default='.', help='Repository/server root (default: .)')
    add_apply_argument(ap)
    args = ap.parse_args()

    plan = plan_removal(args.text_id, args.root)
    print(format_plan(plan))

    if not args.apply:
        print('\nDry run. Pass --apply to actually remove these.')
        return

    report = apply_removal(plan)
    print('\nApplied:')
    for line in report:
        print(f'  {line}')
    print('\nRecord this in docs/DATA_OPERATIONS.md:\n')
    print(data_operations_lines(plan, report))
    print('\nThen regenerate .gitignore\'s restricted-texts block:')
    print('  venv/bin/python scripts/corpus/restricted_texts_gitignore.py')


if __name__ == '__main__':
    main()
