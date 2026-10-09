"""The public data bundle must never carry a withheld language, a restricted
text, a key, or a translation whose licence is not open.

The rules are in scripts/ops/public_bundle_exclusions.json. The script
scripts/ops/build_public_bundle.sh reads them through
scripts/ops/public_bundle_lib.py, and this test reads them the same way, so
the list the script obeys is the list the test checks.
"""
import json
import os
import sqlite3
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPS = os.path.join(ROOT, 'scripts', 'ops')
sys.path.insert(0, ROOT)
sys.path.insert(0, OPS)

import public_bundle_lib as lib  # noqa: E402
import filter_passage_index as fpi  # noqa: E402

EXCL = lib.load_exclusions()
REGISTRY_FILE = os.path.join(ROOT, EXCL['restricted_registry'])
HASH = 'a' * 32


def paths_for_work(lang, work):
    """Every kind of file the bundle could hold for one work."""
    return [
        f'texts/{lang}/{work}.tess',
        f'texts/{lang}/{work}.part.3.tess',
        f'cache/lemmas/{lang}/{work}-{HASH}.json',
        f'cache/lemmas/{lang}/{work}.part.2-{HASH}.json',
        f'data/translations/{lang}__{work}.json',
        f'data/translations/{lang}__{work}.part.1.json',
        f'backend/embeddings/{lang}/{work}.npy',
        f'backend/embeddings/{lang}/{work}.meta.json',
    ]


def test_core_and_withheld_languages_do_not_overlap():
    withheld = set(EXCL['withheld_languages']) | set(EXCL['other_languages_not_bundled'])
    assert not withheld & set(EXCL['core_languages'])
    assert {'ar', 'fa', 'ur'} <= set(EXCL['withheld_languages'])


@pytest.mark.parametrize('lang', ['ar', 'fa', 'ur', 'it', 'fro', 'gmh'])
def test_every_language_scoped_path_is_excluded(lang):
    for tpl in EXCL['language_scoped_path_templates']:
        path = tpl.format(lang=lang).replace('*', 'x')
        if tpl.endswith('/' + lang) or tpl == f'texts/{lang}':
            path += '/something.tess'
        assert lib.excluded_reason(path, EXCL), (tpl, path)


@pytest.mark.parametrize('lang', ['ar', 'fa', 'ur'])
def test_concrete_files_of_withheld_languages_are_excluded(lang):
    for path in (f'texts/{lang}/hafez.divan.tess', f'cache/lemmas/{lang}.json',
                 f'cache/lemmas/{lang}/hafez.divan-{HASH}.json',
                 f'data/inverted_index/{lang}_index.db', f'cache/bigrams/{lang}_bigrams.json',
                 f'backend/embeddings/{lang}/hafez.divan.npy', f'data/translations/{lang}__hafez.divan.json',
                 f'cache/reuse_pairs/{lang}.db', f'data/lemma_tables/{lang}_surface_lemmas.json'):
        assert lib.excluded_reason(path, EXCL), path


@pytest.mark.parametrize('path', [
    '.env', 'instance/app.db', 'tesseraev6.sql', 'db/tesseraev6.sql', 'data/job_uploads/x.txt',
    'cache/scholarship/abc.json', 'data/citation_index/citations.db', 'data/commentaries/rashi__genesis.json',
    'models/hub/x', 'tesserae-models/theme_reader_minilm/model.bin', 'secret.pem', 'server.key',
    'cache/bigrams/la_bigrams.json.pre-rebuild-1.bak', 'data/inverted_index/syntax_latin.db',
    'data/translations/manifest.json', 'data/translations/links/x.json', 'backup_passphrase',
])
def test_private_paths_are_excluded(path):
    assert lib.excluded_reason(path, EXCL), path


@pytest.mark.parametrize('path', [
    'texts/la/vergil.aeneid.tess', 'cache/lemmas/la.json', 'data/inverted_index/grc_index.db',
    'data/translations/la__vergil.aeneid.json', 'data/documents/metadata.db',
])
def test_ordinary_paths_are_allowed(path):
    assert lib.excluded_reason(path, EXCL) is None


