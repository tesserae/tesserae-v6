"""Tessa runs Search One Text, People & Places and Events herself.

Each search is tested for its routing (a question that should reach it does,
three that should not do not), the facts it gives the model, the control under
the answer, an empty result and, for Events and People & Places, an ambiguous
name. The searches run through the real TOOLS table over a fake loopback.
"""
import pytest

from backend.assistant import actions, agent, corpus_lookup, searches, three_searches as t3


def _text(tid, author, title, lang='la', part=None):
    return {'id': tid + '.tess', 'author': author, 'author_key': author.lower(),
            'display_name': f'{author}, {title}' + (f', Book {part}' if part else ''),
            'title': title + (f', Book {part}' if part else ''), 'work': title,
            'work_key': title.lower().replace(' ', '_'), 'is_part': bool(part), 'language': lang,
            'part_num': str(part) if part else None}


TEXTS = {
    'la': [_text('vergil.aeneid', 'Vergil', 'Aeneid'), _text('vergil.aeneid.part.6', 'Vergil', 'Aeneid', part=6),
           _text('cicero.de_amicitia', 'Cicero', 'De Amicitia'), _text('cicero.de_officiis', 'Cicero', 'De Officiis'),
           _text('tibullus.elegies', 'Tibullus', 'Elegies'), _text('lucan.bellum_civile', 'Lucan', 'Bellum Civile')],
    'grc': [_text('thucydides.peloponnesian_war', 'Thucydides', 'Peloponnesian War', 'grc'),
            _text('homer.iliad', 'Homer', 'Iliad', 'grc')],
    'en': [_text('shakespeare.hamlet', 'Shakespeare', 'Hamlet', 'en'),
           _text('coleridge.rime_of_the_ancient_mariner', 'Coleridge', 'Rime of the Ancient Mariner', 'en')],
}


def _theme_row(i, author='Vergil', title='Aeneid, Book 1', locus='1.85–1.96'):
    return {'author': author, 'title': title, 'work': 'vergil.aeneid.part.1', 'display_name': f'{author}, {title}',
            'locus': locus, 'locus_start': locus.split('–')[0], 'ref_start': 'verg. aen. ' + locus.split('–')[0],
            'gist': f'A sudden storm number {i} scatters the fleet.', 'strong': True, 'language': 'la'}


THEME = {'results': [_theme_row(i) for i in range(10)], 'confidence': {'level': 'restricted'},
         'note': 'Confidence is not rated for a search within one author or work.'}

SARPEDON = {'id': 'pn:sarpe', 'label': 'Sarpedon', 'display_label': 'Sarpedon', 'type': 'person', 'source': 'promoted',
            'mentions_total': 169, 'mention_counts': {'grc': 100, 'la': 69}, 'label_shared': False,
            'label_shared_with': [], 'description': None, 'display_label_la': 'Sarpedon', 'display_label_grc': None}
SARPEDON_FULL = dict(SARPEDON, works=[
    {'work': 'homer.iliad.part.16', 'author': 'Homer', 'title': 'Iliad, Book 16', 'display_name': 'Homer, Iliad, Book 16',
     'language': 'grc', 'count': 17},
    {'work': 'homer.iliad.part.5', 'author': 'Homer', 'title': 'Iliad, Book 5', 'display_name': 'Homer, Iliad, Book 5',
     'language': 'grc', 'count': 9},
    {'work': 'vergil.aeneid.part.1', 'author': 'Vergil', 'title': 'Aeneid, Book 1', 'display_name': 'Vergil, Aeneid, Book 1',
     'language': 'la', 'count': 3}], document_counts={'grc': 2})
DELIA = dict(SARPEDON, id='pn:deli2', label='Delia', display_label='Delia', display_label_la='Delia', mentions_total=70,
             mention_counts={'la': 70})
DELIA_FULL = dict(DELIA, works=[
    {'work': 'tibullus.elegies', 'author': 'Tibullus', 'title': 'Elegies', 'display_name': 'Tibullus, Elegies',
     'language': 'la', 'count': 44},
    {'work': 'ovid.amores', 'author': 'Ovid', 'title': 'Amores', 'display_name': 'Ovid, Amores', 'language': 'la',
     'count': 3}], document_counts={})
ROME_A = dict(SARPEDON, id='ln:E1', label='Rome', display_label='Rome', type='place', mentions_total=900,
              mention_counts={'la': 900})
