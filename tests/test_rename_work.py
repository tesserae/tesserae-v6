"""Tests for scripts/corpus/rename_work.py: renaming a work across the
.tess file, the inverted index, the lemma cache, the passage index, and
precomputed embeddings -- everything a work's id touches outside git.

Everything here is built fresh under pytest's tmp_path and passed to the
script via --root. Nothing touches this repository's own texts/, data/,
cache/, or backend/embeddings/.
"""
import hashlib
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from scripts.corpus import rename_work as rw  # noqa: E402
from backend.lemma_cache import get_cache_path  # noqa: E402

OLD = 'iqbal_lahori.diwan'
NEW = 'iqbal.diwan'
LANG = 'fa'

TESS_LINES = [
    (f'{OLD}.1', 'دی شیخ با چراغ'),
    (f'{OLD}.2', 'کز دام و دد'),
    (f'{OLD}.3', 'زاین همرهان'),
]

OTHER_TESS_LINES = [
    ('other.work.1', 'unrelated text'),
]


def _write_tess(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for ref, text in lines:
            f.write(f'<{ref}>\t{text}\n')


def _build_index_db(path, rows):
    """rows: list of (text_id, filename, author, title, line_refs)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, '
                'author TEXT, title TEXT, line_count INTEGER)')
    con.execute('CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, '
                'lemmas TEXT, tokens TEXT, PRIMARY KEY (text_id, ref))')
    con.execute('CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)')
    con.execute('CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INTEGER)')
    for text_id, filename, author, title, refs in rows:
        con.execute('INSERT INTO texts VALUES (?, ?, ?, ?, ?)',
                    (text_id, filename, author, title, len(refs)))
        for ref in refs:
            con.execute('INSERT INTO lines VALUES (?, ?, ?, ?, ?)',
                        (text_id, ref, 'content', '["lemma"]', '["tok"]'))
            con.execute('INSERT INTO postings VALUES (?, ?, ?, ?)',
                        ('lemma', text_id, ref, '[0]'))
    con.execute("INSERT INTO lemma_doc_freq VALUES ('lemma', 2)")
    con.commit()
    con.close()


def _build_passage_index(idx_dir, entries):
    """entries: list of (work, n_windows) -> builds ids.json, descriptions.jsonl,
    window_texts.db consistent with scripts/corpus/build_batch_windows.py's
    actual field names."""
    os.makedirs(idx_dir, exist_ok=True)
    ids = []
    descriptions = []
    windows = []
    lines_rows = []
    for work, n in entries:
        for i in range(n):
            wid = f'{work}:fine:{i}'
            ids.append(wid)
            ref_start = f'{work}.{i * 2 + 1}'
            ref_end = f'{work}.{i * 2 + 2}'
            descriptions.append({'id': wid, 'language': LANG, 'work': work,
                                  'scale': 'fine', 'ref_start': ref_start,
                                  'ref_end': ref_end, 'desc': f'desc {i}'})
            windows.append((wid, LANG, work, ref_start, ref_end, 'window text'))
        lines_rows.extend((work, i, f'{work}.{i + 1}', f'line {i}') for i in range(n * 2))

    json.dump(ids, open(os.path.join(idx_dir, 'ids.json'), 'w', encoding='utf-8'))
    with open(os.path.join(idx_dir, 'descriptions.jsonl'), 'w', encoding='utf-8') as f:
        for d in descriptions:
            f.write(json.dumps(d, ensure_ascii=False) + '\n')
    con = sqlite3.connect(os.path.join(idx_dir, 'window_texts.db'))
    con.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, '
                'ref_start TEXT, ref_end TEXT, text TEXT)')
    con.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    con.executemany('INSERT INTO window_texts VALUES (?, ?, ?, ?, ?, ?)', windows)
    con.executemany('INSERT INTO lines VALUES (?, ?, ?, ?)', lines_rows)
    con.commit()
    con.close()


@pytest.fixture
def root(tmp_path):
    r = str(tmp_path)
    _write_tess(os.path.join(r, 'texts', LANG, f'{OLD}.tess'), TESS_LINES)
    _write_tess(os.path.join(r, 'texts', LANG, 'other.work.tess'), OTHER_TESS_LINES)

    _build_index_db(
        os.path.join(r, 'data', 'inverted_index', f'{LANG}_index.db'),
        [(1, f'{OLD}.tess', 'iqbal_lahori', 'diwan', [l[0] for l in TESS_LINES]),
         (2, 'other.work.tess', 'other', 'work', ['other.work.1'])])

    cache_lang_dir = os.path.join(r, 'cache', 'lemmas', LANG)
    os.makedirs(cache_lang_dir, exist_ok=True)
    units_line = [{'ref': ref, 'text': text, 'tokens': []} for ref, text in TESS_LINES]
    cache_payload = {
        'text_id': f'{OLD}.tess', 'language': LANG,
        'file_hash': hashlib.md5(
            open(os.path.join(r, 'texts', LANG, f'{OLD}.tess'), 'rb').read()
        ).hexdigest(),
        'cached_at': '2026-09-06T00:00:00', 'units_line': units_line, 'units_phrase': [],
    }
    hashed_path = get_cache_path(f'{OLD}.tess', LANG, cache_dir=os.path.join(r, 'cache', 'lemmas'))
    os.makedirs(os.path.dirname(hashed_path), exist_ok=True)
    json.dump(cache_payload, open(hashed_path, 'w', encoding='utf-8'), ensure_ascii=False)
    legacy_path = os.path.join(cache_lang_dir, f'{OLD}.json')
    json.dump(cache_payload, open(legacy_path, 'w', encoding='utf-8'), ensure_ascii=False)

    _build_passage_index(os.path.join(r, 'data', 'passage_index'),
                          [(OLD, 2), ('other.work', 1)])

    emb_dir = os.path.join(r, 'backend', 'embeddings', LANG)
    os.makedirs(emb_dir, exist_ok=True)
    with open(os.path.join(emb_dir, f'{OLD}.npy'), 'wb') as f:
        f.write(b'\x93NUMPY-fake-vector-bytes')
    meta = {
        'text_path': os.path.join(r, 'backend', '..', 'texts', LANG, f'{OLD}.tess'),
        'language': LANG, 'n_lines': len(TESS_LINES), 'embedding_dim': 4,
        'created': '2026-09-06T00:00:00',
        'line_refs': [ref for ref, _ in TESS_LINES],
    }
    json.dump(meta, open(os.path.join(emb_dir, f'{OLD}.meta.json'), 'w', encoding='utf-8'))

    return r


# --------------------------------------------------------------- dry run ---

def test_dry_run_reports_without_writing(root, capsys):
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'dry run, nothing written' in out
    # nothing moved
    assert os.path.exists(os.path.join(root, 'texts', LANG, f'{OLD}.tess'))
    assert not os.path.exists(os.path.join(root, 'texts', LANG, f'{NEW}.tess'))


def test_nothing_found_for_an_unrelated_id(root, capsys):
    rc = rw.main(['--root', root, '--language', LANG, '--old', 'nobody.nothing',
                  '--new', 'nobody.something'])
    assert rc == 0
    assert 'nothing carries that name' in capsys.readouterr().out


def test_same_old_and_new_is_a_noop(root, capsys):
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', OLD])
    assert rc == 0
    assert 'nothing to do' in capsys.readouterr().out


# --------------------------------------------------------------- collision -

def test_refuses_when_new_tess_already_exists(root, capsys):
    new_path = os.path.join(root, 'texts', LANG, f'{NEW}.tess')
    _write_tess(new_path, [('x.1', 'already here')])
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc == 2
    err = capsys.readouterr().err
    assert 'REFUSING' in err
    # nothing under the old name was touched
    assert os.path.exists(os.path.join(root, 'texts', LANG, f'{OLD}.tess'))
    con = sqlite3.connect(os.path.join(root, 'data', 'inverted_index', f'{LANG}_index.db'))
    assert con.execute('SELECT filename FROM texts WHERE text_id=1').fetchone()[0] == f'{OLD}.tess'
    con.close()


# ----------------------------------------------------------------- apply ---

def test_apply_renames_every_store(root):
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc == 0

    # 1. .tess file + line tags
    old_tess = os.path.join(root, 'texts', LANG, f'{OLD}.tess')
    new_tess = os.path.join(root, 'texts', LANG, f'{NEW}.tess')
    assert not os.path.exists(old_tess)
    assert os.path.exists(new_tess)
    content = open(new_tess, encoding='utf-8').read()
    assert f'<{NEW}.1>' in content
    assert OLD not in content
    assert any(f.startswith(f'{os.path.basename(old_tess)}.bak-rename-')
               for f in os.listdir(os.path.dirname(old_tess)))
    # the unrelated text is untouched
    assert os.path.exists(os.path.join(root, 'texts', LANG, 'other.work.tess'))

    # 2. inverted index
    db = os.path.join(root, 'data', 'inverted_index', f'{LANG}_index.db')
    con = sqlite3.connect(db)
    row = con.execute('SELECT filename, author, title FROM texts WHERE text_id=1').fetchone()
    assert row == (f'{NEW}.tess', 'iqbal', 'diwan')
    refs = [r[0] for r in con.execute('SELECT ref FROM lines WHERE text_id=1 ORDER BY ref')]
    assert refs == [f'{NEW}.1', f'{NEW}.2', f'{NEW}.3']
    posting_refs = sorted(r[0] for r in con.execute('SELECT ref FROM postings WHERE text_id=1'))
    assert posting_refs == [f'{NEW}.1', f'{NEW}.2', f'{NEW}.3']
    # the unrelated work (text_id 2) is untouched
    other_row = con.execute('SELECT filename, author, title FROM texts WHERE text_id=2').fetchone()
    assert other_row == ('other.work.tess', 'other', 'work')
    other_refs = [r[0] for r in con.execute('SELECT ref FROM lines WHERE text_id=2')]
    assert other_refs == ['other.work.1']
    con.close()
    assert any(f.startswith(f'{LANG}_index.db.bak-rename-')
               for f in os.listdir(os.path.dirname(db)))

    # 3. lemma cache
    new_hashed = get_cache_path(f'{NEW}.tess', LANG, cache_dir=os.path.join(root, 'cache', 'lemmas'))
    assert os.path.exists(new_hashed)
    new_payload = json.load(open(new_hashed, encoding='utf-8'))
    assert new_payload['text_id'] == f'{NEW}.tess'
    assert [u['ref'] for u in new_payload['units_line']] == [f'{NEW}.1', f'{NEW}.2', f'{NEW}.3']
    expected_hash = hashlib.md5(open(new_tess, 'rb').read()).hexdigest()
    assert new_payload['file_hash'] == expected_hash

    new_legacy = os.path.join(root, 'cache', 'lemmas', LANG, f'{NEW}.json')
    assert os.path.exists(new_legacy)

    # the old cache files remain (kept as their own backup) plus a stamped copy
    old_legacy = os.path.join(root, 'cache', 'lemmas', LANG, f'{OLD}.json')
    assert os.path.exists(old_legacy)
    cache_dir_files = os.listdir(os.path.join(root, 'cache', 'lemmas', LANG))
    assert any('.bak-rename-' in f for f in cache_dir_files)

    # 4. passage index
    idx = os.path.join(root, 'data', 'passage_index')
    ids = json.load(open(os.path.join(idx, 'ids.json'), encoding='utf-8'))
    assert f'{NEW}:fine:0' in ids
    assert f'{NEW}:fine:1' in ids
    assert f'{OLD}:fine:0' not in ids
    assert 'other.work:fine:0' in ids  # untouched
    descs = [json.loads(l) for l in open(os.path.join(idx, 'descriptions.jsonl'), encoding='utf-8')]
    renamed_descs = [d for d in descs if d['work'] == NEW]
    assert len(renamed_descs) == 2
    assert all(d['ref_start'].startswith(f'{NEW}.') for d in renamed_descs)
    other_descs = [d for d in descs if d['work'] == 'other.work']
    assert len(other_descs) == 1

    wcon = sqlite3.connect(os.path.join(idx, 'window_texts.db'))
    works = {r[0] for r in wcon.execute('SELECT DISTINCT work FROM window_texts')}
    assert works == {NEW, 'other.work'}
    line_works = {r[0] for r in wcon.execute('SELECT DISTINCT work FROM lines')}
    assert line_works == {NEW, 'other.work'}
    wcon.close()

    # 5. embeddings
    new_npy = os.path.join(root, 'backend', 'embeddings', LANG, f'{NEW}.npy')
    new_meta = os.path.join(root, 'backend', 'embeddings', LANG, f'{NEW}.meta.json')
    assert os.path.exists(new_npy)
    assert os.path.exists(new_meta)
    assert not os.path.exists(os.path.join(root, 'backend', 'embeddings', LANG, f'{OLD}.npy'))
    meta = json.load(open(new_meta, encoding='utf-8'))
    assert meta['text_path'].endswith(f'/{NEW}.tess')
    assert meta['line_refs'] == [f'{NEW}.1', f'{NEW}.2', f'{NEW}.3']


def test_rerun_refuses_rather_than_double_applying(root, capsys):
    rc1 = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc1 == 0
    # The old lemma cache files are deliberately kept (as their own backup),
    # so a second run with the same arguments finds the NEW names already
    # occupied and refuses, rather than silently doing nothing or clobbering
    # what the first run wrote.
    rc2 = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc2 == 2
    assert 'REFUSING' in capsys.readouterr().err


# --------------------------------------------- passage index: unsupported --

def test_passage_index_refuses_author_with_other_works(tmp_path, capsys):
    r = str(tmp_path)
    _write_tess(os.path.join(r, 'texts', LANG, f'{OLD}.tess'), TESS_LINES)
    # a SECOND work under the same old author, which an author-level passage
    # index rename would also move -- the script must refuse rather than
    # silently renaming more than asked.
    _build_passage_index(os.path.join(r, 'data', 'passage_index'),
                          [(OLD, 1), ('iqbal_lahori.another_work', 1)])
    rc = rw.main(['--root', r, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc == 2
    assert 'REFUSING' in capsys.readouterr().err
    # nothing was touched
    assert os.path.exists(os.path.join(r, 'texts', LANG, f'{OLD}.tess'))


def test_passage_index_unsupported_when_work_title_changes(tmp_path, capsys):
    r = str(tmp_path)
    old_id = 'hafez.diwan'
    new_id = 'hafez.divan'  # title itself changes, not just the author
    _write_tess(os.path.join(r, 'texts', LANG, f'{old_id}.tess'),
                [(f'{old_id}.1', 'text')])
    _build_passage_index(os.path.join(r, 'data', 'passage_index'), [(old_id, 1)])
    rc = rw.main(['--root', r, '--language', LANG, '--old', old_id, '--new', new_id])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'supported' in out.lower() or 'own pass' in out.lower()
