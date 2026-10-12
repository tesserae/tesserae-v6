"""backend/scholarship_recent.py and GET /passages/recent-scholarship, the services faked."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import scholarship as sch  # noqa: E402
from backend import scholarship_recent as sr  # noqa: E402

A = {'work': 'vergil.aeneid', 'author': 'Vergil', 'title': 'Aeneid', 'abbrev': 'Aeneid', 'locus': '', 'lo': '', 'hi': ''}
Q = 'Dido falls in love with Aeneas'


def item(title, abstract='', doi=None, year=2010, **kw):
    return dict({'title': title, 'authors': ['A. Scholar'], 'year': year, 'venue': 'Classical Quarterly',
                 'doi': doi, 'abstract': abstract, 'source': 'openalex'}, **kw)


def _words():
    return sr._question_words_for_match(Q, A)


def test_content_words_and_stem_prefix():
    assert sr.content_words(Q) == ['dido', 'falls', 'love', 'aeneas']
    assert sr._matched("Dido's passion and the loves of Aeneas", ['dido', 'love', 'mutiny']) == {'dido', 'love'}
    assert sr._matched('the mutinies of the legions', ['mutiny']) == {'mutiny'}


def test_filter_keeps_author_with_question_word():
    out = sr._filter([item('Love in Vergil', 'Dido and desire in the Aeneid.')], A, _words())
    assert len(out) == 1 and out[0]['score'] >= 1 and 'Dido' in out[0]['excerpt']


def test_filter_drops_author_without_question_word():
    assert sr._filter([item('Vergil and the Georgics', 'Farming and bees in Vergil.')], A, _words()) == []


def test_filter_drops_question_word_without_author_or_title():
    assert sr._filter([item('Love in Ovid', 'Dido appears in the Heroides.')], A, _words()) == []


def test_filter_drops_no_title_and_dedupes_by_doi_then_title():
    items = [item('', 'Vergil Dido', doi='10.1/a'),
             item('Dido in Vergil', 'Vergil on Dido', doi='10.1/B'),
             item('Dido and Vergil again', 'Vergil on Dido', doi='10.1/b'),
             item('Dido in Vergil', 'Vergil on Dido', doi=None)]
    out = sr._filter(items, A, _words())
    assert [i['title'] for i in out] == ['Dido in Vergil']


def test_merge_dedupes_across_services_and_orders():
    one = [{'title': 'X on Dido', 'doi': '10.1/x', 'year': 2001, 'score': 1, 'oa_url': None, 'excerpt': ''}]
    two = [{'title': 'X on Dido', 'doi': '10.1/X', 'year': 2001, 'score': 1, 'oa_url': 'http://free', 'excerpt': 'e'},
           {'title': 'Y on Dido and love', 'doi': None, 'year': 1999, 'score': 2, 'oa_url': None, 'excerpt': ''}]
    out = sr.merge([one, two])
    assert [i['title'] for i in out] == ['Y on Dido and love', 'X on Dido']
    assert out[1]['oa_url'] == 'http://free'


def _fake_names(monkeypatch):
    monkeypatch.setattr(sr, 'work_names_dict', lambda work: dict(A))
    monkeypatch.setattr(sch, '_unpaywall', lambda doi: {'oa_url': 'http://free/' + doi})


def test_recent_openalex_filters_and_adds_free_copy(monkeypatch):
    _fake_names(monkeypatch)
    seen = []
    monkeypatch.setattr(sch, '_openalex', lambda q: seen.append(q) or [
        item('Love in Vergil', 'Dido and desire in the Aeneid.', doi='10.1/love'),
        item('Bees', 'Georgics only, by Vergil.')])
    out = sr.recent(Q, 'vergil.aeneid', 'openalex')
    assert seen == ['Vergil Aeneid ' + Q]
    assert out['available'] and [i['title'] for i in out['results']] == ['Love in Vergil']
    assert out['results'][0]['oa_url'] == 'http://free/10.1/love'


def test_recent_unkeyed_services_are_off(monkeypatch):
    _fake_names(monkeypatch)
    monkeypatch.setattr(sch, 'S2_API_KEY', '')
    monkeypatch.setattr(sch, 'GOOGLE_BOOKS_KEY', '')
    for s in ('s2', 'books'):
        out = sr.recent(Q, 'vergil.aeneid', s)
        assert out == {'service': s, 'available': False, 'results': [], 'reason': 'off'}
        assert sr.state(out) == 'off'


def test_core_falls_back_to_quoted_words_when_and_form_is_refused(monkeypatch):
    import requests
    _fake_names(monkeypatch)
    forms = []

    def fake(query, a, words):
        forms.append(query)
        if len(forms) == 1:
            raise requests.HTTPError('500')
        return [item('Love in Vergil', 'Dido and desire in the Aeneid.', source='core')]
    monkeypatch.setattr(sr, '_core_items', fake)
    out = sr.recent(Q, 'vergil.aeneid', 'core')
    assert len(forms) == 2 and '"dido" AND "falls" AND "love"' in forms[1]
    assert out['results'][0]['title'] == 'Love in Vergil'


def test_route_service_that_raises_is_available_false_status_200(monkeypatch):
    _fake_names(monkeypatch)

    def boom(q):
        raise RuntimeError('http://x/?key=SECRET')
    monkeypatch.setattr(sch, '_crossref', boom)
    r = app.test_client().get('/api/passages/recent-scholarship', query_string={
        'question': Q, 'work': 'vergil.aeneid', 'service': 'crossref'})
    assert r.status_code == 200
    d = json.loads(r.get_data())
    assert d['available'] is False and d['results'] == [] and d['reason'] == 'the service did not answer'
    assert 'SECRET' not in r.get_data(as_text=True)


def test_route_answers_items_and_rejects_unknown_service(monkeypatch):
    _fake_names(monkeypatch)
    monkeypatch.setattr(sch, '_crossref', lambda q: [item('Love in Vergil', 'Dido in the Aeneid.', source='crossref')])
    c = app.test_client()
    d = json.loads(c.get('/api/passages/recent-scholarship', query_string={
        'question': Q, 'work': 'vergil.aeneid', 'service': 'crossref'}).get_data())
    assert d['service'] == 'crossref' and d['available'] and len(d['results']) == 1
    r = c.get('/api/passages/recent-scholarship', query_string={'question': Q, 'work': 'vergil.aeneid', 'service': 'nope'})
    assert r.status_code == 200 and json.loads(r.get_data())['available'] is False