ROME_B = dict(SARPEDON, id='pn:rome2', label='Rome', display_label='Rome', type='deity', mentions_total=40,
              mention_counts={'la': 40}, description='The goddess Roma.')

ACTIUM = {'id': 'Q160387', 'label': 'Battle of Actium', 'type': 'battle', 'date_start': -31, 'date_end': -31,
          'place': 'Aktio', 'place_ancient': 'Actium', 'n_passages': 30, 'n_documents': 0}
ACTIUM_OLD = {'id': 'Q9173813', 'label': 'Battle of Actium', 'type': 'battle', 'date_start': -435, 'date_end': -435,
              'place': 'Akri', 'place_ancient': 'Actium', 'n_passages': 0, 'n_documents': 2}
ACTIUM_FULL = {
    'event': dict(ACTIUM, description='31 BCE decisive confrontation of the Final War of the Roman Republic'),
    'passage_counts': {'yes': 13, 'mention': 17, 'no': 88},
    'passages': [{'work': 'plutarch.antony', 'ref_start': 'plut. ant. 64.2', 'llm_label': 'yes',
                  'excerpts': [{'text': 'the ships turned in flight'}]},
                 {'work': 'cassius_dio.roman_history', 'ref_start': 'cass. dio 50.32.8', 'llm_label': 'yes', 'excerpts': []},
                 {'work': 'propertius.elegies', 'ref_start': 'prop. 4.6.50', 'llm_label': 'mention', 'excerpts': []}],
    'documents': [], 'scholarship': [{'kind': 'article', 'title': 'A'}, {'kind': 'article', 'title': 'B'}]}


class Loopback:
    """The site's own routes, as the searches module reaches them."""

    def __init__(self):
        self.calls = []
        self.entities = {'sarpedon': [SARPEDON], 'delia': [DELIA], 'rome': [ROME_A, ROME_B]}
        self.full = {'pn:sarpe': SARPEDON_FULL, 'pn:deli2': DELIA_FULL, 'ln:E1': dict(ROME_A, works=[]),
                     'pn:rome2': dict(ROME_B, works=[])}
        self.events = {'actium': [ACTIUM, ACTIUM_OLD], 'battle of cannae': [dict(ACTIUM, id='Q1', label='Battle of Cannae',
                       date_start=-216, date_end=-216, place='Cannae', place_ancient=None)],
                       'thermopylae': [dict(ACTIUM, id='Q2', label='Battle of Thermopylae', date_start=-480,
                                            date_end=-480, place='Thermopylae', place_ancient=None)]}
        self.theme = THEME

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        if path == '/texts':
            return TEXTS.get(params.get('language'), [])
        if path == '/passages/theme-search':
            return self.theme
        if path == '/entities/search':
            rows = self.entities.get(params['q'].lower(), [])
            return {'q': params['q'], 'results': rows, 'total': len(rows)}
        if path.startswith('/entities/'):
            return self.full[path[len('/entities/'):]]
        if path == '/events':
            rows = self.events.get(params['q'].lower(), [])
            return {'events': rows, 'total': len(rows)}
        if path.startswith('/events/'):
            return ACTIUM_FULL if path.endswith('Q160387') else {'event': self.events['battle of cannae'][0],
                                                                 'passage_counts': {}, 'passages': [],
                                                                 'documents': [], 'scholarship': []}
        raise searches.SearchError('no such route ' + path)

    def paths(self):
        return [c[0] for c in self.calls if c[0] != '/texts']


@pytest.fixture
def site(monkeypatch):
    loop = Loopback()
    monkeypatch.setattr(searches, '_get', loop)
    monkeypatch.setattr(corpus_lookup, '_texts', {})
    monkeypatch.setattr(searches, '_listing_cache', {})
    monkeypatch.setattr(searches, '_census_cache', {})
    monkeypatch.setattr(agent.model, 'is_available', lambda: True)
    # The chooser must never be reached for these questions: a search from the model would be a routing change.
    monkeypatch.setattr(agent.model, 'complete', lambda *a, **k: '{"search": null}')
    return loop


def _prep(question):
    steps = []
    out = agent._prepare(question, steps.append) or {}
    return out, out.get('facts') or []


def _search_names(facts):
    return [f.get('search') for f in facts]


