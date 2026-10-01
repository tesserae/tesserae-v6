"""A restricted text must never leave the server in a bundle: not the
per-language texts download, not a release export.

backend/blueprints/downloads.py and scripts/build_passage_index_release.py are
the two places that package texts/ (or data derived from it) for someone to
take away. Both are tested here against a throwaway registry entry and
throwaway files, since the real registry is empty and this guarantee has to
hold before the first real entry arrives.
"""
import json
import os
import sys
import zipfile
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest  # noqa: E402
from flask import Flask  # noqa: E402

import backend.restricted_texts as restricted_texts  # noqa: E402


@pytest.fixture
def fixture_registry(tmp_path, monkeypatch):
    """A registry with one restricted work, pointed at by the module under
    test instead of the real (empty) data/restricted_texts.json."""
    registry_path = tmp_path / 'restricted_texts.json'
    registry_path.write_text(json.dumps({
        'texts': {
            'heldwork.history': {
                'holder': 'Test Licence Holder',
                'credit': 'Source: Test Licence Holder (example.invalid)',
                'license': 'indexing and search only; no redistribution',
                'added': '2026-10-01',
                'ends': None,
            }
        }
    }))
    monkeypatch.setattr(restricted_texts, 'REGISTRY_PATH', registry_path)
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}
    yield
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}


@pytest.fixture
def fixture_texts(tmp_path):
    lang_dir = tmp_path / 'texts' / 'la'
    lang_dir.mkdir(parents=True)
    (lang_dir / 'heldwork.history.tess').write_text('<line> withheld </line>\n')
    (lang_dir / 'ordinary.poem.tess').write_text('<line> open </line>\n')
    return tmp_path / 'texts'


# ---------------------------------------------------------------------------
# create_zip_from_directory: the low-level function both the texts zip and
# (if it is ever reused) another bundler would call.
# ---------------------------------------------------------------------------
def test_create_zip_skips_restricted_and_notes_the_withholding(fixture_texts):
    from backend.blueprints.downloads import create_zip_from_directory

    buf = create_zip_from_directory(
        str(fixture_texts / 'la'), prefix='texts_la',
        skip_files={'heldwork.history.tess'})
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        assert 'texts_la/ordinary.poem.tess' in names
        assert 'texts_la/heldwork.history.tess' not in names
        assert 'texts_la/README_RESTRICTED.txt' in names
        note = zf.read('texts_la/README_RESTRICTED.txt').decode('utf-8')
        assert '1 text' in note
        assert 'indexing and search only' in note


def test_create_zip_with_no_skips_adds_no_readme(fixture_texts):
    from backend.blueprints.downloads import create_zip_from_directory

    buf = create_zip_from_directory(str(fixture_texts / 'la'), prefix='texts_la')
    with zipfile.ZipFile(buf) as zf:
        assert 'texts_la/README_RESTRICTED.txt' not in zf.namelist()


# ---------------------------------------------------------------------------
# The actual routes
# ---------------------------------------------------------------------------
@pytest.fixture
def downloads_app(fixture_texts, fixture_registry, monkeypatch):
    from backend.blueprints import downloads as downloads_mod
    monkeypatch.setattr(downloads_mod, 'TEXTS_DIR', str(fixture_texts))
    app = Flask(__name__)
    app.register_blueprint(downloads_mod.downloads_bp, url_prefix='/api')
    return app.test_client()


def test_download_texts_route_withholds_restricted_file(downloads_app):
    resp = downloads_app.get('/api/downloads/texts/la')
    assert resp.status_code == 200
    assert 'X-Tesserae-Restricted-Withheld' in resp.headers
    assert 'indexing and search only' in resp.headers['X-Tesserae-Restricted-Withheld']
    with zipfile.ZipFile(BytesIO(resp.data)) as zf:
        names = zf.namelist()
        assert any(n.endswith('ordinary.poem.tess') for n in names)
        assert not any(n.endswith('heldwork.history.tess') for n in names)


def test_download_info_excludes_restricted_from_count(downloads_app):
    resp = downloads_app.get('/api/downloads/info')
    data = resp.get_json()
    assert data['texts']['la']['count'] == 1  # ordinary.poem only
    assert data['texts']['la']['restricted_withheld'] == 1
    assert 'indexing and search only' in data['texts']['la']['restricted_note']


# ---------------------------------------------------------------------------
# The passage-index release script
# ---------------------------------------------------------------------------
@pytest.fixture
def release_script(monkeypatch):
    """Import the release script as a module without running it (it has no
    `if __name__` guard, so import alone is safe; main() is called explicitly
    by each test, against monkeypatched paths)."""
    import importlib
    spec_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'scripts', 'build_passage_index_release.py')
    spec = importlib.util.spec_from_file_location('build_passage_index_release', spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_release_withholds_restricted_work_windows(tmp_path, fixture_registry, release_script):
    index_dir = tmp_path / 'index'
    index_dir.mkdir()
    out_dir = tmp_path / 'out'

    ids = ['la/heldwork.history:1-5', 'la/ordinary.poem:1-5']
    json.dump(ids, open(index_dir / 'ids.json', 'w'))
    np.save(index_dir / 'embeddings.npy', np.zeros((2, 4), dtype=np.float32))
    with open(index_dir / 'descriptions.jsonl', 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'id': ids[0], 'language': 'la', 'work': 'heldwork.history',
                             'desc': {'gist': 'withheld'}}) + '\n')
        fh.write(json.dumps({'id': ids[1], 'language': 'la', 'work': 'ordinary.poem',
                             'desc': {'gist': 'open'}}) + '\n')

    release_script.INDEX = str(index_dir)
    release_script.OUT = str(out_dir)
    release_script.main()

    la_dir = out_dir / 'la'
    v_ids = json.load(open(la_dir / 'ids.json'))
    assert v_ids == ['la/ordinary.poem:1-5']
    manifest = json.load(open(la_dir / 'MANIFEST.json'))
    assert manifest['restricted_windows_withheld'] == 1
    assert manifest['windows'] == 1