def test_every_registry_entry_is_excluded_in_every_core_language():
    ids = lib.load_registry_ids(REGISTRY_FILE)
    ids = ids | {'phi.test_author.test_work'}  # a synthetic entry, because the live registry may be empty
    for work in ids:
        for lang in EXCL['core_languages']:
            for path in paths_for_work(lang, work):
                assert lib.excluded_reason(path, EXCL, ids), path


def test_a_work_not_in_the_registry_is_not_caught_by_mistake():
    for path in paths_for_work('la', 'vergil.aeneid'):
        assert lib.excluded_reason(path, EXCL, {'phi.other'}) is None, path


def test_registry_file_is_readable_json():
    with open(REGISTRY_FILE, encoding='utf-8') as f:
        assert isinstance(json.load(f)['texts'], dict)


@pytest.mark.parametrize('licence,ok', [
    ('Public domain (Douay-Rheims, via eBible.org)', True),
    ('CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain', True),
    ('CC BY 4.0 (Coptic SCRIPTORIUM)', True),
    ('Books 1-8 mostly Duff, public domain; books 9-17 A. S. Kline, non-commercial terms', False),
    ('Public domain text, used with a non-commercial attribution licence', False),
    ('All rights reserved', False),
    ('', False),
])
def test_translation_licence_check(tmp_path, licence, ok):
    p = tmp_path / 'la__x.json'
    p.write_text(json.dumps({'license': licence}), encoding='utf-8')
    assert lib.translation_licence_ok(str(p), EXCL)[0] is ok


def test_select_on_a_miniature_production_folder(tmp_path):
    prod = tmp_path / 'prod'

    def put(rel, text='x'):
        f = prod / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding='utf-8')

    for lang in ('la', 'fa', 'ur', 'ar'):
        put(f'texts/{lang}/w.tess')
        put(f'cache/lemmas/{lang}.json')
        put(f'cache/lemmas/{lang}/w-{HASH}.json')
        put(f'data/inverted_index/{lang}_index.db')
        put(f'cache/bigrams/{lang}_bigrams.json')
    put('texts/la/w.tess.pre-x.bak')
    put('texts/la/phi.secret.tess')
    put(f'cache/lemmas/la/phi.secret-{HASH}.json')
    put('data/translations/la__w.json', json.dumps({'license': 'Public domain'}))
    put('data/translations/la__k.json', json.dumps({'license': 'CC BY-NC 4.0'}))
    put('data/translations/fa__w.json', json.dumps({'license': 'Public domain'}))
    put('data/translations/links/ur__links.json')
    put('.env', 'SECRET=1')
    put('cache/scholarship/a.json')
    put('data/citation_index/citations.db')
    put('data/commentaries/rashi__genesis.json')
    put('data/job_uploads/u.txt')
    put('data/documents/metadata.db')

    notes = {}
    got = {i.rel for i in lib.select('core', str(prod), EXCL, {'phi.secret'}, notes)}
    assert 'texts/la/w.tess' in got
    assert 'cache/lemmas/la.json' in got
    assert 'data/translations/la__w.json' in got
    assert 'data/documents/metadata.db' in got
    assert 'data/translations/la__k.json' not in got
    banned = ('/fa', '/ur', '/ar', 'fa_', 'ur_', 'ar_', 'fa__', 'phi.secret', '.env', 'scholarship',
              'citation_index', 'commentaries', 'job_uploads', '.bak')
    for rel in got:
        assert not any(b in rel for b in banned), rel
        assert not rel.startswith(('texts/fa', 'texts/ur', 'texts/ar')), rel


def test_text_descriptions_keep_only_bundled_languages(tmp_path):
    prod = tmp_path / 'prod'
    (prod / 'data').mkdir(parents=True)
    (prod / 'data/text_descriptions.json').write_text(json.dumps({
        '_comment': 'c', 'la': {'a.b': 'x', 'phi.c': 'y'}, 'fa': {'z.z': 'q'}, 'ur': {}, 'ar': {}}), encoding='utf-8')
    out = lib.filtered_text_descriptions(str(prod), EXCL, {'phi.c'})
    assert set(out) == {'_comment', 'la'}
    assert out['la'] == {'a.b': 'x'}


