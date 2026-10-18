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
    json.dump({'index_version': '2026-01-01',
               'languages': {LANG: sorted({w for w, _ in entries})}},
              open(os.path.join(idx_dir, 'works_by_language.json'), 'w', encoding='utf-8'))
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

    # 4b. the works-by-language sidecar (the Theme Search author filter reads
    # it instead of loading the index; the 2026-10-15 Thucydides rename left
    # it on the old name and the filter found nothing)
    sidecar = json.load(open(os.path.join(idx, 'works_by_language.json'), encoding='utf-8'))
    assert sidecar['languages'][LANG] == sorted([NEW, 'other.work'])
    import datetime
    assert sidecar['index_version'] == datetime.date.fromtimestamp(
        os.path.getmtime(os.path.join(idx, 'ids.json'))).isoformat()

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


def test_apply_succeeds_while_a_reader_holds_the_passage_texts_open(root):
    """Production's web workers keep window_texts.db open. Updating it in place
    failed with "database is locked" (2026-10-07) and left the passage index half
    renamed; the rename now updates a copy and swaps it in."""
    db = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    reader = sqlite3.connect(db, timeout=0.1)
    reader.execute('BEGIN')
    reader.execute('SELECT count(*) FROM window_texts').fetchone()   # holds a shared lock
    try:
        rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    finally:
        reader.rollback()
        reader.close()
    assert rc == 0
    wcon = sqlite3.connect(db)
    works = {r[0] for r in wcon.execute('SELECT DISTINCT work FROM window_texts')}
    assert NEW in works and OLD not in works
    assert not os.path.exists(db + '.renaming')


# ------------------------------------------------- events store, translations

def _build_events_db(root, rows_passages, rows_judgements):
    path = os.path.join(root, 'data', 'events', 'event_dossiers.sqlite')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE passages (event_id TEXT, rank INTEGER, work TEXT, ref_start TEXT, '
                'ref_end TEXT, score REAL, llm_label TEXT, names_matched TEXT, snippet TEXT, '
                'window_id TEXT, language TEXT)')
    con.execute('CREATE TABLE judgements (model TEXT, event TEXT, window_id TEXT, prompt TEXT, '
                'label TEXT, ts REAL, PRIMARY KEY (model, event, window_id, prompt))')
    for i, (work, wid) in enumerate(rows_passages):
        con.execute('INSERT INTO passages VALUES (?, ?, ?, ?, ?, 0.1, "yes", "[]", "s", ?, ?)',
                    ('Q1', i, work, 'a 1.1', 'a 1.2', wid, LANG))
    for i, wid in enumerate(rows_judgements):
        con.execute('INSERT INTO judgements VALUES ("m", ?, ?, "v1", "no", 0.0)', (f'Q{i}', wid))
    con.commit()
    con.close()
    return path


def _events_root(root):
    return _build_events_db(
        root,
        [(OLD, f'{OLD}:fine:0'), (OLD, f'{OLD}.part.2:fine:7'), ('other.work', 'other.work:fine:0')],
        [f'{OLD}:fine:0', f'{OLD}.part.1:fine:3', 'other.work:fine:0', f'{OLD}x:fine:0'])


def _translations_root(root):
    tdir = os.path.join(root, 'data', 'translations')
    os.makedirs(os.path.join(tdir, 'links'), exist_ok=True)
    json.dump({'tess_work': f'{LANG}/{OLD}', 'language': LANG, 'units': []},
              open(os.path.join(tdir, f'{LANG}__{OLD}.json'), 'w', encoding='utf-8'))
    manifest = [
        {'work_id_guess': OLD, 'tess_key': f'{LANG}/{OLD}', 'language': LANG,
         'file': f'{LANG}__{OLD}.json'},
        {'work_id_guess': 'other.work', 'tess_key': f'{LANG}/other.work', 'language': LANG,
         'file': f'{LANG}__other.work.json'},
    ]
    json.dump(manifest, open(os.path.join(tdir, 'manifest.json'), 'w', encoding='utf-8'))
    json.dump({'work': OLD, 'language': LANG, 'links': {f'{OLD}.1': {'url': 'u'}, 'zz.1': {'url': 'v'}}},
              open(os.path.join(tdir, 'links', f'{LANG}__links.json'), 'w', encoding='utf-8'))
    return tdir


