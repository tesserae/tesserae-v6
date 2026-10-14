"""POST /passages/ask-scholarship with the search and the model faked."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend.assistant import model  # noqa: E402
from backend import scholarship_theme  # noqa: E402
from backend.blueprints import passages  # noqa: E402
from backend import scholarship_recent  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def no_live_services(monkeypatch):
    """No test reaches the network: every live service answers 'none' unless a test says otherwise."""
    monkeypatch.setattr(scholarship_recent, 'recent_safe',
                        lambda q, w, s: {'service': s, 'available': True, 'results': [], 'reason': ''})


def note(work, who='Servius', ref='verg. aen. 4.1', text='Dido burns with love.'):
    return {'kind': 'commentary', 'work': work, 'commentator': who, 'ref_start': ref,
            'snippet': text, 'link': {'kind': 'reader', 'url': '/read?x'}, 'title': None, 'year': None}


def article(title, text, year=1890):
    return {'kind': 'article', 'work': None, 'title': title, 'snippet': text, 'year': year,
            'journal': 'The Classical Review', 'commentator': None,
            'link': {'kind': 'jstor', 'url': 'https://www.jstor.org/stable/9'}}


def _post(body):
    r = app.test_client().post('/api/passages/ask-scholarship', json=body)
    assert r.status_code == 200
    return json.loads(r.get_data())


def _setup(monkeypatch, cards, calls=None):
    monkeypatch.setattr(scholarship_theme, 'theme', lambda q, k=0, d=None: {'results': cards})
    monkeypatch.setattr(model, 'is_available', lambda: True)

    def fake(system, user, max_tokens=0, temperature=0):
        if calls is not None:
            calls.append((system, user))
        return 'The notes listed say she is overcome [1] and the article agrees [2].'
    monkeypatch.setattr(model, 'complete', fake)


def test_filter_keeps_note_on_the_work_and_drops_other_work(monkeypatch):
    kept, _ = passages._scholarship_keep(
        [note('vergil.aeneid.part.4'), note('ovid.heroides'), note('vergil.georgics')], 'vergil.aeneid')
    assert [c['work'] for c in kept] == ['vergil.aeneid.part.4']


def test_article_kept_only_when_it_names_the_author_or_title():
    cards = [article('On Virgil', 'a study of Virgil and his age'),
             article('On the Aeneid', 'the Aeneid in the schools'),
             article('On Sappho', 'a note on the Heroides of Ovid')]
    kept, _ = passages._scholarship_keep(cards, 'vergil.aeneid')
    assert [c['title'] for c in kept] == ['On Virgil', 'On the Aeneid']


def test_keeps_at_most_eight_in_order():
    cards = [note('vergil.aeneid', ref=f'verg. aen. 1.{i}') for i in range(12)]
    kept, _ = passages._scholarship_keep(cards, 'vergil.aeneid')
    assert len(kept) == 8 and kept[0]['ref_start'] == 'verg. aen. 1.0'


def test_holdings_stable_for_one_question_and_varies_across_questions():
    kept, info = passages._scholarship_keep([note('vergil.aeneid')], 'vergil.aeneid')
    a = [passages._scholarship_holdings(f'question {i}', kept, info, 'vergil.aeneid') for i in range(40)]
    assert len(set(a)) >= 4
    assert passages._scholarship_holdings('same', kept, info, 'vergil.aeneid') == \
        passages._scholarship_holdings('same', kept, info, 'vergil.aeneid')
    none = [passages._scholarship_holdings(f'question {i}', [], info, 'vergil.aeneid') for i in range(40)]
    assert len(set(none)) >= 4
    for s in a + none:
        assert ':' not in s and ';' not in s and '—' not in s


def test_nothing_kept_gives_unavailable_and_no_model_call(monkeypatch):
    calls = []
    _setup(monkeypatch, [note('ovid.heroides')], calls)
    out = _post({'question': 'jealousy', 'work': 'sappho.fragments', 'lang': 'grc'})
    assert out['available'] is False and out['holdings'] and 'summary' not in out
    assert calls == []


def test_answer_has_cites_with_labels_and_links(monkeypatch):
    calls = []
    _setup(monkeypatch, [note('vergil.aeneid.part.4'), article('On Virgil', 'Virgil at length')], calls)
    out = _post({'question': 'Dido in love', 'work': 'vergil.aeneid', 'lang': 'la'})
    assert out['available'] is True
    assert [c['n'] for c in out['cites']] == [1, 2]
    assert out['cites'][0]['label'] == 'Servius on verg. aen. 4.1'
    assert out['cites'][1]['label'] == 'On Virgil (1890)'
    assert out['cites'][1]['link']['kind'] == 'jstor'
    assert 'at most 120 words' in calls[0][0] and '[1] Servius' in calls[0][1]


def test_model_off_gives_holdings_only(monkeypatch):
    _setup(monkeypatch, [note('vergil.aeneid')])
    monkeypatch.setattr(model, 'is_available', lambda: False)
    out = _post({'question': 'Dido', 'work': 'vergil.aeneid', 'lang': 'la'})
    assert out['available'] is False and out['holdings']


def test_a_note_on_another_work_that_names_the_author_is_kept(monkeypatch):
    # 2026-10-12: Page on the Aeneid comparing Thucydides' plague counts as
    # secondary literature on Thucydides.
    from backend.blueprints import passages as bp
    from backend import passage_index as pi
    monkeypatch.setattr(pi, '_naming', lambda base: {'author': 'Thucydides', 'title': 'Peloponnesian War', 'display_name': 'Thucydides, Peloponnesian War'})
    cards = [
        {'kind': 'commentary', 'work': 'vergil.aeneid.part.3', 'snippet': 'Compare the plague in Thucydides ii. 47.', 'commentator': 'Page'},
        {'kind': 'commentary', 'work': 'vergil.aeneid.part.3', 'snippet': 'A note on the dative.', 'commentator': 'Page'},
        {'kind': 'article', 'title': 'On the plague', 'snippet': 'Lucretius alone is discussed.'},
    ]
    kept, info = bp._scholarship_keep(cards, 'thucydides.peleponnesian_war')
    assert len(kept) == 1 and kept[0]['snippet'].startswith('Compare')
    assert all('for this question' in x or 'this question' in x for x in bp._HOLDINGS_NONE)


def test_articles_hold_a_reserved_share_and_a_question_name_qualifies(monkeypatch):
    from backend.blueprints import passages as bp
    from backend import passage_index as pi
    monkeypatch.setattr(pi, '_naming', lambda base: {'author': 'Vergil', 'title': 'Aeneid', 'display_name': 'Vergil, Aeneid'})
    notes = [{'kind': 'commentary', 'work': 'vergil.aeneid.part.1', 'snippet': f'note {i}', 'commentator': 'Page'} for i in range(12)]
    arts = [{'kind': 'article', 'title': 'Fortuna in Latin Poetry', 'snippet': 'Dido and Aeneas part at the altar.'},
            {'kind': 'article', 'title': 'Ablative of the Efficient', 'snippet': 'Nothing about this poem.'},
            {'kind': 'article', 'title': 'Catullus and the Augustans', 'snippet': 'Virgil borrows from Catullus here.'}]
    kept, _ = bp._scholarship_keep(notes + arts, 'vergil.aeneid', 'Dido falls in love with Aeneas')
    assert len(kept) == 8
    assert [c['kind'] for c in kept].count('article') == 2
    assert all('Ablative' not in (c.get('title') or '') for c in kept)
    kept2, _ = bp._scholarship_keep(notes, 'vergil.aeneid', 'Dido falls in love with Aeneas')
    assert len(kept2) == 8 and all(c['kind'] == 'commentary' for c in kept2)
    assert bp._question_names('Dido falls in love with Aeneas') == ['dido', 'aeneas']
    assert bp._question_names('The plague at Athens') == ['athens']


RECENT = {'title': 'Dido and the Politics of Love', 'authors': ['A. Scholar'], 'year': 2015,
          'venue': 'Classical Quarterly', 'doi': '10.1/dido', 'url': 'https://example.org/p',
          'oa_url': None, 'excerpt': 'Dido yields to desire.', 'source': 'openalex', 'has_text': False, 'score': 2}


def _fake_services(monkeypatch, per_service):
    def fake(q, w, s):
        return per_service.get(s, {'service': s, 'available': True, 'results': [], 'reason': ''})
    monkeypatch.setattr(scholarship_recent, 'recent_safe', fake)


def test_recent_alone_writes_the_paragraph_and_names_the_count(monkeypatch):
    calls = []
    _setup(monkeypatch, [], calls)
    _fake_services(monkeypatch, {'openalex': {'service': 'openalex', 'available': True, 'results': [RECENT], 'reason': ''}})
    out = _post({'question': 'Dido falls in love with Aeneas', 'work': 'vergil.aeneid', 'lang': 'la'})
    assert out['available'] is True
    assert '1 article' in out['holdings']
    assert [c['kind'] for c in out['cites']] == ['recent']
    assert out['cites'][0]['link'] == {'kind': 'web', 'url': 'https://doi.org/10.1/dido'}
    assert out['cites'][0]['label'] == 'Dido and the Politics of Love (2015)'
    assert out['services']['openalex'] == 'ok' and out['services']['crossref'] == 'none'
    assert len(out['recent']) == 1
    system, user = calls[0]
    assert 'at most 150 words' in system and 'abstract' in system
    assert '[1] Article found online, known from its abstract or an excerpt: Dido and the Politics of Love (2015), Classical Quarterly: Dido yields to desire.' in user
    assert 'articles found online, known from abstracts' in user


def test_recent_items_are_numbered_after_the_held_ones_and_prefer_the_free_copy(monkeypatch):
    _setup(monkeypatch, [note('vergil.aeneid.part.4')])
    free = dict(RECENT, oa_url='https://free.example/p.pdf')
    _fake_services(monkeypatch, {'crossref': {'service': 'crossref', 'available': True, 'results': [free], 'reason': ''}})
    monkeypatch.setattr(model, 'complete', lambda *a, **k: 'Servius says so [1] and a recent article agrees [2].')
    out = _post({'question': 'Dido in love', 'work': 'vergil.aeneid', 'lang': 'la'})
    assert [c['n'] for c in out['cites']] == [1, 2]
    assert out['cites'][1]['link']['url'] == 'https://free.example/p.pdf'


def test_without_recent_items_the_limit_stays_120_and_holdings_say_none(monkeypatch):
    calls = []
    _setup(monkeypatch, [note('vergil.aeneid.part.4')], calls)
    out = _post({'question': 'Dido in love', 'work': 'vergil.aeneid', 'lang': 'la'})
    assert 'at most 120 words' in calls[0][0] and 'abstract' not in calls[0][0]
    assert 'recent' in out['holdings'] or 'live services' in out['holdings']
    assert out['recent'] == []


def test_a_failed_service_changes_the_holdings_clause(monkeypatch):
    _setup(monkeypatch, [note('vergil.aeneid.part.4')])
    ok = _post({'question': 'Dido in love', 'work': 'vergil.aeneid', 'lang': 'la'})
    _fake_services(monkeypatch, {'crossref': {'service': 'crossref', 'available': False, 'results': [],
                                              'reason': 'the service did not answer'}})
    bad = _post({'question': 'Dido in love', 'work': 'vergil.aeneid', 'lang': 'la'})
    assert bad['services']['crossref'] == 'failed'
    assert '1 of the live services' in bad['holdings'] and bad['holdings'] != ok['holdings']


def test_clause_states_and_no_forbidden_punctuation():
    info = {'display_name': 'Vergil, Aeneid'}
    kept = [note('vergil.aeneid')]
    for i in range(30):
        q = f'question {i}'
        for args in ((3, 0), (1, 0), (0, 0), (0, 2), (2, 1)):
            for held in (kept, []):
                s = passages._scholarship_holdings(q, held, info, 'vergil.aeneid', *args)
                assert ':' not in s and ';' not in s and '\u2014' not in s and '\u2013' not in s
    found = {passages._scholarship_holdings(f'q{i}', kept, info, 'w', 3, 0) for i in range(60)}
    assert len({s.split(' and ', 1)[-1] if ' and ' in s else s for s in found}) >= 4
    assert '3 articles' in passages._scholarship_holdings('q', kept, info, 'w', 3, 0)
    none_line = passages._scholarship_holdings('q', kept, info, 'w', 0, 0)
    assert 'no article' in none_line or 'nothing' in none_line


def test_holdings_count_is_everything_the_services_listed_not_only_what_the_paragraph_reads(monkeypatch):
    _setup(monkeypatch, [note('vergil.aeneid.part.4')])
    items = [dict(RECENT, title=f'Dido study {i}', doi=f'10.1/{i}') for i in range(6)]
    _fake_services(monkeypatch, {'openalex': {'service': 'openalex', 'available': True, 'results': items, 'reason': ''}})
    out = _post({'question': 'Dido in love', 'work': 'vergil.aeneid', 'lang': 'la'})
    assert '6 articles' in out['holdings'] and len(out['recent']) == 4


def test_cites_carry_the_fields_a_citation_needs(monkeypatch):
    calls = []
    _setup(monkeypatch, [note('vergil.aeneid.part.4'), article('On Virgil', 'Virgil at length')], calls)
    out = _post({'question': 'Dido in love', 'work': 'vergil.aeneid', 'lang': 'la'})
    for c in out['cites']:
        assert {'n', 'kind', 'label', 'link'} <= set(c)
        for k in ('title', 'authors', 'year', 'journal', 'venue', 'doi', 'url', 'oa_url',
                  'commentator', 'work', 'ref_start', 'ref_end'):
            assert k in c
    assert out['cites'][0]['commentator'] == 'Servius'
    assert out['cites'][1]['title'] == 'On Virgil'


def test_prompt_leaves_out_items_that_do_not_bear_on_the_question():
    s = passages._SCHOL_SYSTEM
    assert 'does not bear on the question is left out and never mentioned' in s
    assert 'not even to say it does not address the question' in s


@pytest.mark.skipif(not os.environ.get('TESSERAE_LLM_URL'),
                    reason='needs the model gateway (TESSERAE_LLM_URL)')
def test_gateway_paragraph_does_not_mention_an_irrelevant_item(monkeypatch):
    """Live model: one note answers the question, one article is about something else."""
    monkeypatch.undo()
    model._availability['at'] = 0
    if not model.is_available():
        pytest.skip('the gateway does not answer')
    system = passages._SCHOL_SYSTEM.format(limit=120)
    user = '\n'.join([
        'Vergil, Aeneid', 'Why does Dido fall in love with Aeneas?',
        'The sources below are commentary notes and journal articles only. Name them as such.',
        '[1] Servius, on aen. 1.1: Venus and Cupid, disguised as Ascanius, set Dido on fire with love.',
        '[2] Journal article, The Classical Review, Harbor Tolls at Ostia: This article discusses '
        'the collection of harbor tolls at Ostia in the second century.'])
    # 3000 tokens, not the route's 400: the gateway model reasons first and can use up
    # 400 before it writes a word (seen 2026-10-13).
    text = None
    for _ in range(3):
        text = model.complete(system, user, 3000, 0.2)
        if text:
            break
    if not text:
        pytest.skip('the gateway model wrote nothing in three tries (reasoning used the budget)')
    assert '[1]' in text
    assert 'Harbor Tolls' not in text and 'Ostia' not in text and '[2]' not in text