def _make_index(prod):
    pdir = prod / 'data/passage_index'
    pdir.mkdir(parents=True)
    rows = [('a.w:fine:0', 'la', 'a.w'), ('a.w:fine:6', 'la', 'a.w'), ('f.d:fine:0', 'fa', 'f.d'),
            ('u.g:fine:0', 'ur', 'u.g'), ('g.h:fine:0', 'grc', 'g.h'), ('p.s:fine:0', 'la', 'phi.s')]
    (pdir / 'ids.json').write_text(json.dumps([r[0] for r in rows]))
    np.save(pdir / 'embeddings.npy', np.arange(len(rows) * 3, dtype=np.float32).reshape(len(rows), 3))
    with open(pdir / 'descriptions.jsonl', 'w', encoding='utf-8') as f:
        for i, lang, w in reversed(rows):  # not in embedding order, on purpose
            f.write(json.dumps({'id': i, 'language': lang, 'work': w,
                                'desc': {'gist': f'gist {i}', 'themes': ['t']}}) + '\n')
    c = sqlite3.connect(pdir / 'window_texts.db')
    c.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, ref_start TEXT, ref_end TEXT, text TEXT)')
    c.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    for i, lang, w in rows:
        c.execute('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', (i, lang, w, '1', '2', 'text'))
        c.execute('INSERT INTO lines VALUES (?,?,?,?)', (w, 0, '1', 'line'))
    c.commit(); c.close()
    c = sqlite3.connect(pdir / 'window_names.db')
    c.execute('CREATE TABLE window_names (id text, k text, form text)')
    c.execute('CREATE TABLE name_df (k text primary key, df integer)')
    c.execute('CREATE TABLE meta (key text, value text)')
    for i, k in (('a.w:fine:0', 'iesus'), ('f.d:fine:0', 'iesus'), ('u.g:fine:0', 'rumi'), ('g.h:fine:0', 'zeus')):
        c.execute('INSERT INTO window_names VALUES (?,?,?)', (i, k, k))
    c.executemany('INSERT INTO name_df VALUES (?,?)', [('iesus', 2), ('rumi', 1), ('zeus', 1)])
    c.executemany('INSERT INTO meta VALUES (?,?)', [('windows', '4'), ('windows_fa', '1'), ('windows_ur', '1'), ('windows_he', '0')])
    c.commit(); c.close()
    (pdir / 'works_by_language.json').write_text(json.dumps(
        {'index_version': 'x', 'languages': {'la': ['a.w', 'phi.s'], 'fa': ['f.d'], 'ur': ['u.g'], 'grc': ['g.h']}}))
    return rows


def test_passage_index_filter_drops_withheld_languages_and_restricted_works(tmp_path):
    prod = tmp_path / 'prod'
    rows = _make_index(prod)
    (prod / 'data').mkdir(exist_ok=True)
    reg = tmp_path / 'registry.json'
    reg.write_text(json.dumps({'texts': {'phi.s': {}}}))
    out = tmp_path / 'out'
    rc = fpi.main(['--prod', str(prod), '--out', str(out), '--registry', str(reg), '--skip-map'])
    assert rc == 0
    pdir = out / 'data/passage_index'
    ids = json.loads((pdir / 'ids.json').read_text())
    assert ids == ['a.w:fine:0', 'a.w:fine:6', 'g.h:fine:0']
    emb = np.load(pdir / 'embeddings.npy')
    src = np.load(prod / 'data/passage_index/embeddings.npy')
    assert emb.shape == (3, 3)
    assert (emb[0] == src[0]).all() and (emb[2] == src[4]).all()
    descs = [json.loads(line) for line in open(pdir / 'descriptions.jsonl', encoding='utf-8')]
    assert {d['id'] for d in descs} == set(ids)
    c = sqlite3.connect(pdir / 'window_texts.db')
    assert {r[0] for r in c.execute('SELECT language FROM window_texts')} == {'la', 'grc'}
    assert {r[0] for r in c.execute('SELECT DISTINCT work FROM lines')} == {'a.w', 'g.h'}
    c = sqlite3.connect(pdir / 'window_names.db')
    assert dict(c.execute('SELECT k, df FROM name_df')) == {'iesus': 1, 'zeus': 1}
    assert {r[0] for r in c.execute('SELECT key FROM meta')} == {'windows', 'windows_he'}
    c = sqlite3.connect(pdir / 'desc_fts.sqlite')
    assert c.execute('SELECT COUNT(*) FROM desc').fetchone()[0] == 3
    wbl = json.loads((pdir / 'works_by_language.json').read_text())
    assert set(wbl['languages']) == {'la', 'grc'} and wbl['languages']['la'] == ['a.w']