# --------------------------------------------------------------------------
# Routing: five that reach each search, and questions that must not
# --------------------------------------------------------------------------
@pytest.mark.parametrize('question', [
    'What does the Aeneid say about storms?',
    'Where does Thucydides talk about plague?',
    'In Hamlet, where does a ghost appear?',
    'Where in the Aeneid does someone descend to the underworld?',
    'What does Aeneid 6 say about the sibyl?',
])
def test_one_text_questions_reach_search_one_text(site, question):
    out, facts = _prep(question)
    assert 'one_text_search' in out['ran']
    assert site.paths() == ['/passages/theme-search']


def test_one_text_request_is_the_page_request(site):
    _prep('What does the Aeneid say about storms?')
    path, params = [c for c in site.calls if c[0] == '/passages/theme-search'][0]
    assert params == {'q': 'storms', 'works': 'vergil.aeneid', 'limit': 25, 'languages': 'la'}


def test_one_book_is_searched_as_a_book_of_its_work(site):
    _prep('What does Aeneid 6 say about the sibyl?')
    _, params = [c for c in site.calls if c[0] == '/passages/theme-search'][0]
    assert params['works'] == 'vergil.aeneid' and params['books'] == '6' and params['q'] == 'the sibyl'


def test_an_author_with_one_work_is_that_work(site):
    out, facts = _prep('Where does Thucydides talk about plague?')
    _, params = [c for c in site.calls if c[0] == '/passages/theme-search'][0]
    assert params['works'] == 'thucydides.peloponnesian_war' and params['languages'] == 'grc'


@pytest.mark.parametrize('question', [
    'What does Cicero say about friendship?',                    # an author with two works: the old routing stays
    'Are there any passages about a storm at sea?',              # no work named: Theme Search across everything
    'Where does the phrase "arma virumque" appear in the Aeneid?',   # a quoted phrase is Line Search
])
def test_one_text_does_not_take_these(site, question):
    out, facts = _prep(question)
    assert 'one_text_search' not in (out.get('ran') or [])
    assert not any(c[0] == '/passages/theme-search' and c[1].get('works') for c in site.calls)


def test_an_ordinary_word_of_a_title_is_not_a_work_named(site):
    # "ancient sources" must not become the Rime of the Ancient Mariner
    assert t3.one_text_request('What do ancient sources say about storms?') is None
    out, facts = _prep('What do ancient sources say about the battle of Actium?')
    assert 'one_text_search' not in out['ran'] and 'events' in out['ran']


def test_comparison_of_two_texts_is_not_taken(site):
    out, facts = _prep('What does the Aeneid say about storms compared with Lucan?')
    assert 'one_text_search' not in (out.get('ran') or [])


@pytest.mark.parametrize('question,name', [
    ('Where is Sarpedon mentioned?', 'Sarpedon'),
    ('Which works name Delia?', 'Delia'),
    ('How often is Sarpedon named?', 'Sarpedon'),
    ('Who mentions Sarpedon?', 'Sarpedon'),
    ('where is sarpedon mentioned', 'sarpedon'),
])
def test_mention_questions_reach_people_and_places(site, question, name):
    out, facts = _prep(question)
    assert 'people_places' in out['ran']
    assert site.paths()[0] == '/entities/search'


@pytest.mark.parametrize('question', [
    'Where does the phrase "arma virumque" appear?',             # Line Search
    'Which works mention the Aeneid?',                           # a title, not a person or place
    'How does People & Places decide that a word refers to a particular person?',   # the guide
    'where is the phrase mentioned',                             # no name at all
])
def test_people_and_places_does_not_take_these(site, question):
    out, facts = _prep(question)
    assert 'people_places' not in (out.get('ran') or [])
    assert not any(f.get('search') == 'people_places' for f in facts)


@pytest.mark.parametrize('question', [
    'What do ancient sources say about the battle of Actium?',
    'Tell me about the battle of Cannae.',
    'Which texts describe Thermopylae?',
    'What happened at the battle of Actium?',
    'Which sources describe the battle of Actium?',
])
def test_event_questions_reach_events(site, question):
    out, facts = _prep(question)
    assert 'events' in out['ran']
    assert site.paths()[0] == '/events'


