#!/usr/bin/env python3
"""Rename a work across every store its name lives in OUTSIDE git.

A work's id (``<author>.<work>``, from its ``.tess`` filename) is repeated
in five places that are not tracked in the repository and so are not fixed
by a pull request alone:

  1. ``texts/<lang>/<old>.tess`` itself, and the line tag at the start of
     every line in it (``<old.N>`` -> ``<new.N>``).
  2. the inverted index, ``data/inverted_index/<lang>_index.db``: the
     ``texts`` row's ``filename``/``author``/``title``, and the ``ref``
     column of every ``lines`` and ``postings`` row for that text.
  3. the lemma cache, ``cache/lemmas/<lang>/``: the legacy plain-named file
     and/or the ASCII-safe hashed-named file (``backend/lemma_cache.
     get_cache_path``), whose ``text_id`` and per-unit ``ref`` fields name
     the work, and whose ``file_hash`` is the MD5 of the ``.tess`` file's
     bytes -- which changes the moment the line tags are rewritten, so a
     moved cache is re-stamped with the NEW file's hash or it is silently
     never read again.
  4. the passage index, ``data/passage_index/`` (window ids, descriptions,
     ``window_texts.db``) -- delegated to ``rename_work_in_passage_index.py``,
     which already does exactly this and is reused here rather than
     reimplemented.
  5. precomputed semantic-search vectors, ``backend/embeddings/<lang>/
     <old>.npy`` and ``.meta.json`` (``text_path``, ``line_refs``).

Tracked files (``backend/author_dates.json``, ``data/text_descriptions.json``,
etc.) are NOT touched here -- those are edited by hand in the pull request
that proposes a rename, where a human reads what else the note beside the
old id was saying. This script is the production step that runs after that
pull request merges.

Dry run by default, like every script under this convention
(``scripts/corpus/corpus_safety.py``): a plan is always printed; ``--apply``
is required to write anything. Every file this script modifies in place, or
moves, is backed up first as ``<name>.bak-rename-<timestamp>`` (collision-safe:
a second run in the same second gets ``-1``, ``-2``, ...). A store with
nothing under the old name, or missing entirely (e.g. no embeddings built
yet for a text), is reported and skipped -- not an error.

Line tags do not always equal the work id (some corpora cite a work by an
abbreviation inside the ``.tess`` file that differs from its filename); pass
``--old-tag``/``--new-tag`` when the literal ``<tag.N>`` prefix in the
``.tess`` file is not ``--old``/``--new`` themselves. The embeddings'
``line_refs`` are the SAME literal citation strings captured off the
``.tess`` file at the time its vectors were computed, so this script rewrites
only the entries that start with ``<old-tag>.`` -- if none do (a text whose
vectors were computed against still another citation form), that is reported
as zero rewritten, not guessed at.

REFUSES outright, before writing anything to ANY store, if the new id
already exists anywhere it would collide (an existing ``.tess``, index row,
cache file, embeddings file, or passage-index id already under the new
name) -- renaming onto an occupied name would merge two different works
under one id silently.

    ./venv/bin/python3 scripts/corpus/rename_work.py \\
        --root . --language fa --old iqbal_lahori.diwan --new iqbal.diwan
    ... --apply
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, ROOT)

from scripts.corpus.corpus_safety import (  # noqa: E402
    add_apply_argument, backup, atomic_write, read_text_preserving_eol,
)
import scripts.corpus.rename_work_in_passage_index as passage_rename  # noqa: E402
from backend.lemma_cache import get_cache_path  # noqa: E402


def split_id(work_id):
    """('iqbal_lahori.diwan') -> ('iqbal_lahori', 'diwan'); the second
    element is '' for an id with no dot."""
    author, _, rest = work_id.partition('.')
    return author, rest


def _rewrite_prefix(value, old, new):
    """'<old>.foo' -> '<new>.foo'; anything else (or a non-string) is
    returned unchanged. Same convention as rename_work_in_passage_index's
    renamed(): matching on old + '.' is what keeps a longer name that
    happens to start with old from being mangled."""
    if not isinstance(value, str):
        return value
    prefix = old + '.'
    if value.startswith(prefix):
        return new + '.' + value[len(prefix):]
    return value


# --------------------------------------------------------------- .tess -----

def tess_path(root, language, work_id):
    return os.path.join(root, 'texts', language, f'{work_id}.tess')


def plan_tess(root, language, old, old_tag):
    path = tess_path(root, language, old)
    if not os.path.exists(path):
        return {'found': False}
    content = read_text_preserving_eol(path)
    pattern = re.compile(r'^<' + re.escape(old_tag) + r'\.', re.MULTILINE)
    n_tagged = len(pattern.findall(content))
    n_lines = len(content.splitlines())
    return {'found': True, 'path': path, 'tagged_lines': n_tagged, 'total_lines': n_lines}


def apply_tess(root, language, old, new, old_tag, new_tag):
    old_path = tess_path(root, language, old)
    new_path = tess_path(root, language, new)
    if not os.path.exists(old_path):
        return {'found': False}
    if os.path.exists(new_path):
        raise RuntimeError(f'refusing: {new_path} already exists')
    content = read_text_preserving_eol(old_path)
    pattern = re.compile(r'^<' + re.escape(old_tag) + r'\.', re.MULTILINE)
    new_content, n = pattern.subn(f'<{new_tag}.', content)
    backup_path = backup(old_path, tag='rename')
    atomic_write(new_path, new_content)
    os.remove(old_path)
    return {'found': True, 'rewritten_lines': n, 'backup': backup_path,
            'old_path': old_path, 'new_path': new_path}


# ---------------------------------------------------------- inverted index -

def index_db_path(root, language):
    return os.path.join(root, 'data', 'inverted_index', f'{language}_index.db')


def plan_index(root, language, old, new):
    db = index_db_path(root, language)
    if not os.path.exists(db):
        return {'found': False}
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    try:
        row = con.execute('SELECT text_id FROM texts WHERE filename=?',
                           (f'{old}.tess',)).fetchone()
        if row is None:
            return {'found': True, 'db': db, 'text_present': False}
        text_id = row[0]
        n_lines, = con.execute('SELECT COUNT(*) FROM lines WHERE text_id=?',
                                (text_id,)).fetchone()
        n_postings, = con.execute('SELECT COUNT(*) FROM postings WHERE text_id=?',
                                   (text_id,)).fetchone()
        new_exists = con.execute('SELECT 1 FROM texts WHERE filename=?',
                                  (f'{new}.tess',)).fetchone() is not None
        return {'found': True, 'db': db, 'text_present': True, 'text_id': text_id,
                'lines': n_lines, 'postings': n_postings,
                'new_filename_exists': new_exists}
    finally:
        con.close()


def apply_index(root, language, old, new):
    plan = plan_index(root, language, old, new)
    if not plan.get('found') or not plan.get('text_present'):
        return plan
    if plan['new_filename_exists']:
        raise RuntimeError(f'refusing: {new}.tess already present in {plan["db"]}')
    db = plan['db']
    text_id = plan['text_id']
    new_author, new_rest = split_id(new)
    new_title = new_rest or new_author
    cut = len(old) + 1
    tmp = f'{db}.tmp-rename-{os.getpid()}'
    shutil.copy2(db, tmp)
    con = sqlite3.connect(tmp)
    try:
        con.execute('UPDATE texts SET filename=?, author=?, title=? WHERE text_id=?',
                    (f'{new}.tess', new_author, new_title, text_id))
        con.execute('UPDATE lines SET ref = ? || substr(ref, ?) WHERE text_id=?',
                    (new + '.', cut + 1, text_id))
        con.execute('UPDATE postings SET ref = ? || substr(ref, ?) WHERE text_id=?',
                    (new + '.', cut + 1, text_id))
        con.commit()
        n_lines_after, = con.execute('SELECT COUNT(*) FROM lines WHERE text_id=?',
                                      (text_id,)).fetchone()
        n_postings_after, = con.execute('SELECT COUNT(*) FROM postings WHERE text_id=?',
                                         (text_id,)).fetchone()
        if n_lines_after != plan['lines']:
            raise AssertionError('line row count changed')
        if n_postings_after != plan['postings']:
            raise AssertionError('postings row count changed')
        stray, = con.execute('SELECT COUNT(*) FROM lines WHERE text_id=? AND ref LIKE ?',
                              (text_id, old + '.%')).fetchone()
        if stray:
            raise AssertionError('old-named refs remain in lines')
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise AssertionError('integrity_check failed on the renamed copy')
    except BaseException:
        con.close()
        os.remove(tmp)
        raise
    con.close()
    backup_path = backup(db, tag='rename')
    os.replace(tmp, db)
    return {**plan, 'applied': True, 'backup': backup_path,
            'lines_after': n_lines_after, 'postings_after': n_postings_after}


# -------------------------------------------------------------- lemma cache

def lemma_cache_paths(root, language, work_id):
    cache_lang_dir = os.path.join(root, 'cache', 'lemmas', language)
    legacy = os.path.join(cache_lang_dir, f'{work_id.replace("/", "_")}.json')
    hashed = get_cache_path(f'{work_id}.tess', language,
                             cache_dir=os.path.join(root, 'cache', 'lemmas'))
    return {'legacy': legacy, 'hashed': hashed}


def plan_lemma_cache(root, language, old):
    paths = lemma_cache_paths(root, language, old)
    found = {k: v for k, v in paths.items() if os.path.exists(v)}
    return {'found': found}


def _rewrite_cache_payload(data, old, new, new_file_hash):
    data = dict(data)
    old_text_id, new_text_id = f'{old}.tess', f'{new}.tess'
    if data.get('text_id') == old_text_id:
        data['text_id'] = new_text_id
    for key in ('units_line', 'units_phrase'):
        units = data.get(key)
        if not units:
            continue
        rewritten = []
        for u in units:
            u = dict(u)
            if 'ref' in u:
                u['ref'] = _rewrite_prefix(u['ref'], old, new)
            rewritten.append(u)
        data[key] = rewritten
    if new_file_hash is not None:
        data['file_hash'] = new_file_hash
    return data


def apply_lemma_cache(root, language, old, new, new_tess_path):
    plan = plan_lemma_cache(root, language, old)
    if not plan['found']:
        return {'found': {}, 'written': []}
    new_paths = lemma_cache_paths(root, language, new)
    for kind in plan['found']:
        if os.path.exists(new_paths[kind]):
            raise RuntimeError(f'refusing: {new_paths[kind]} already exists')
    new_hash = None
    if os.path.exists(new_tess_path):
        with open(new_tess_path, 'rb') as f:
            new_hash = hashlib.md5(f.read()).hexdigest()  # nosec B324
    written = []
    for kind, old_path in plan['found'].items():
        with open(old_path, encoding='utf-8') as f:
            data = json.load(f)
        backup(old_path, tag='rename')  # the un-renamed original stays too
        new_data = _rewrite_cache_payload(data, old, new, new_hash)
        new_path = new_paths[kind]
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        atomic_write(new_path, json.dumps(new_data, ensure_ascii=False))
        written.append({'kind': kind, 'old': old_path, 'new': new_path,
                         'file_hash_updated': new_hash is not None})
    return {'found': plan['found'], 'written': written}


# ------------------------------------------------------------ passage index
#
# rename_work_in_passage_index.py matches a prefix `old + '.'` against three
# kinds of value: the window id (`<work>:<scale>:<n>`, work itself being
# `<author>.<title>`), the 'work' field of a description (equal to the work
# id, no suffix), and a ref (`<work>.<n>`, dot-joined). Those three only
# share a common `old + '.'` prefix when `old` is the AUTHOR alone -- the
# script's own docstring example renames an author, `archimède` ->
# `archimedes`, moving every work of that author at once. Passing a FULL
# work id (`iqbal_lahori.diwan`) as `old` does not match: the id has a colon
# after the title (`iqbal_lahori.diwan:fine:0`, not a dot), and the 'work'
# field is `iqbal_lahori.diwan` with nothing after it for `old + '.'` to be
# a prefix of. So this script is reused at the AUTHOR level (correct here:
# iqbal_lahori names exactly one work, so renaming the author moves exactly
# the one work this whole rename is about) -- not called directly with the
# full work ids, and NOT reused for a rename that changes the work title
# rather than (or in addition to) the author, which the guard below refuses
# rather than mishandling.

def passage_index_dir(root):
    return os.path.join(root, 'data', 'passage_index')


def _passage_ids(idx):
    return json.load(open(os.path.join(idx, 'ids.json'), encoding='utf-8'))


def _passage_author_works(ids, author):
    """Distinct work ids in `ids` (window ids, `<work>:<scale>:<n>`) whose
    work starts with `author + '.'`."""
    prefix = author + '.'
    return {i.split(':', 1)[0] for i in ids if i.split(':', 1)[0].startswith(prefix)}


def plan_passage_index(root, old, new):
    idx = passage_index_dir(root)
    ids_path = os.path.join(idx, 'ids.json')
    if not os.path.exists(ids_path):
        return {'found': False}
    old_author, old_rest = split_id(old)
    new_author, new_rest = split_id(new)
    works = _passage_author_works(_passage_ids(idx), old_author)
    if old not in works:
        return {'found': False}  # this work isn't in the passage index at all
    if old_rest != new_rest:
        return {'found': True, 'index': idx, 'supported': False,
                'reason': ("rename_work_in_passage_index.py only reuses cleanly for an "
                           "author-level move (unchanged work title); this rename changes "
                           "the work title too, so the passage index needs its own pass")}
    other_works = sorted(w for w in works if w != old)
    counts = passage_rename.count_affected(idx, old_author)
    return {'found': True, 'index': idx, 'supported': True,
            'old_author': old_author, 'new_author': new_author,
            'other_works_under_author': other_works, **counts}


def passage_index_would_collide(root, old, new):
    plan = plan_passage_index(root, old, new)
    if not plan.get('found') or not plan.get('supported'):
        return False
    idx = plan['index']
    existing = set(_passage_ids(idx))
    would_be = {passage_rename.renamed(i, plan['old_author'], plan['new_author'])
                for i in existing if i.startswith(plan['old_author'] + '.')}
    return bool(would_be & existing)


def apply_passage_index(root, old, new):
    plan = plan_passage_index(root, old, new)
    if not plan.get('found') or not plan.get('supported'):
        return plan
    if plan['other_works_under_author']:
        raise RuntimeError(
            f"refusing: the passage index holds other work(s) under author "
            f"{plan['old_author']!r} too ({plan['other_works_under_author']}); "
            "an author-level rename would move them as well -- handle this one by hand")
    if not any(plan.get(k) for k in ('ids', 'descriptions', 'windows', 'line rows')):
        return {**plan, 'applied': False, 'reason': 'nothing under the old name'}
    rc = passage_rename.main(['--index', plan['index'], '--from', plan['old_author'],
                               '--to', plan['new_author'], '--tag', 'rename', '--apply'])
    if rc != 0:
        raise RuntimeError(f'rename_work_in_passage_index.py refused or failed (exit {rc})')
    return {**plan, 'applied': True}


# -------------------------------------------------------------- embeddings

def embeddings_paths(root, language, work_id):
    base = os.path.join(root, 'backend', 'embeddings', language, work_id)
    return {'npy': base + '.npy', 'meta': base + '.meta.json'}


def plan_embeddings(root, language, old):
    paths = embeddings_paths(root, language, old)
    found = {k: v for k, v in paths.items() if os.path.exists(v)}
    return {'found': found}


def apply_embeddings(root, language, old, new, old_tag, new_tag):
    plan = plan_embeddings(root, language, old)
    if not plan['found']:
        return {'found': {}, 'written': []}
    new_paths = embeddings_paths(root, language, new)
    for kind in plan['found']:
        if os.path.exists(new_paths[kind]):
            raise RuntimeError(f'refusing: {new_paths[kind]} already exists')
    written = []
    if 'npy' in plan['found']:
        old_path = plan['found']['npy']
        backup(old_path, tag='rename')
        os.replace(old_path, new_paths['npy'])
        written.append({'kind': 'npy', 'old': old_path, 'new': new_paths['npy']})
    if 'meta' in plan['found']:
        old_path = plan['found']['meta']
        with open(old_path, encoding='utf-8') as f:
            meta = json.load(f)
        backup(old_path, tag='rename')
        meta = dict(meta)
        text_path = meta.get('text_path')
        if isinstance(text_path, str):
            dirpart, base = os.path.split(text_path)
            if base == f'{old}.tess':
                meta['text_path'] = os.path.join(dirpart, f'{new}.tess')
        refs = meta.get('line_refs')
        n_rewritten = 0
        if isinstance(refs, list):
            new_refs = []
            for r in refs:
                nr = _rewrite_prefix(r, old_tag, new_tag) if isinstance(r, str) else r
                if nr != r:
                    n_rewritten += 1
                new_refs.append(nr)
            meta['line_refs'] = new_refs
        new_path = new_paths['meta']
        atomic_write(new_path, json.dumps(meta, ensure_ascii=False))
        os.remove(old_path)
        written.append({'kind': 'meta', 'old': old_path, 'new': new_path,
                         'line_refs_rewritten': n_rewritten,
                         'line_refs_total': len(refs or [])})
    return {'found': plan['found'], 'written': written}


# --------------------------------------------------------------- orchestration

def check_collisions(root, language, old, new):
    problems = []
    if os.path.exists(tess_path(root, language, new)):
        problems.append(f'{tess_path(root, language, new)} already exists')
    index_plan = plan_index(root, language, old, new)
    if index_plan.get('found') and index_plan.get('text_present') and index_plan.get('new_filename_exists'):
        problems.append(f'{new}.tess already present in {index_plan["db"]}')
    lemma_found = plan_lemma_cache(root, language, old)['found']
    lemma_new = lemma_cache_paths(root, language, new)
    for kind in lemma_found:
        if os.path.exists(lemma_new[kind]):
            problems.append(f'lemma cache {lemma_new[kind]} already exists')
    emb_found = plan_embeddings(root, language, old)['found']
    emb_new = embeddings_paths(root, language, new)
    for kind in emb_found:
        if os.path.exists(emb_new[kind]):
            problems.append(f'embeddings {emb_new[kind]} already exists')
    if passage_index_would_collide(root, old, new):
        problems.append('passage index: renamed ids would collide with ids already present')
    passage_plan = plan_passage_index(root, old, new)
    if passage_plan.get('found') and passage_plan.get('supported') and passage_plan.get('other_works_under_author'):
        problems.append(
            f"passage index: author {passage_plan['old_author']!r} also holds "
            f"{passage_plan['other_works_under_author']}; an author-level rename "
            "would move them too -- handle the passage index by hand")
    return problems


def _passage_has_something(plan):
    if not plan.get('found'):
        return False
    if not plan.get('supported', True):
        return True  # found but needs a by-hand pass; don't call it "nothing"
    return any(plan.get(k) for k in ('ids', 'descriptions', 'windows', 'line rows'))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=ROOT, help='repository root (default: this script\'s own)')
    ap.add_argument('--language', required=True)
    ap.add_argument('--old', required=True, help='current work id, e.g. iqbal_lahori.diwan')
    ap.add_argument('--new', required=True, help='new work id, e.g. iqbal.diwan')
    ap.add_argument('--old-tag', dest='old_tag', default=None,
                     help='the .tess line-tag prefix, if it differs from --old')
    ap.add_argument('--new-tag', dest='new_tag', default=None,
                     help='the .tess line-tag prefix, if it differs from --new')
    add_apply_argument(ap, 'write the rename (default: report only)')
    args = ap.parse_args(argv)

    old, new = args.old, args.new
    if old == new:
        print('nothing to do: the two ids are the same')
        return 0
    old_tag = args.old_tag or old
    new_tag = args.new_tag or new
    root, language = args.root, args.language

    tess_plan = plan_tess(root, language, old, old_tag)
    index_plan = plan_index(root, language, old, new)
    lemma_plan = plan_lemma_cache(root, language, old)
    passage_plan = plan_passage_index(root, old, new)
    emb_plan = plan_embeddings(root, language, old)

    print(f'{language}/{old} -> {language}/{new}  (tag {old_tag} -> {new_tag})')
    print(f'  .tess:           {tess_plan}')
    print(f'  inverted index:  {index_plan}')
    print(f'  lemma cache:     found={sorted(lemma_plan["found"])}')
    print(f'  passage index:   {passage_plan}')
    print(f'  embeddings:      found={sorted(emb_plan["found"])}')

    nothing_found = (
        not tess_plan.get('found')
        and not (index_plan.get('found') and index_plan.get('text_present'))
        and not lemma_plan['found']
        and not _passage_has_something(passage_plan)
        and not emb_plan['found']
    )
    if nothing_found:
        print('\nnothing carries that name in any store under --root')
        return 0

    problems = check_collisions(root, language, old, new)
    if problems:
        print('\nREFUSING: the new id already exists', file=sys.stderr)
        for p in problems:
            print(f'  - {p}', file=sys.stderr)
        return 2

    if not args.apply:
        print('\ndry run, nothing written; pass --apply')
        return 0

    results = {'tess': apply_tess(root, language, old, new, old_tag, new_tag)}
    results['index'] = apply_index(root, language, old, new)
    results['lemma_cache'] = apply_lemma_cache(
        root, language, old, new, tess_path(root, language, new))
    results['passage_index'] = apply_passage_index(root, old, new)
    results['embeddings'] = apply_embeddings(root, language, old, new, old_tag, new_tag)

    print('\napplied:')
    for k, v in results.items():
        print(f'  {k}: {v}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
