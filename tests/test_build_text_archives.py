"""The per-language text archives: the restricted file is left out, the manifest
has the right rows and licenses, and the download route serves the static archive
when it exists and zips on the fly only when it does not."""
import csv
import importlib.util
import io
import json
import os
import tarfile
import zipfile
from io import BytesIO

import pytest
from flask import Flask

import backend.restricted_texts as restricted_texts

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'build_text_archives', os.path.join(HERE, '..', 'scripts', 'corpus', 'build_text_archives.py'))
bta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bta)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / 'restricted_texts.json'
    path.write_text(json.dumps({'texts': {'heldwork.history': {
        'holder': 'Test', 'credit': 'c', 'license': 'indexing only', 'added': '2026-10-01', 'ends': None}}}))
    monkeypatch.setattr(restricted_texts, 'REGISTRY_PATH', path)
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}
    yield
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}


@pytest.fixture
def texts_root(tmp_path):
    d = tmp_path / 'texts' / 'la'
    d.mkdir(parents=True)
    (d / 'heldwork.history.tess').write_text('<h. 1.1>\twithheld\n')
    (d / 'ordinary.poem.tess').write_text('<o. 1.1>\tone\n<o. 1.2>\ttwo\n')
    (d / 'nocredit.poem.tess').write_text('<n. 1.1>\tonly\n')
    (d / 'nclicensed.poem.tess').write_text('<c. 1.1>\ta\n<c. 1.2>\tb\n<c. 1.3>\tc\n')
    (d / 'offlineonly.poem.tess').write_text('<f. 1.1>\tpaper\n')
    return tmp_path / 'texts'


@pytest.fixture
def index():
    return bta.SourceIndex([
        {'author': 'Ordinary', 'work': 'Poem', 'e_source': 'Perseus', 'e_source_url': 'http://x.example/p',
         'print_source': 'Oxford 1900', 'license': 'CC BY-SA 4.0'},
        {'author': 'Nclicensed', 'work': 'Poem', 'e_source': 'Site', 'e_source_url': 'http://y.example',
         'print_source': 'Print', 'license': 'CC BY-NC-SA 4.0'},
        {'author': 'Offlineonly', 'work': 'Poem', 'e_source': 'Musisque Deoque',
         'e_source_url': 'http://www.mqdq.it/', 'print_source': 'Print',
         'license': 'Noncommercial use only, copies on paper or offline media'},
    ])


def test_archive_leaves_out_restricted_and_writes_manifest(tmp_path, registry, texts_root, index):
    out = tmp_path / 'out'
    r = bta.build_language('la', str(texts_root), str(out), index, '2026-10-25', {'la': 'Latin'})
    assert (r['files'], r['restricted'], r['no_credit_row'], r['noncommercial']) == (3, 1, 1, 1)
    with tarfile.open(out / 'texts_la.tar.gz') as tf:
        names = tf.getnames()
        assert 'texts_la/ordinary.poem.tess' in names
        assert 'texts_la/heldwork.history.tess' not in names
        assert 'texts_la/offlineonly.poem.tess' not in names
        assert 'texts_la/MANIFEST.tsv' in names and 'texts_la/README.txt' in names
        inner = tf.extractfile('texts_la/MANIFEST.tsv').read()
        readme = tf.extractfile('texts_la/README.txt').read().decode()
    beside = (out / 'texts_la_manifest.tsv').read_bytes()
    assert inner == beside
    assert 'noncommercial use only' in readme and '1 file(s) have no credit row' in readme
    assert r['withheld_by_terms'] == 1 and '1 from Musisque Deoque' in readme
    rows = {r['file']: r for r in csv.DictReader(io.StringIO(beside.decode()), delimiter='\t')}
    assert set(rows) == {'ordinary.poem.tess', 'nocredit.poem.tess', 'nclicensed.poem.tess'}
    ok = rows['ordinary.poem.tess']
    assert (ok['lines'], ok['license'], ok['noncommercial_only'], ok['archive_date']) == (
        '2', 'CC BY-SA 4.0', 'no', '2026-10-25')
    assert ok['electronic_source'] == 'Perseus' and ok['print_source'] == 'Oxford 1900'
    assert rows['nocredit.poem.tess']['license'] == 'unknown'
    assert rows['nclicensed.poem.tess']['noncommercial_only'] == 'yes'
    assert not list(out.glob('*.new'))


def test_row_without_license_field_is_not_stated(tmp_path, registry, texts_root):
    idx = bta.SourceIndex([{'author': 'Ordinary', 'work': 'Poem', 'e_source': 'Perseus'}])
    row, matched, withheld = bta.manifest_row(str(texts_root / 'la' / 'ordinary.poem.tess'),
                                              'ordinary.poem.tess', idx, '2026-10-25')
    assert matched and row['license'] == bta.NOT_STATED and withheld is None


def test_withheld_sources_match_name_or_address():
    assert bta.withheld_reason({'e_source': 'MQDQ', 'e_source_url': ''}).startswith('Musisque Deoque')
    assert bta.withheld_reason({'e_source': 'Corpus Thomisticum'}).startswith('Corpus Thomisticum')
    assert bta.withheld_reason({'e_source': '', 'e_source_url': 'http://www.augustinus.it/latino/x.htm'}
                               ).startswith('augustinus.it')
    assert bta.withheld_reason({'e_source': 'Perseus', 'e_source_url': 'http://x'}) is None
    assert bta.withheld_reason(None) is None


@pytest.fixture
def client(tmp_path, registry, texts_root, monkeypatch):
    from backend.blueprints import downloads as dm
    monkeypatch.setattr(dm, 'TEXTS_DIR', str(texts_root))
    monkeypatch.setattr(dm, 'PUBLIC_DATA_DIR', str(tmp_path / 'public_data'))
    app = Flask(__name__)
    app.register_blueprint(dm.downloads_bp, url_prefix='/api')
    return app.test_client()


def test_route_serves_static_archive_when_present(tmp_path, client):
    pd = tmp_path / 'public_data'
    pd.mkdir()
    (pd / 'texts_la.tar.gz').write_bytes(b'ARCHIVE-BYTES')
    resp = client.get('/api/downloads/texts/la')
    assert resp.status_code == 200
    assert resp.data == b'ARCHIVE-BYTES'
    assert 'texts_la.tar.gz' in resp.headers['Content-Disposition']


def test_route_falls_back_to_zip_without_restricted(client):
    resp = client.get('/api/downloads/texts/la')
    assert resp.status_code == 200
    assert 'X-Tesserae-Restricted-Withheld' in resp.headers
    with zipfile.ZipFile(BytesIO(resp.data)) as zf:
        names = zf.namelist()
    assert any(n.endswith('ordinary.poem.tess') for n in names)
    assert not any(n.endswith('heldwork.history.tess') for n in names)