def test_events_plan_counts(root, capsys):
    _events_root(root)
    plan = rw.plan_events(root, OLD, NEW)
    assert plan['passages_work'] == 2
    assert plan['passages_window_id'] == 2
    assert plan['judgements_window_id'] == 2  # the 'OLDx' id is not a match
    assert plan['new_id_rows'] == 0
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW])
    assert rc == 0
    assert 'events store' in capsys.readouterr().out


def test_events_apply_rewrites_backs_up_and_verifies(root):
    path = _events_root(root)
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc == 0
    con = sqlite3.connect(path)
    assert con.execute('SELECT COUNT(*) FROM passages WHERE work = ?', (NEW,)).fetchone()[0] == 2
    wids = sorted(r[0] for r in con.execute('SELECT window_id FROM passages'))
    assert wids == sorted([f'{NEW}:fine:0', f'{NEW}.part.2:fine:7', 'other.work:fine:0'])
    jw = sorted(r[0] for r in con.execute('SELECT window_id FROM judgements'))
    assert jw == sorted([f'{NEW}:fine:0', f'{NEW}.part.1:fine:3', 'other.work:fine:0', f'{OLD}x:fine:0'])
    assert con.execute('SELECT COUNT(*) FROM passages WHERE work LIKE ?', (OLD + '%',)).fetchone()[0] == 0
    con.close()
    assert any(f.startswith('event_dossiers.sqlite.bak-rename-')
               for f in os.listdir(os.path.dirname(path)))


def test_events_absent_is_skipped_silently(root):
    assert rw.plan_events(root, OLD, NEW) == {'found': False}
    assert rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply']) == 0


def test_events_collision_refuses_without_force(root, capsys):
    path = _events_root(root)
    con = sqlite3.connect(path)
    con.execute('INSERT INTO judgements VALUES ("m", "Qz", ?, "v1", "no", 0.0)', (f'{NEW}:fine:9',))
    con.commit()
    con.close()
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc == 2
    assert 'events store' in capsys.readouterr().err
    con = sqlite3.connect(path)
    assert con.execute('SELECT COUNT(*) FROM passages WHERE work = ?', (OLD,)).fetchone()[0] == 2
    con.close()
    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply', '--force'])
    assert rc == 0


def test_translations_plan_and_apply(root):
    tdir = _translations_root(root)
    plan = rw.plan_translations(root, LANG, OLD, NEW)
    assert plan['file'].endswith(f'{LANG}__{OLD}.json')
    assert plan['manifest_fields'] == ['file', 'tess_key', 'work_id_guess']
    assert len(plan['links']) == 1 and plan['links'][0]['ref_keys'] == 1

    rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'])
    assert rc == 0
    assert not os.path.exists(os.path.join(tdir, f'{LANG}__{OLD}.json'))
    moved = json.load(open(os.path.join(tdir, f'{LANG}__{NEW}.json'), encoding='utf-8'))
    assert moved['tess_work'] == f'{LANG}/{NEW}'
    manifest = json.load(open(os.path.join(tdir, 'manifest.json'), encoding='utf-8'))
    assert manifest[0] == {'work_id_guess': NEW, 'tess_key': f'{LANG}/{NEW}', 'language': LANG,
                           'file': f'{LANG}__{NEW}.json'}
    assert manifest[1]['work_id_guess'] == 'other.work'
    links = json.load(open(os.path.join(tdir, 'links', f'{LANG}__links.json'), encoding='utf-8'))
    assert links['work'] == NEW
    assert sorted(links['links']) == [f'{NEW}.1', 'zz.1']
    names = os.listdir(tdir)
    assert any(n.startswith(f'{LANG}__{OLD}.json.bak-rename-') for n in names)
    assert any(n.startswith('manifest.json.bak-rename-') for n in names)
    assert any(n.startswith(f'{LANG}__links.json.bak-rename-') for n in os.listdir(os.path.join(tdir, 'links')))


