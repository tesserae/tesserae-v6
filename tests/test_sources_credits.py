import json
from pathlib import Path

PATH = Path(__file__).parent.parent / 'data' / 'sources_credits.json'
REQUIRED = ('collection', 'name', 'url', 'licence_name')


def test_every_record_has_required_fields():
    records = json.loads(PATH.read_text(encoding='utf-8'))
    assert records
    for rec in records:
        for key in REQUIRED:
            assert rec.get(key), f"{rec.get('name')!r} lacks {key}"
    names = [r['name'] for r in records]
    assert len(names) == len(set(names))


def test_endpoint_returns_records():
    from backend.blueprints.corpus import corpus_bp
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(corpus_bp, url_prefix='/api')
    resp = app.test_client().get('/api/sources-credits')
    assert resp.status_code == 200
    assert resp.get_json()['total'] == len(json.loads(PATH.read_text(encoding='utf-8')))