@pytest.mark.parametrize('question', [
    'How does the Events page decide which battles to list?',     # the guide
    'Compare the battle of Actium in Vergil with Propertius.',    # a comparison
    'Which texts describe a storm at sea?',                       # no event of that name
])
def test_events_does_not_take_these(site, question):
    out, facts = _prep(question)
    assert not any(f.get('search') == 'events' and f.get('kind') in (t3.KIND_EVENT, t3.KIND_SEVERAL) for f in facts)


# --------------------------------------------------------------------------
# Facts the model writes from
# --------------------------------------------------------------------------
def test_one_text_facts_carry_references_and_the_cap(site):
    out, facts = _prep('What does the Aeneid say about storms?')
    f = [x for x in facts if x.get('search') == 'one_text_search'][0]
    assert f['kind'] == t3.KIND_ONE_TEXT and f['work_searched'] == 'Vergil, Aeneid'
    assert f['passages_returned'] == 10 and len(f['examples']) == 5
    assert f['examples'][0]['ref'] == 'Vergil, Aeneid 1.85'
    assert 'only the first 5 of 10' in f['examples_note']
    assert f['match_band'] == 'not rated' and 'not rated' in f['page_note']
    assert t3.model_writes(facts) and not t3.code_answers(facts)


@pytest.mark.parametrize('conf,band', [({'level': 'strong', 'fitted': 'within-work 2026-10-12'}, 'Strong match'),
                                       ({'level': 'moderate', 'fitted': 'x'}, 'Moderate match'),
                                       ({'level': 'low', 'fitted': 'x'}, 'Closest passages')])
def test_the_match_band_is_the_pages_label(site, conf, band):
    site.theme = dict(THEME, confidence=conf, note='These passages stand out.')
    out, facts = _prep('What does the Aeneid say about storms?')
    f = [x for x in facts if x.get('search') == 'one_text_search'][0]
    assert f['kind'] == t3.KIND_ONE_TEXT and f['match_band'] == band and f['page_note'] == 'These passages stand out.'


def test_a_low_band_that_was_not_fitted_is_nothing_resembling_the_subject(site):
    site.theme = dict(THEME, confidence={'level': 'low'}, note='Weak.')
    out, facts = _prep('What does the Aeneid say about storms?')
    f = [x for x in facts if x.get('search') == 'one_text_search'][0]
    assert f['kind'] == t3.KIND_NONE and 'Nothing in this work resembles that subject.' in f['note']


def test_a_subject_no_passage_description_contains_gives_nothing_to_search_for(site):
    site.theme = dict(THEME, confidence={'level': 'low', 'no_known_words': True}, note='No known words.')
    out, facts = _prep('What does the Aeneid say about storms?')
    f = [x for x in facts if x.get('search') == 'one_text_search'][0]
    assert f['kind'] == t3.KIND_NONE and f['note'].startswith('Nothing to search for.')


def test_people_places_facts_give_the_entry(site):
    out, facts = _prep('Where is Sarpedon mentioned?')
    f = [x for x in facts if x.get('search') == 'people_places'][0]
    assert f['kind'] == t3.KIND_PLACES and f['heading'] == 'Sarpedon' and f['lines_naming_it'] == 169
    assert f['works_naming_it'] == 2          # the Iliad (two books added up) and the Aeneid
    assert f['works_with_most_lines_TOP5_ONLY'][0] == 'Homer, Iliad: 26 lines'
    assert f['inscriptions_and_papyri_naming_it'] == 2


def test_people_places_limits_to_the_author_asked_about(site):
    out, facts = _prep('How often does Tibullus mention Delia?')
    f = [x for x in facts if x.get('search') == 'people_places'][0]
    assert f['heading'] == 'Delia' and f['limited_to'] == 'Tibullus'
    assert f['lines_naming_it_within_that_limit'] == 44 and f['lines_naming_it'] == 70


def test_event_facts_use_the_pages_date_and_place(site):
    site.events['actium'] = [ACTIUM]
    out, facts = _prep('What do ancient sources say about the battle of Actium?')
    f = [x for x in facts if x.get('search') == 'events'][0]
    assert f['kind'] == t3.KIND_EVENT and f['date'] == '31 BCE' and f['place'] == 'Actium (modern Aktio)'
    assert (f['narrative_passages'], f['mention_passages'], f['articles'], f['documents_nearby']) == (13, 17, 2, 0)
    assert [e['ref'] for e in f['examples']] == ['Plutarch, Antony 64.2', 'Cassius Dio, Roman History 50.32.8']
    assert len(f['examples']) == 2 and f['examples'][0]['text'] == 'the ships turned in flight'


