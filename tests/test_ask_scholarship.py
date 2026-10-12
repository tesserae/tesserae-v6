"""POST /passages/ask-scholarship with the search and the model faked."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend.assistant import model  # noqa: E402
from backend import scholarship_theme  # noqa: E402
from backend.blueprints import passages  # noqa: E402


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