def test_translation_file_collision_refuses_even_with_force(root, capsys):
    tdir = _translations_root(root)
    json.dump({}, open(os.path.join(tdir, f'{LANG}__{NEW}.json'), 'w'))
    for extra in ([], ['--force']):
        rc = rw.main(['--root', root, '--language', LANG, '--old', OLD, '--new', NEW, '--apply'] + extra)
        assert rc == 2
        assert 'already exists' in capsys.readouterr().err
    assert os.path.exists(os.path.join(tdir, f'{LANG}__{OLD}.json'))


# ------------------------------------------------- space-separated tags ----
#
# The Greek corpus tags its lines '<work N>' with a space, not '<work.N>', and
# a few files carry a broken tag whose work part is empty ('<antisthenes. 1>').
# The 2026-10-18 renaming of 37 Greek-titled works needed the tool to keep each
# ref's own separator in the .tess file, the index and the lemma cache.

SP_OLD = 'pseudolucian.λούκιος_ἢ_ὄνος'
SP_NEW = 'pseudolucian.asinus'
SP_LINES = [(f'{SP_OLD} 1', 'Ἀπῄειν ποτὲ ἐς Θετταλίαν'), (f'{SP_OLD} 2', 'ἦν δέ μοι πατρῷον')]


def _space_root(tmp_path, old, lines):
    r = str(tmp_path)
    _write_tess(os.path.join(r, 'texts', LANG, f'{old}.tess'), lines)
    _build_index_db(os.path.join(r, 'data', 'inverted_index', f'{LANG}_index.db'),
                    [(1, f'{old}.tess', old.split('.')[0], old.split('.', 1)[1], [l[0] for l in lines])])
    cache_dir = os.path.join(r, 'cache', 'lemmas')
    payload = {'text_id': f'{old}.tess', 'language': LANG, 'file_hash': 'x', 'cached_at': 'now',
               'units_line': [{'ref': ref, 'text': text, 'tokens': []} for ref, text in lines], 'units_phrase': []}
    hashed = get_cache_path(f'{old}.tess', LANG, cache_dir=cache_dir)
    os.makedirs(os.path.dirname(hashed), exist_ok=True)
    json.dump(payload, open(hashed, 'w', encoding='utf-8'), ensure_ascii=False)
    return r


def test_space_separated_tags_keep_their_separator(tmp_path):
    r = _space_root(tmp_path, SP_OLD, SP_LINES)
    assert rw.main(['--root', r, '--language', LANG, '--old', SP_OLD, '--new', SP_NEW, '--apply']) == 0
    content = open(os.path.join(r, 'texts', LANG, f'{SP_NEW}.tess'), encoding='utf-8').read()
    assert f'<{SP_NEW} 1>' in content and f'<{SP_OLD}' not in content
    con = sqlite3.connect(os.path.join(r, 'data', 'inverted_index', f'{LANG}_index.db'))
    refs = sorted(x for (x,) in con.execute('SELECT ref FROM lines'))
    assert refs == [f'{SP_NEW} 1', f'{SP_NEW} 2']
    assert sorted(x for (x,) in con.execute('SELECT ref FROM postings')) == refs
    cache = json.load(open(get_cache_path(f'{SP_NEW}.tess', LANG,
                                          cache_dir=os.path.join(r, 'cache', 'lemmas')), encoding='utf-8'))
    assert [u['ref'] for u in cache['units_line']] == [f'{SP_NEW} 1', f'{SP_NEW} 2']