def test_a_name_alone_must_be_a_whole_word_of_the_event(site):
    # the route matches inside words: Troy finds Troyes
    site.events['siege of troy'] = []
    site.events['troy'] = [dict(ACTIUM, id='Q3', label='Battle of the Catalaunian Plains', place='Troyes',
                                place_ancient=None)]
    out, facts = _prep('Tell me about the siege of Troy.')
    f = [x for x in facts if x.get('search') == 'events'][0]
    assert f['kind'] == t3.KIND_NONE


def test_no_identifier_is_a_field_of_the_facts_the_model_writes_from(site):
    out, facts = _prep('Where is Sarpedon mentioned?')
    assert not {'entry_id', 'event_id'} & set(facts[-1])
    site.events['actium'] = [ACTIUM]
    out, facts = _prep('What do ancient sources say about the battle of Actium?')
    assert not {'entry_id', 'event_id'} & set(facts[-1])


def test_date_and_place_labels_follow_the_page():
    assert t3.date_label(-52, -49) == '52 to 49 BCE' and t3.date_label(-5, 14) == '5 BCE to 14 CE'
    assert t3.date_label(9, None) == '9 CE'
    assert t3.place_label('Perugia', 'Perusia') == 'Perusia (modern Perugia)'
    assert t3.place_label('Cannae', 'Cannae') == 'Cannae' and t3.place_label('Cannae', None) == 'Cannae'


# --------------------------------------------------------------------------
# Controls
# --------------------------------------------------------------------------
def test_one_text_control_opens_the_page_with_work_and_question(site):
    out, facts = _prep('What does the Aeneid say about storms?')
    ctl = [a for a in actions.build(facts, 'q') if a['kind'] == 'one_text'][0]
    assert ctl['url'] == '/ask-a-work?work=vergil.aeneid&lang=la&q=storms'


def test_one_text_control_carries_the_book(site):
    out, facts = _prep('What does Aeneid 6 say about the sibyl?')
    ctl = [a for a in actions.build(facts, 'q') if a['kind'] == 'one_text'][0]
    assert 'books=6' in ctl['url'] and 'q=the+sibyl' in ctl['url']


def test_a_work_the_chooser_picked_gets_its_language_from_the_listing(site):
    fact = {'search': 'one_text_search', 'args': {'work': 'homer.iliad', 'query': 'a funeral'},
            'work_searched': 'Homer, Iliad'}
    assert actions._three_controls(fact)[0]['url'] == '/ask-a-work?work=homer.iliad&lang=grc&q=a+funeral'


def test_people_places_control_opens_the_entry(site):
    out, facts = _prep('Where is Sarpedon mentioned?')
    ctl = [a for a in actions.build(facts, 'q') if a['kind'] == 'people_places']
    assert [c['url'] for c in ctl] == ['/mentions?e=pn%3Asarpe']


def test_event_control_opens_the_event_page(site):
    site.events['actium'] = [ACTIUM]
    out, facts = _prep('What do ancient sources say about the battle of Actium?')
    ctl = [a for a in actions.build(facts, 'q') if a['kind'] == 'event']
    assert [c['url'] for c in ctl] == ['/events/Q160387']


# --------------------------------------------------------------------------
# Empty results, written in code
# --------------------------------------------------------------------------
def test_one_text_with_no_passages_says_so(site):
    site.theme = {'results': [], 'note': 'The index holds no passages of that work.'}
    out, facts = _prep('What does the Aeneid say about storms?')
    f = facts[-1]
    assert f['kind'] == t3.KIND_NONE and t3.code_answers(facts)
    s = agent._handoff_sentence(facts)
    assert 'found no passages' in s and 'storms' in s
    assert any(a['kind'] == 'one_text' for a in actions.build(facts, 'q'))


def test_a_name_with_no_entry_says_so(site):
    site.entities['perusia'] = []
    out, facts = _prep('Which works name Perusia?')
    f = [x for x in facts if x.get('search') == 'people_places'][0]
    assert f['kind'] == t3.KIND_NONE
    assert agent._handoff_sentence(facts) == 'People & Places has no entry for Perusia.'
    assert [a['url'] for a in actions.build(facts, 'q')] == ['/mentions?q=Perusia']


