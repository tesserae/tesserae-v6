"""Tessa runs Inscriptions & Papyri, Coins and Objects herself.

Each search is tested for its routing (five questions that reach it, three that
must not), the facts it gives the model, the control under the answer and an
empty result. The searches run through the real TOOLS table over a fake loopback.
"""
import os
import re

import pytest

from backend.assistant import actions, agent, collections_searches as cs, corpus_lookup, searches
from backend.assistant import three_searches as t3


def _text(tid, author, title, lang='la'):
    return {'id': tid + '.tess', 'author': author, 'author_key': author.lower(),
            'display_name': f'{author}, {title}', 'title': title, 'work': title,
            'work_key': title.lower().replace(' ', '_'), 'is_part': False, 'language': lang, 'part_num': None}


TEXTS = {
    'la': [_text('vergil.aeneid', 'Vergil', 'Aeneid'), _text('pliny.natural_history', 'Pliny', 'Natural History'),
           _text('tibullus.elegies', 'Tibullus', 'Elegies')],
    'grc': [_text('homer.iliad', 'Homer', 'Iliad', 'grc')],
    'en': [_text('shakespeare.hamlet', 'Shakespeare', 'Hamlet', 'en')],
}


def _doc(doc_id='edh:HD028139', text='Augusto / sacrum', edition='CIL 02 (2. Aufl.) 07, 00253; tab. 9, 5.',
         place='Corduba, near', modern='Córdoba, near', nb=-30, na=30, **kw):
    row = {'collection': 'documents', 'doc_id': doc_id, 'text': text, 'credit': {'principal_edition': edition},
           'ancient_place': place, 'modern_place': modern, 'date_not_before': nb, 'date_not_after': na,
           'region': 'Baetica', 'text_type_label': 'dedicatory inscription', 'object_type_label': 'Basis',
           'material_label': 'unknown'}
    row.update(kw)
    return row


DOCS = {'collection': 'documents', 'total': 18765, 'results': [_doc(), _doc('edh:HD2', 'Augusto / patri', 'AE 1990, 123',
                                                                              'Roma', 'Roma', 1, 50)]}
PAPYRI = {'collection': 'documents', 'total': 1079, 'results': [
    _doc('papyri:26812', 'τιμῆς σίτου', 'P.Oxy. 42 3060', 'Oxyrhynchos',
         None, 101, 200, text_type_label='letter (private)', material_label='papyrus', object_type_label=None)]}
COIN = {'id': 'ocre:ric.2_3.hdn.2009', 'title': 'RIC II, Part 3 (second edition) Hadrian 2009', 'authority': 'Hadrian',
        'mint': 'Rome', 'material': 'Silver', 'denomination': 'Denarius', 'date_start': 133, 'date_end': 135,
        'obverse_legend': 'HADRIANVS AVG COS III P P', 'reverse_legend': 'FELICITAS AVG',
        'obverse_description': 'Bust of Hadrian', 'reverse_description': 'Felicitas standing left, holding caduceus'}
OBJECT = {'id': 'si:A376471-0', 'title': 'Terracotta Lamp', 'museum': 'smithsonian', 'museum_name': 'Smithsonian Institution',
          'culture': 'Roman', 'object_type': 'Lamp', 'date_start': -100, 'date_end': -1, 'date_text': None,
          'description': 'Top: head (possibly Medusa), bottom: LCAESAR (?)', 'short_text': None}
ALL_PLACES = [
    {'value': 'Pompeii', 'label': 'Pompeii (Pompei)', 'modern': 'Pompei', 'count': 4779},
    {'value': 'Pompeiopolis', 'label': 'Pompeiopolis (Ta\u015fk\u00f6pr\u00fc)', 'modern': 'Ta\u015fk\u00f6pr\u00fc', 'count': 6},
    {'value': 'Oxyrhynchos', 'label': 'Oxyrhynchos (Beni Mas\u00e2r)', 'modern': 'Beni Mas\u00e2r', 'count': 4422},
    {'value': 'Oxyrhynchus', 'label': 'Oxyrhynchus', 'modern': '', 'count': 1},     # a stray spelling in the list
    {'value': 'Oxyrhynchites', 'label': 'Oxyrhynchites', 'modern': '', 'count': 1077},
    {'value': 'Roma', 'label': 'Roma', 'modern': '', 'count': 20000},
    {'value': 'Athens', 'label': 'Athens (Athina)', 'modern': 'Athina', 'count': 3000},
]
MINTS = {'available': True, 'facets': {'mint': [{'value': 'Rome', 'count': 9000}, {'value': 'Alexandria', 'count': 1240},
                                                 {'value': 'Alexandreia Troas', 'count': 139}]}}