def test_broken_tag_with_empty_work_part_is_repaired_through_old_tag(tmp_path):
    old, new = 'antisthenes.αἴας', 'antisthenes.aiax'
    lines = [('antisthenes. 1', 'Ἐβουλόμην ἂν'), ('antisthenes. 2', 'Σχεδὸν μὲν οὖν')]
    r = _space_root(tmp_path, old, lines)
    assert rw.main(['--root', r, '--language', LANG, '--old', old, '--new', new,
                             '--old-tag', 'antisthenes.', '--new-tag', new, '--apply']) == 0
    content = open(os.path.join(r, 'texts', LANG, f'{new}.tess'), encoding='utf-8').read()
    assert f'<{new} 1>' in content and '<antisthenes. ' not in content
    con = sqlite3.connect(os.path.join(r, 'data', 'inverted_index', f'{LANG}_index.db'))
    assert sorted(x for (x,) in con.execute('SELECT ref FROM lines')) == [f'{new} 1', f'{new} 2']


def _space_passage_index(idx_dir, work, n, other):
    """Like _build_passage_index, with the Greek corpus's 'work N' references."""
    os.makedirs(idx_dir, exist_ok=True)
    ids, descriptions, windows, lines_rows = [], [], [], []
    for w, count in ((work, n), (other, 1)):
        for i in range(count):
            wid = f'{w}:fine:{i}'
            ids.append(wid)
            rs, re_ = f'{w} {i * 2 + 1}', f'{w} {i * 2 + 2}'
            descriptions.append({'id': wid, 'language': LANG, 'work': w, 'scale': 'fine',
                                 'ref_start': rs, 'ref_end': re_, 'desc': f'desc {i}'})
            windows.append((wid, LANG, w, rs, re_, 'window text'))
        lines_rows.extend((w, i, f'{w} {i + 1}', f'line {i}') for i in range(count * 2))
    json.dump(ids, open(os.path.join(idx_dir, 'ids.json'), 'w', encoding='utf-8'))
    json.dump({'index_version': '2026-01-01', 'languages': {LANG: sorted([work, other])}},
              open(os.path.join(idx_dir, 'works_by_language.json'), 'w', encoding='utf-8'))
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


def test_title_change_moves_the_passage_index_through_leaf_mode(tmp_path):
    r = _space_root(tmp_path, SP_OLD, SP_LINES)
    # a second Pseudo-Lucian work under the same author must stay where it is
    other = 'pseudolucian.κυνικός'
    _space_passage_index(os.path.join(r, 'data', 'passage_index'), SP_OLD, 2, other)
    assert rw.main(['--root', r, '--language', LANG, '--old', SP_OLD, '--new', SP_NEW, '--apply']) == 0
    idx = os.path.join(r, 'data', 'passage_index')
    ids = json.load(open(os.path.join(idx, 'ids.json'), encoding='utf-8'))
    assert sorted(ids) == sorted([f'{SP_NEW}:fine:0', f'{SP_NEW}:fine:1', f'{other}:fine:0'])
    descs = [json.loads(l) for l in open(os.path.join(idx, 'descriptions.jsonl'), encoding='utf-8')]
    mine = [d for d in descs if d['work'] == SP_NEW]
    assert len(mine) == 2 and mine[0]['ref_start'] == f'{SP_NEW} 1' and mine[1]['ref_end'] == f'{SP_NEW} 4'
    assert [d for d in descs if d['work'] == other][0]['ref_start'] == f'{other} 1'
    con = sqlite3.connect(os.path.join(idx, 'window_texts.db'))
    assert sorted(x for (x,) in con.execute('SELECT ref_start FROM window_texts WHERE work = ?', (SP_NEW,))) == [f'{SP_NEW} 1', f'{SP_NEW} 3']
    assert sorted(x for (x,) in con.execute('SELECT ref FROM lines WHERE work = ?', (SP_NEW,))) == [f'{SP_NEW} 1', f'{SP_NEW} 2', f'{SP_NEW} 3', f'{SP_NEW} 4']
    assert con.execute('SELECT COUNT(*) FROM lines WHERE work = ?', (other,)).fetchone()[0] == 2
    sidecar = json.load(open(os.path.join(idx, 'works_by_language.json'), encoding='utf-8'))
    assert sorted(sidecar['languages'][LANG]) == sorted([SP_NEW, other])