def test_an_event_that_is_not_there_says_so(site):
    out, facts = _prep('Tell me about the siege of Perusia.')
    f = [x for x in facts if x.get('search') == 'events'][0]
    assert f['kind'] == t3.KIND_NONE
    assert 'no event named Perusia' in agent._handoff_sentence(facts)
    assert [a['url'] for a in actions.build(facts, 'q')] == ['/events']


def test_the_full_title_is_tried_before_the_name(site):
    _prep('Tell me about the siege of Perusia.')
    qs = [c[1]['q'] for c in site.calls if c[0] == '/events']
    assert qs == ['siege of Perusia', 'Perusia']


# --------------------------------------------------------------------------
# Several matches: listed in code, with the question which
# --------------------------------------------------------------------------
def test_two_events_of_one_name_are_listed_with_dates(site):
    out, facts = _prep('What do ancient sources say about the battle of Actium?')
    f = [x for x in facts if x.get('search') == 'events'][0]
    assert f['kind'] == t3.KIND_SEVERAL and f['match_count'] == 2
    s = agent._handoff_sentence(facts)
    assert '31 BCE' in s and '435 BCE' in s and s.endswith('Which one do you mean?')
    assert 'Actium (modern Aktio)' in s
    urls = [a['url'] for a in actions.build(facts, 'q')]
    assert urls == ['/events/Q160387', '/events/Q9173813']
    # a list of matches needs no dossier request
    assert not any(p.startswith('/events/') for p in site.paths())


def test_two_entries_of_one_name_are_listed(site):
    out, facts = _prep('Where is Rome mentioned?')
    f = [x for x in facts if x.get('search') == 'people_places'][0]
    assert f['kind'] == t3.KIND_SEVERAL and f['match_count'] == 2
    s = agent._handoff_sentence(facts)
    assert 'Rome (place, 900 lines' in s and 'Rome (deity, 40 lines' in s and s.endswith('Which one do you mean?')


# --------------------------------------------------------------------------
# The answer: guardrails cover the new facts, the new tools are registered
# --------------------------------------------------------------------------
def test_the_model_is_given_the_three_searches_prompt_and_rule(site):
    out, facts = _prep('What does the Aeneid say about storms?')
    assert agent._answer_system(facts) is agent.THREE_SEARCHES_SYSTEM
    assert agent._answer_rule(facts, 'q') == t3.RULE
    # an ordinary phrase search keeps its prompt
    assert agent._answer_system([{'search': 'line_search'}]) is agent.ANSWER_SYSTEM


def test_streaming_answer_is_checked_against_the_facts(site, monkeypatch):
    monkeypatch.setattr(agent.model, 'stream', lambda *a, **k: iter([
        'Vergil, Aeneid 1.85 has a storm. Vergil, Aeneid 6.851 does too. There are 99 of them.']))
    events = list(agent.answer_stream('What does the Aeneid say about storms?'))
    done = events[-1][1]
    assert done['guardrails']['references_removed'] == ['Aeneid 6.851']
    assert '99' in done['guardrails']['unsupported_numbers']
    assert done['guardrails']['clean'] is False
    assert any(a['kind'] == 'one_text' for a in done['actions'])


def test_code_answers_do_not_call_the_model(site, monkeypatch):
    def boom(*a, **k):
        raise AssertionError('the model was called')
    monkeypatch.setattr(agent.model, 'stream', boom)
    events = list(agent.answer_stream('What do ancient sources say about the battle of Actium?'))
    text = ''.join(e[1] for e in events if e[0] == 'chunk')
    assert 'Which one do you mean?' in text and events[-1][1]['guardrails']['clean'] is True


def test_the_tools_are_registered_for_the_chooser_and_the_guide():
    for name in t3.NAMES:
        assert name in searches.TOOLS and name in searches.tool_menu()
    from backend.assistant import prompts
    desc = prompts._BASE_TOOLS + prompts._SCENE_TOOLS
    assert 'one_text_search' in desc and 'people_places' in desc and 'events' in desc


def test_a_failed_search_is_reported_not_dropped(site, monkeypatch):
    def broken(path, params):
        if path == '/passages/theme-search':
            raise searches.SearchError('search returned 500')
        return site(path, params)
    monkeypatch.setattr(searches, '_get', broken)
    out, facts = _prep('What does the Aeneid say about storms?')
    assert any(f.get('search') == 'one_text_search' and f.get('failed') for f in facts)