class Loopback:
    def __init__(self):
        self.calls = []
        self.docs = DOCS
        self.coins = {'available': True, 'total': 117, 'coins': [COIN]}
        self.objects = {'available': True, 'total': 5, 'objects': [OBJECT]}

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        if path == '/texts':
            return TEXTS.get(params.get('language'), [])
        if path == '/line-search':
            return self.docs
        if path == '/documents/places':
            rows = [p for p in ALL_PLACES if params['q'].lower() in p['value'].lower()]
            return {'places': rows, 'total': len(rows)}
        if path == '/coins/facets':
            return MINTS
        if path == '/passages/theme-search':
            return {'results': [{'author': 'Vergil', 'title': 'Aeneid, Book 1', 'locus_start': '1.85', 'gist': 'A storm.',
                                 'strong': True}], 'confidence': {'level': 'restricted'}, 'note': ''}
        if path == '/coins':
            return self.coins
        if path == '/objects':
            return self.objects
        raise searches.SearchError('no such route ' + path)

    def paths(self):
        return [c[0] for c in self.calls if c[0] != '/texts']

    def last(self, path):
        return [c[1] for c in self.calls if c[0] == path][-1]


@pytest.fixture
def site(monkeypatch):
    loop = Loopback()
    monkeypatch.setattr(searches, '_get', loop)
    monkeypatch.setattr(corpus_lookup, '_texts', {})
    monkeypatch.setattr(searches, '_listing_cache', {})
    monkeypatch.setattr(searches, '_census_cache', {})
    monkeypatch.setattr(searches, '_mint_cache', {})
    monkeypatch.setattr(agent.model, 'is_available', lambda: True)
    # The chooser must never be reached for these questions, and the translation of a subject is the one model call.
    monkeypatch.setattr(agent.model, 'complete', lambda *a, **k: '{"search": null}')
    translations = {'Augustus': 'Augustus', 'grain': 'σῖτος', 'dis manibus': 'dis manibus'}
    monkeypatch.setattr(cs, 'corpus_words', lambda subject, lang: translations.get(subject))
    return loop


def _prep(question):
    out = agent._prepare(question, lambda s: None) or {}
    return out, out.get('facts') or []


# --------------------------------------------------------------------------
# Routing: five that reach each search, three that must not
# --------------------------------------------------------------------------
@pytest.mark.parametrize('question', [
    'Find inscriptions that mention Augustus',
    'Are there papyri about grain from Oxyrhynchus?',
    'Latin inscriptions with the phrase dis manibus from Pompeii',
    'Show me inscriptions from the 2nd century AD that mention Augustus',
    'How many papyri mention grain?',
])
def test_document_questions_reach_inscriptions_and_papyri(site, question):
    out, facts = _prep(question)
    assert out['ran'] == ['documents_search']


@pytest.mark.parametrize('question', [
    'Coins of Hadrian with Felicitas',
    'Which coin types show an elephant?',
    'Find coins minted at Rome showing Victory',
    'Are there coins of Augustus with a capricorn?',
    'Show me denarii that name Hadrian',
])
def test_coin_questions_reach_coins(site, question):
    out, facts = _prep(question)
    assert out['ran'] == ['coins_search']


@pytest.mark.parametrize('question', [
    'Museum objects showing Medusa',
    'Etruscan mirrors',
    'Find museum objects with a lion',
    'Are there Greek objects in a museum that show Herakles?',
    'Show me Roman lamps in the museums',
])
def test_object_questions_reach_objects(site, question):
    out, facts = _prep(question)
    assert out['ran'] == ['objects_search']


@pytest.mark.parametrize('question', [
    'How do I search the Inscriptions & Papyri page?',
    'Where do the inscriptions and papyri come from?',
    'What does the Aeneid say about storms?',
    'Where is Sarpedon mentioned?',
    'Compare the coins of Hadrian with the Aeneid',
    'What is the Coins page?',
    'Do you have museum objects?',
    'How do I use the Objects page?',
    'Are there passages about a storm at sea?',
    'Where does the phrase arma virumque occur?',
    'What do ancient sources say about the battle of Actium?',
    'Inscriptions',
    'Does People & Places include inscriptions?',
    'Can I search the inscriptions by place or date?',
    'What do the coins pages show?',
    'Can I see images of the museum objects?',
])
def test_the_collection_searches_do_not_take_these(site, question):
    assert cs.collection_request(question) is None


