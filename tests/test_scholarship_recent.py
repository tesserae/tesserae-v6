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


# ------------------------------------------------------------ the tighter keep rule

def test_filter_drops_item_naming_the_work_only_in_core_full_text():
    milton = item('Paradise Lost and the epic tradition', 'Dido and desire in Milton.',
                  snippet='Dido echoes the Aeneid here.', names_work=True, source='core')
    assert sr._filter([milton], A, _words()) == []


def test_filter_drops_item_naming_the_work_only_in_a_book_snippet():
    book = item('Roman poetry', 'Dido in a survey.', snippet='Vergil, Aeneid 4', source='google_books')
    assert sr._filter([book], A, _words()) == []


def test_filter_does_not_count_abstract_text_beyond_1500_characters():
    late = item('Epic women', 'x ' * 800 + 'Vergil and Dido.')
    assert sr._filter([late], A, _words()) == []


def test_filter_drops_schoolbook_titles():
    for t in ('OCR Ancient History AS and A Level Component 2: Vergil', 'Vergil Revision Guide',
              'GCSE Latin: Aeneid', "Aeneid Student's Book", 'The Aeneid Workbook', 'Aeneid exam practice'):
        assert sr._filter([item(t, 'Dido in the Aeneid.')], A, _words()) == [], t


def test_title_naming_the_work_outranks_abstract_only_naming():
    commentary = item('Virgil, Aeneid 4: a commentary', 'Dido.', year=2020)
    milton = item('Dido and love in Paradise Lost', 'Milton reads the Aeneid and Dido and love.', year=2023)
    out = sr.order(sr._filter([milton, commentary], A, _words()))
    assert out[0]['title'].startswith('Virgil, Aeneid 4') and out[0]['title_names_work'] is True
    assert out[1]['title_names_work'] is False


def test_full_text_naming_breaks_ties_between_equal_items():
    a = item('Dido in Vergil', 'Dido.', year=2001)
    b = item('Dido in Vergil, too', 'Dido.', year=2001, snippet='the Aeneid says', names_work=True)
    out = sr.order(sr._filter([a, b], A, _words()))
    assert out[0]['title'] == 'Dido in Vergil, too'


# ------------------------------------------------------------ no work (Theme Search)

def test_no_work_keeps_two_question_words_with_one_in_the_title():
    two = item('Dido and Aeneas in love', 'Vergil.')
    abstract_only = item('A study of opera', 'Dido and Aeneas in a Vergil production.')
    one = item('Dido at Carthage', 'Vergil, nothing else.')
    out = sr._filter([two, abstract_only, one], None, sr.content_words(Q))
    assert [i['title'] for i in out] == ['Dido and Aeneas in love']


def test_no_work_short_question_needs_every_word():
    words = sr.content_words('plague Athens')
    assert [i['title'] for i in sr._filter([item('The plague of Athens', 'Thucydides.'), item('The plague', 'Thucydides.')], None, words)] == \
        ['The plague of Athens']


def test_no_work_orders_by_title_matches_then_question_words_then_year():
    words = sr.content_words(Q)
    items = [item('Dido and Aeneas', 'love falls Vergil', year=2001), item('Dido, Aeneas and love', 'Vergil', year=1990),
             item('Dido and Aeneas again', 'love falls Vergil', year=2020)]
    out = sr.order(sr._filter(items, None, words))
    assert [i['title'] for i in out] == ['Dido, Aeneas and love', 'Dido and Aeneas again', 'Dido and Aeneas']


def test_recent_without_a_work_asks_with_the_question_alone(monkeypatch):
    seen = []
    monkeypatch.setattr(sch, '_openalex', lambda q: seen.append(q) or [item('Dido and Aeneas in love', 'Vergil')])
    monkeypatch.setattr(sch, '_unpaywall', lambda doi: None)
    out = sr.recent(Q, None, 'openalex')
    assert seen == [Q] and len(out['results']) == 1


def test_route_work_is_optional(monkeypatch):
    monkeypatch.setattr(sch, '_crossref', lambda q: [item('Dido and Aeneas in love', 'Vergil', source='crossref')])
    monkeypatch.setattr(sch, '_unpaywall', lambda doi: None)
    d = json.loads(app.test_client().get('/api/passages/recent-scholarship', query_string={
        'question': Q, 'service': 'crossref'}).get_data())
    assert d['available'] and len(d['results']) == 1