def test_connections_map_filter_recomputes_pair_tables(tmp_path):
    src = tmp_path / 'map.db'
    c = sqlite3.connect(src)
    c.executescript('''
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE works (work TEXT PRIMARY KEY, language TEXT, author_key TEXT, author_display TEXT,
            year INTEGER, era_label TEXT, century INTEGER, century_label TEXT, genre TEXT,
            window_count INTEGER, total_links INTEGER, links_per_window REAL);
        CREATE TABLE windows (id TEXT PRIMARY KEY, work TEXT, language TEXT, ref_start TEXT, ref_end TEXT, gist TEXT);
        CREATE TABLE edges (window_a TEXT, window_b TEXT, score REAL, work_a TEXT, work_b TEXT, pos_a INTEGER, pos_b INTEGER);
        CREATE TABLE work_pairs (work_a TEXT, work_b TEXT, lang_a TEXT, lang_b TEXT, count INTEGER, count_notrans INTEGER,
            is_translation_curated INTEGER, is_translation_heuristic INTEGER, PRIMARY KEY (work_a, work_b));
        CREATE TABLE author_pairs (author_a TEXT, author_b TEXT, lang_a TEXT, lang_b TEXT, count INTEGER, count_notrans INTEGER);
        CREATE TABLE century_pairs (lang_pair TEXT, century_a INTEGER, century_b INTEGER, label_a TEXT, label_b TEXT, count INTEGER, count_notrans INTEGER);
        CREATE TABLE genre_pairs (genre_a TEXT, genre_b TEXT, count INTEGER, count_notrans INTEGER);
    ''')
    c.execute("INSERT INTO meta VALUES ('index_fingerprint', '\"old\"')")
    for w, lang, auth, cent, genre in (('a.w', 'la', 'A', 1, 'epic'), ('g.h', 'grc', 'G', -8, 'epic'), ('f.d', 'fa', 'F', 14, 'lyric')):
        c.execute('INSERT INTO works VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (w, lang, auth.lower(), auth, 0, 'e', cent, 'c', genre, 10, 99, 9.9))
        c.execute('INSERT INTO windows VALUES (?,?,?,?,?,?)', (w + ':0', w, lang, '1', '2', 'g'))
    c.executemany('INSERT INTO edges VALUES (?,?,?,?,?,?,?)', [
        ('a.w:0', 'g.h:0', 0.9, 'a.w', 'g.h', 0, 0), ('a.w:0', 'f.d:0', 0.9, 'a.w', 'f.d', 0, 0)])
    c.executemany('INSERT INTO work_pairs VALUES (?,?,?,?,?,?,?,?)', [
        ('a.w', 'g.h', 'la', 'grc', 4, 4, 0, 0), ('a.w', 'f.d', 'la', 'fa', 7, 7, 0, 0)])
    c.commit(); c.close()
    dst = tmp_path / 'filtered.db'
    fpi.filter_map(str(src), str(dst), {'la', 'grc'}, set(), '1.2')
    d = sqlite3.connect(dst)
    assert {r[0] for r in d.execute('SELECT work FROM works')} == {'a.w', 'g.h'}
    assert d.execute('SELECT COUNT(*) FROM edges').fetchone()[0] == 1
    assert d.execute('SELECT COUNT(*) FROM windows').fetchone()[0] == 2
    assert d.execute('SELECT count FROM work_pairs').fetchall() == [(4,)]
    assert d.execute("SELECT total_links FROM works WHERE work='a.w'").fetchone()[0] == 4
    assert d.execute('SELECT count FROM genre_pairs').fetchall() == [(4,)]
    assert d.execute('SELECT SUM(count) FROM author_pairs').fetchone()[0] == 4
    assert json.loads(d.execute("SELECT value FROM meta WHERE key='index_fingerprint'").fetchone()[0]) == '1.2'