@pytest.mark.parametrize('question', [
    'What does the Aeneid say about coins?',
    'In Hamlet, where does an inscription appear?',
])
def test_a_question_that_names_one_work_goes_to_search_one_text(site, question):
    out, facts = _prep(question)
    assert out['ran'] == ['one_text_search']


def test_a_question_naming_two_collections_is_left_alone(site):
    assert cs.collection_request('Find coins and inscriptions of Hadrian') is None


# --------------------------------------------------------------------------
# The request each search makes
# --------------------------------------------------------------------------
def test_documents_request_is_the_pages_request(site):
    _prep('Latin inscriptions with the phrase dis manibus from Pompeii')
    p = site.last('/line-search')
    assert p['collection'] == 'documents' and p['query'] == 'dis manibus' and p['language'] == 'la'
    assert p['search_type'] == 'lemma' and p['kind'] == 'inscriptions' and p['doc_place'] == 'Pompeii'


def test_papyri_are_greek_unless_latin_is_asked_for(site):
    _prep('Are there papyri about grain from Oxyrhynchus?')
    p = site.last('/line-search')
    assert p['language'] == 'grc' and p['kind'] == 'papyri' and p['query'] == 'σῖτος'
    assert p['doc_place'] == 'Oxyrhynchos'            # the page's spelling, not the stray one-document "Oxyrhynchus"
    assert cs.collection_request('Find Latin papyri that mention Caesar')['language'] == 'la'


def test_a_phrase_is_searched_as_typed_and_a_subject_is_translated(site, monkeypatch):
    seen = []
    monkeypatch.setattr(cs, 'corpus_words', lambda s, lang: seen.append(s) or None)
    _prep('Latin inscriptions with the phrase dis manibus')
    assert seen == []
    _prep('Find inscriptions that mention Augustus')
    assert seen == ['Augustus']


def test_a_century_becomes_a_date_range(site):
    assert cs.collection_request('inscriptions of the 2nd century AD mentioning Augustus')['date_from'] == 101
    r = cs.collection_request('coins of the first century BC showing a ship')
    assert (r['date_from'], r['date_to']) == (-100, -1) and r['words'] == 'ship'
    _prep('Show me inscriptions from the 2nd century AD that mention Augustus')
    p = site.last('/line-search')
    assert p['date_from'] == 101 and p['date_to'] == 200


def test_coin_and_object_words_are_the_pages_query(site):
    _prep('Coins of Hadrian with Felicitas')
    assert site.last('/coins')['q'] == 'Hadrian Felicitas'
    _prep('Etruscan mirrors')
    assert site.last('/objects')['q'] == 'Etruscan mirror'       # the page matches word starts, so the singular finds both


def test_one_word_that_is_no_dictionary_form_is_tried_on_its_letters(site, monkeypatch):
    calls = []

    def loop(path, params):
        calls.append((path, params))
        if path == '/line-search':
            return {'total': 0, 'results': []} if params['search_type'] == 'lemma' else DOCS
        return site(path, params)
    monkeypatch.setattr(searches, '_get', loop)
    _out, facts = _prep('Find inscriptions that mention Augustus')
    assert [c[1]['search_type'] for c in calls if c[0] == '/line-search'] == ['lemma', 'exact']
    assert facts[-1]['search_note'] and facts[-1]['args']['search_type'] == 'exact'


# --------------------------------------------------------------------------
# Facts
# --------------------------------------------------------------------------
def test_document_facts_write_the_edition_out_and_carry_the_line(site):
    out, facts = _prep('Find inscriptions that mention Augustus')
    f = facts[-1]
    assert f['kind'] == t3.KIND_COLLECTION and f['documents_found'] == 18765
    ex = f['examples'][0]
    assert ex['ref'] == 'Corpus Inscriptionum Latinarum (CIL) 02 (2. Aufl.) 07, 00253; tab. 9, 5.'
    assert ex['date'] == '30 BC to 30 AD' and ex['findspot'] == 'Corduba, near' and ex['matching_line'] == 'Augusto / sacrum'
    assert ex['kind_of_document'] == 'dedicatory inscription, Basis'          # "unknown" material is left out
    assert f['examples'][1]['ref'] == "L'Année épigraphique (AE) 1990, 123"
    assert 'only the first 2 of 18765' in f['examples_note']
    assert 'doc_id' not in str(f)


