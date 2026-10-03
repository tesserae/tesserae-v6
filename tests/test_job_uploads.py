"""A cluster job returns its result file through /api/jobs/upload (2026-10-03)."""
import hashlib
import os

import pytest

from backend.blueprints import job_uploads


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(job_uploads, 'UPLOAD_ROOT', str(tmp_path))
    os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
    from backend.app import app
    app.config['TESTING'] = True
    (tmp_path / 'embed-1').mkdir()
    (tmp_path / 'embed-1' / '.token').write_text('secret-token\n')
    with app.test_client() as c:
        yield c, tmp_path


def test_right_token_stores_the_file_and_reports_its_hash(client):
    c, root = client
    body = b'x' * 10000
    r = c.put('/api/jobs/upload/embed-1/part-000.npy', data=body, headers={'X-Job-Token': 'secret-token'})
    assert r.status_code == 200, r.data
    assert r.json['bytes'] == 10000 and r.json['sha256'] == hashlib.sha256(body).hexdigest()
    assert (root / 'embed-1' / 'part-000.npy').read_bytes() == body
    assert [f.name for f in (root / 'embed-1').iterdir() if f.name.endswith('.part')] == []


def test_wrong_or_missing_token_is_refused(client):
    c, root = client
    assert c.put('/api/jobs/upload/embed-1/a.bin', data=b'x', headers={'X-Job-Token': 'nope'}).status_code == 403
    assert c.put('/api/jobs/upload/embed-1/a.bin', data=b'x').status_code == 403
    assert c.put('/api/jobs/upload/other-job/a.bin', data=b'x', headers={'X-Job-Token': 'secret-token'}).status_code == 403
    assert not (root / 'embed-1' / 'a.bin').exists()


def test_names_cannot_walk_the_tree(client):
    c, root = client
    assert c.put('/api/jobs/upload/embed-1/.token', data=b'x', headers={'X-Job-Token': 'secret-token'}).status_code == 400
    assert c.put('/api/jobs/upload/embed-1/..%2Fescape', data=b'x', headers={'X-Job-Token': 'secret-token'}).status_code in (400, 404, 405)
    assert (root / 'embed-1' / '.token').read_text().strip() == 'secret-token'
    assert not (root / 'escape').exists() and not (root / 'embed-1' / 'escape').exists()


def test_oversize_declared_upload_is_refused(client, monkeypatch):
    c, root = client
    monkeypatch.setattr(job_uploads, 'MAX_BYTES', 100)
    r = c.put('/api/jobs/upload/embed-1/big.bin', data=b'x' * 200, headers={'X-Job-Token': 'secret-token'})
    assert r.status_code == 413
    assert not (root / 'embed-1' / 'big.bin').exists()
