"""GET /api/texts/structure/<work>: a work's story list for the Reader."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from flask import Flask  # noqa: E402

from backend.blueprints import corpus as corpus_mod  # noqa: E402


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(corpus_mod.corpus_bp, url_prefix='/api')
    with app.test_client() as c:
        yield c


def test_shahnameh_stories(client):
    r = client.get('/api/texts/structure/ferdowsi.shahnameh')
    assert r.status_code == 200
    d = r.get_json()
    assert d['work'] == 'ferdowsi.shahnameh' and d['unit'] == 'story'
    assert len(d['sections']) == 857
    s = d['sections'][150]
    assert s['number'] == 151
    assert s['first_ref'] == 'ferdowsi.shahnameh.151.1.1'
    assert {'title_en', 'title_fa', 'last_ref', 'n_couplets'} <= set(s)
    assert 'ganjoor_poem_id' not in s


@pytest.mark.parametrize('work', ['verg.aen', 'no.such.work', '..', 'Ferdowsi.Shahnameh', 'a..b'])
def test_no_structure_is_404(client, work):
    r = client.get(f'/api/texts/structure/{work}')
    assert r.status_code == 404
    if r.is_json:
        assert r.get_json() == {'error': 'no structure'}


def _write(tmp_path, monkeypatch, work, name, data):
    import json
    folder = tmp_path / work
    folder.mkdir()
    (folder / name).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(corpus_mod, 'TEXT_STRUCTURE_DIR', tmp_path)


MASNAVI = [
    {"major": 1, "title": "بخش ۱ - سرآغاز", "full_title": "مولانا » مثنوی معنوی » دفتر اول » بخش ۱ - سرآغاز",
     "ganjoor_poem_id": 7893, "first_ref": "rumi.masnavi.1.1.1", "last_ref": "rumi.masnavi.1.34.2",
     "source_name": "ویکی‌درج"},
    {"major": 1, "title": "بخش ۲ - عاشق شدن", "full_title": "مولانا » مثنوی معنوی » دفتر اول » بخش ۲ - عاشق شدن",
     "ganjoor_poem_id": 7894, "first_ref": "rumi.masnavi.1.35.1", "last_ref": "rumi.masnavi.1.54.2",
     "source_name": "ویکی‌درج"},
    {"major": 2, "title": "بخش ۱ - آغاز", "full_title": "مولانا » مثنوی معنوی » دفتر دوم » بخش ۱ - آغاز",
     "ganjoor_poem_id": 7990, "first_ref": "rumi.masnavi.2.1.1", "last_ref": "rumi.masnavi.2.9.2",
     "source_name": "ویکی‌درج"},
]

BAGH = {"sections": [
    {"section": 1, "page": "باغ و بہار/آغاز", "revid": 2100,
     "first_ref": "mir_amman.bagh_o_bahar.1.1", "last_ref": "mir_amman.bagh_o_bahar.1.9", "paragraphs": 9},
    {"section": 2, "page": "باغ و بہار/سبب تالیف کتاب", "revid": 2095,
     "first_ref": "mir_amman.bagh_o_bahar.2.1", "last_ref": "mir_amman.bagh_o_bahar.2.7", "paragraphs": 7},
], "left_out": "x"}


def test_verse_sections(client, tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, 'rumi.masnavi', 'sections.json', MASNAVI)
    d = client.get('/api/texts/structure/rumi.masnavi').get_json()
    assert d['unit'] == 'section' and [s['number'] for s in d['sections']] == [1, 2, 3]
    assert [s['reign_fa'] for s in d['sections']] == ['دفتر اول', 'دفتر اول', 'دفتر دوم']
    assert d['sections'][1]['title_fa'] == 'بخش ۲ - عاشق شدن'
    assert d['sections'][2]['label'] == 2 and 'label' not in d['sections'][0]
    assert d['sections'][0]['first_ref'] == 'rumi.masnavi.1.1.1'
    assert 'title_en' not in d['sections'][0] and 'n_couplets' not in d['sections'][0]
    assert 'ganjoor_poem_id' not in d['sections'][0] and 'full_title' not in d['sections'][0]


def test_verse_sections_without_full_title_and_own_majors(client, tmp_path, monkeypatch):
    gul = [{"major": 0, "story": 1, "title": "دیباچه", "first_ref": "a.0.1.1", "last_ref": "a.0.1.9"},
           {"major": 1, "story": 1, "title": "حکایت ۱", "first_ref": "a.1.1.1", "last_ref": "a.1.1.9"},
           {"major": 1, "story": 2, "title": "حکایت ۲", "first_ref": "a.1.2.1", "last_ref": "a.1.2.9"}]
    _write(tmp_path, monkeypatch, 'saadi.gulistan', 'sections.json', gul)
    d = client.get('/api/texts/structure/saadi.gulistan').get_json()
    assert [s['reign_fa'] for s in d['sections']] == ['دیباچه', 'باب 1', 'باب 1']
    own = [{"major": 1, "title": "x", "first_ref": "t.1.1"}, {"major": 2, "title": "y", "first_ref": "t.2.1"}]
    (tmp_path / 'saadi.gulistan' / 'sections.json').unlink()
    (tmp_path / 'saadi.gulistan').rmdir()
    _write(tmp_path, monkeypatch, 'attar.tazkirat_al_awliya', 'sections.json', own)
    d = client.get('/api/texts/structure/attar.tazkirat_al_awliya').get_json()
    assert all('reign_fa' not in s for s in d['sections'])


def test_prose_sections(client, tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, 'mir_amman.bagh_o_bahar', 'sections.json', BAGH)
    d = client.get('/api/texts/structure/mir_amman.bagh_o_bahar').get_json()
    assert d['unit'] == 'section'
    s = d['sections']
    assert [x['number'] for x in s] == [1, 2]
    assert s[0]['title_fa'] == 'آغاز' and s[1]['title_fa'] == 'سبب تالیف کتاب'
    assert s[0]['n_units'] == 9 and 'n_couplets' not in s[0] and 'reign_fa' not in s[0]
    assert 'label' not in s[0] and 'revid' not in s[0]


def test_prose_zero_based_keeps_label(client, tmp_path, monkeypatch):
    data = {"sections": [{"section": 0, "page": "چهار مقاله/مقدمه", "first_ref": "n.0.1", "paragraphs": 24},
                         {"section": 1, "page": "چهار مقاله/مقالت اول", "first_ref": "n.1.1", "paragraphs": 23}]}
    _write(tmp_path, monkeypatch, 'nizami_arudi.chahar_maqala', 'sections.json', data)
    s = client.get('/api/texts/structure/nizami_arudi.chahar_maqala').get_json()['sections']
    assert [x['number'] for x in s] == [1, 2] and [x['label'] for x in s] == [0, 1]


def test_stories_json_wins_and_stays_story(client, tmp_path, monkeypatch):
    stories = [{"number": 1, "title_en": "A", "title_fa": "ب", "reign_fa": "ج", "first_ref": "w.1.1.1",
                "last_ref": "w.1.2.2", "n_couplets": 2, "extra": 1}]
    _write(tmp_path, monkeypatch, 'w.x', 'stories.json', stories)
    (tmp_path / 'w.x' / 'sections.json').write_text('[]', encoding='utf-8')
    d = client.get('/api/texts/structure/w.x').get_json()
    assert d['unit'] == 'story' and d['sections'] == [{k: v for k, v in stories[0].items() if k != 'extra'}]