def test_document_facts_name_the_words_searched_and_the_filters(site):
    out, facts = _prep('Latin inscriptions with the phrase dis manibus from Pompeii')
    f = facts[-1]
    assert f['words_searched'] == 'dis manibus' and f['limited_to_kind'] == 'inscriptions'
    assert f['limited_to_findspot'] == 'Pompeii'
    out, facts = _prep('Are there papyri about grain from Oxyrhynchus?')
    assert facts[-1]['asked_as'] == 'grain' and facts[-1]['words_searched'] == '\u03c3\u1fd6\u03c4\u03bf\u03c2'


def test_coin_facts_give_legend_mint_and_date(site):
    out, facts = _prep('Coins of Hadrian with Felicitas')
    f = facts[-1]
    assert f['coin_types_found'] == 117
    ex = f['examples'][0]
    assert ex['legend'] == 'HADRIANVS AVG COS III P P / FELICITAS AVG' and ex['mint'] == 'Rome'
    assert ex['date'] == '133 to 135 CE' and ex['denomination'] == 'Silver Denarius'
    assert ex['ref'].startswith('RIC II')


def test_object_facts_give_museum_date_and_title(site):
    out, facts = _prep('Museum objects showing Medusa')
    f = facts[-1]
    assert f['objects_found'] == 5
    ex = f['examples'][0]
    assert ex['ref'] == 'Terracotta Lamp' and ex['museum'] == 'Smithsonian Institution' and ex['date'] == '100 to 1 BCE'


def test_five_examples_at_most(site):
    site.coins = {'available': True, 'total': 900, 'coins': [dict(COIN, id=str(i)) for i in range(8)]}
    out, facts = _prep('Coins of Hadrian with Felicitas')
    assert len(facts[-1]['examples']) == 5 and 'first 5 of 900' in facts[-1]['examples_note']


def test_edition_names_equal_the_pages_table():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'client', 'src', 'utils', 'editionNames.js'),
               encoding='utf-8').read()
    body = src[src.index('EDITION_NAMES = {'):src.index('};')]
    pairs = re.findall(r"^\s*'((?:[^'\\]|\\.)*)':\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'),?\s*$", body, re.M)
    assert dict((k, v[1:-1].replace("\\'", "'")) for k, v in pairs) == cs.EDITION_NAMES


def test_an_unlisted_edition_is_left_as_written():
    assert cs.expand_editions('P.Oxy. 63 4394') == 'The Oxyrhynchus Papyri (P.Oxy.) 63 4394'
    assert cs.expand_editions('Foo 12') == 'Foo 12'
    assert cs.expand_editions('IGDS 5') == 'Inscriptions grecques dialectales de Sicile (IGDS) 5'


# --------------------------------------------------------------------------
# Controls
# --------------------------------------------------------------------------
def test_documents_control_opens_the_page_with_the_search_filled_in(site):
    out, facts = _prep('Latin inscriptions with the phrase dis manibus from Pompeii')
    ctl = [a for a in actions.build(facts, 'q') if a['kind'] == 'documents']
    assert len(ctl) == 1
    url = ctl[0]['url']
    assert url.startswith('/inscriptions-papyri?')
    for part in ('q=dis+manibus', 'lang=la', 'type=lemma', 'collection=documents', 'kind=inscriptions',
                 'doc_place=Pompeii', 'documents=1'):
        assert part in url


def test_documents_control_carries_the_dates_and_the_letters_type(site):
    out, facts = _prep('Show me inscriptions from the 2nd century AD that mention Augustus')
    url = [a for a in actions.build(facts, 'q') if a['kind'] == 'documents'][0]['url']
    assert 'date_from=101' in url and 'date_to=200' in url


def test_coin_and_object_controls_open_the_page_with_the_words(site):
    out, facts = _prep('Coins of Hadrian with Felicitas')
    assert [a['url'] for a in actions.build(facts, 'q') if a['kind'] == 'coins'] == ['/coins?q=Hadrian+Felicitas']
    out, facts = _prep('Museum objects showing Medusa')
    assert [a['url'] for a in actions.build(facts, 'q') if a['kind'] == 'objects'] == ['/objects?q=Medusa']