def test_core_forms_without_a_work_have_no_author_group():
    assert sr._core_query_forms(['dido', 'love'], None) == ['dido AND love', '"dido" AND "love"']


# ------------------------------------------------------------ Google Books: one retry

def _http_error(code):
    import requests
    r = requests.Response()
    r.status_code = code
    return requests.HTTPError('boom', response=r)


BOOK = {'items': [{'volumeInfo': {'title': 'Aeneid commentary', 'authors': ['A. B.'], 'publishedDate': '2020',
                                  'description': 'Dido in the Aeneid.'}}]}


def test_books_retries_once_after_a_503(monkeypatch, tmp_path):
    monkeypatch.setattr(sch, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(sch.time, 'sleep', lambda s: None)
    monkeypatch.setattr(sch, 'GOOGLE_BOOKS_KEY', 'k')
    calls = []

    def fake(url, params):
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(503)
        return BOOK
    monkeypatch.setattr(sch, '_get', fake)
    assert len(sr._books_items('Vergil Aeneid Dido')) == 1 and len(calls) == 2


def test_books_two_failures_answer_available_false(monkeypatch, tmp_path):
    monkeypatch.setattr(sch, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(sch.time, 'sleep', lambda s: None)
    monkeypatch.setattr(sch, 'GOOGLE_BOOKS_KEY', 'k')
    monkeypatch.setattr(sr, 'work_names_dict', lambda work: dict(A))
    calls = []

    def fake(url, params):
        calls.append(1)
        raise _http_error(503)
    monkeypatch.setattr(sch, '_get', fake)
    out = sr.recent_safe(Q, 'vergil.aeneid', 'books')
    assert out['available'] is False and len(calls) == 2


def test_get_retry_does_not_retry_a_4xx(monkeypatch):
    calls = []

    def fake(url, params):
        calls.append(1)
        raise _http_error(403)
    monkeypatch.setattr(sch, '_get', fake)
    import pytest
    import requests
    with pytest.raises(requests.HTTPError):
        sch._get_retry('https://x.example/y', {})
    assert len(calls) == 1


def test_reader_books_retries_once_after_a_503(monkeypatch, tmp_path):
    monkeypatch.setattr(sch, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(sch.time, 'sleep', lambda s: None)
    monkeypatch.setattr(sch, 'GOOGLE_BOOKS_KEY', 'k')
    calls = []

    def fake(url, params):
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(503)
        return {'items': [{'id': 'b1', 'volumeInfo': {'title': 'Aeneid commentary', 'authors': ['A. B.'],
                                                       'publishedDate': '2020'},
                           'searchInfo': {'textSnippet': 'Vergil, Aeneid 1.1 arma'}}]}
    monkeypatch.setattr(sch, '_get', fake)
    p = {'work': 'vergil.aeneid', 'author': 'Vergil', 'title': 'Aeneid', 'abbrev': 'Aen.', 'lo': '1.1', 'hi': '1.1'}
    out = sch.books(p)
    assert out['available'] and len(out['results']) == 1 and len(calls) == 3  # 503, ok, ok (second query, same book)


def test_no_work_needs_a_classics_signal():
    words = sr.content_words(Q)
    bare = item('Dido and Aeneas in love', 'A staging of the opera.')
    with_title = item('Dido and Aeneas in love', 'A staging of the opera. Compare the Odyssey.')
    with_author = item('Dido and Aeneas in love', 'Vergil is the source.')
    assert sr._filter([bare], None, words) == []
    assert len(sr._filter([with_title], None, words)) == 1
    assert len(sr._filter([with_author], None, words)) == 1
    # a work-aware search does not need the signal
    assert len(sr._filter([item('Dido and Aeneas in the Aeneid', 'x')], A, _words())) == 1


def test_signal_names_leave_out_ordinary_words():
    names = sr._author_names()
    assert 'homer' in names or 'vergil' in names
    assert not {'young', 'gray', 'pope', 'swift', 'blake'} & names