def test_a_coin_control_carries_the_years(site):
    out, facts = _prep('Coins of the first century BC showing a ship')
    url = [a for a in actions.build(facts, 'q') if a['kind'] == 'coins'][0]['url']
    assert url == '/coins?q=ship&date_from=-100&date_to=-1'


# --------------------------------------------------------------------------
# Empty results, written in code
# --------------------------------------------------------------------------
def test_no_document_says_so_and_names_the_filters(site):
    site.docs = {'collection': 'documents', 'total': 0, 'results': []}
    out, facts = _prep('Latin inscriptions with the phrase dis manibus from Pompeii')
    f = facts[-1]
    assert f['kind'] == t3.KIND_NONE and t3.code_answers([f])
    s = t3.code_sentence(f)
    assert 'finds no document' in s and 'dis manibus' in s and 'from Pompeii' in s and 'inscriptions' in s


def test_a_findspot_the_list_lacks_is_said_and_no_search_is_run(site):
    out, facts = _prep('Find inscriptions that mention Augustus in Nowhereville')
    assert '/line-search' not in site.paths()
    s = t3.code_sentence(facts[-1])
    assert 'no findspot called Nowhereville' in s


def test_the_words_searched_are_given_when_they_differ_from_the_question(site):
    site.docs = {'collection': 'documents', 'total': 0, 'results': []}
    out, facts = _prep('Are there papyri about grain from Oxyrhynchus?')
    s = t3.code_sentence(facts[-1])
    assert 'Greek words for “grain”' in s


def test_no_coin_and_no_object_say_so(site):
    site.coins = {'available': True, 'total': 0, 'coins': []}
    site.objects = {'available': True, 'total': 0, 'objects': []}
    out, facts = _prep('Coins of Hadrian with Felicitas')
    assert t3.code_sentence(facts[-1]) == 'The Coins page finds no coin type for “Hadrian Felicitas”.'
    out, facts = _prep('Museum objects showing Medusa')
    assert t3.code_sentence(facts[-1]) == 'The Objects page finds no museum object for “Medusa”.'


def test_a_page_that_is_not_available_is_an_empty_result(site):
    site.coins = {'available': False, 'coins': [], 'total': 0}
    out, facts = _prep('Coins of Hadrian with Felicitas')
    assert facts[-1]['kind'] == t3.KIND_NONE


def test_empty_answers_do_not_call_the_model(site, monkeypatch):
    site.coins = {'available': True, 'total': 0, 'coins': []}

    def boom(*a, **k):
        raise AssertionError('the model was called')
    monkeypatch.setattr(agent.model, 'stream', boom)
    events = list(agent.answer_stream('Coins of Hadrian with Felicitas'))
    text = ''.join(e[1] for e in events if e[0] == 'chunk')
    assert 'finds no coin type' in text and events[-1][1]['guardrails']['clean'] is True


# --------------------------------------------------------------------------
# The answer: guardrails cover the new facts, the tools are registered
# --------------------------------------------------------------------------
def test_the_model_is_given_the_searches_prompt_and_rule(site):
    out, facts = _prep('Coins of Hadrian with Felicitas')
    assert agent._answer_system(facts) is agent.THREE_SEARCHES_SYSTEM
    assert agent._answer_rule(facts, 'q') == t3.RULE
    assert 'Coins' in agent.THREE_SEARCHES_SYSTEM and 'Inscriptions & Papyri' in t3.RULE


def test_streaming_answer_is_checked_against_the_facts(site, monkeypatch):
    monkeypatch.setattr(agent.model, 'stream', lambda *a, **k: iter([
        'Found 117 coin types. RIC II, Part 3 (second edition) Hadrian 2009 shows Felicitas, minted at Rome. '
        'There are 4321 more.']))
    events = list(agent.answer_stream('Coins of Hadrian with Felicitas'))
    done = events[-1][1]
    assert '4321' in done['guardrails']['unsupported_numbers'] and done['guardrails']['clean'] is False
    assert any(a['kind'] == 'coins' for a in done['actions'])


def test_the_tools_are_registered_for_the_chooser_and_the_guide():
    from backend.assistant import prompts
    for name in cs.NAMES:
        assert name in searches.TOOLS and name in searches.tool_menu() and name in t3.NAMES
        assert name in prompts._BASE_TOOLS


def test_a_failed_search_is_reported_not_dropped(site, monkeypatch):
    def broken(path, params):
        if path == '/coins':
            raise searches.SearchError('search returned 500')
        return site(path, params)
    monkeypatch.setattr(searches, '_get', broken)
    out, facts = _prep('Coins of Hadrian with Felicitas')
    assert any(f.get('search') == 'coins_search' and f.get('failed') for f in facts)


def test_the_translation_asks_for_words_in_the_right_script(monkeypatch):
    monkeypatch.setattr(agent.model, 'complete', lambda *a, **k: 'σῖτος')
    assert cs.corpus_words('grain', 'grc') == 'σῖτος'
    assert cs.corpus_words('grain', 'la') is None                   # Greek letters for a Latin search are refused
    monkeypatch.setattr(agent.model, 'complete', lambda *a, **k: 'frumentum\nfrumenti means grain, as in')
    assert cs.corpus_words('grain', 'la') == 'frumentum'
    monkeypatch.setattr(agent.model, 'complete', lambda *a, **k: 'one two three four')
    assert cs.corpus_words('grain', 'la') is None
    monkeypatch.setattr(agent.model, 'complete', lambda *a, **k: None)
    assert cs.corpus_words('grain', 'la') is None


def test_a_findspot_is_the_pages_spelling():
    site_get = Loopback()
    old = searches._get
    searches._get = site_get
    try:
        assert searches._findspot('Pompeii', 'la') == 'Pompeii'
        assert searches._findspot('Oxyrhynchus', 'grc') == 'Oxyrhynchos'
        assert searches._findspot('Rome', 'la') == 'Roma'
        assert searches._findspot('Athens', 'grc') == 'Athens'
        assert searches._findspot('Nowhereville', 'la') is None
    finally:
        searches._get = old


def test_a_mint_and_a_denomination_are_the_pages_filters(site):
    r = cs.collection_request('Show me denarii minted at Rome that name Hadrian')
    assert r['denomination'] == 'Denarius' and r['mint'] == 'Rome' and r['words'] == 'Hadrian'
    _prep('Show me denarii minted at Rome that name Hadrian')
    p = site.last('/coins')
    assert p['mint'] == 'Rome' and p['denomination'] == 'Denarius' and p['q'] == 'Hadrian'
    out, facts = _prep('Find coins minted at Alexandria showing Isis')
    assert site.last('/coins')['mint'] == 'Alexandria' and facts[-1]['limited_to_mint'] == 'Alexandria'
    url = [a['url'] for a in actions.build(facts, 'q') if a['kind'] == 'coins'][0]
    assert url == '/coins?q=Isis&mint=Alexandria'


def test_a_mint_the_page_does_not_list_is_searched_as_a_word(site):
    out, facts = _prep('Find coins minted at Narnia showing a lion')
    assert 'mint' not in site.last('/coins') and site.last('/coins')['q'] == 'lion Narnia'
    assert 'limited_to_mint' not in facts[-1] and facts[-1]['words_searched'] == 'lion Narnia'


def test_a_mint_alone_is_something_to_look_for(site):
    out, facts = _prep('Find coins minted at Alexandria')
    assert out['ran'] == ['coins_search'] and site.last('/coins')['mint'] == 'Alexandria'
    url = [a['url'] for a in actions.build(facts, 'q') if a['kind'] == 'coins'][0]
    assert url == '/coins?mint=Alexandria'


def test_a_document_with_several_matching_lines_is_listed_once(site):
    site.docs = {'collection': 'documents', 'total': 9, 'results': [_doc('edh:A', 'one'), _doc('edh:A', 'two'),
                                                                    _doc('edh:B', 'three')]}
    out, facts = _prep('Find inscriptions that mention Augustus')
    assert [e['matching_line'] for e in facts[-1]['examples']] == ['one', 'three']


def test_the_resolved_findspot_is_in_the_facts_and_the_control(site):
    out, facts = _prep('Are there papyri about grain from Oxyrhynchus?')
    assert facts[-1]['limited_to_findspot'] == 'Oxyrhynchos' and facts[-1]['args']['place'] == 'Oxyrhynchos'
    assert 'asked_as' in facts[-1]['args']
    url = [a['url'] for a in actions.build(facts, 'q') if a['kind'] == 'documents'][0]
    assert 'doc_place=Oxyrhynchos' in url
    out, facts = _prep('Find inscriptions that mention Augustus')
    assert 'asked_as' not in facts[-1]['args']                 # the words were searched as typed
