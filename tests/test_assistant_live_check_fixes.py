"""Four answers that failed a live check of Tessa on 10 October 2026, and the
number check's two false alarms."""
import pytest

from backend.assistant import actions, agent, corpus_lookup, searches, site_help
from backend.assistant.model import numbers_preserved


def _row(id_, author, title, language='la', part=False):
    return {'id': id_, 'language': language, 'author': author,
            'author_key': author.lower().replace(' ', '_'), 'title': title,
            'display_name': f'{author}, {title}',
            'work_key': title.lower().replace(' ', '_'), 'is_part': part}


ROWS = [
    _row('statius.thebaid.tess', 'Statius', 'Thebaid'),
    _row('statius.thebaid.part.1.tess', 'Statius', 'Thebaid', part=True),
    _row('statius.silvae.tess', 'Statius', 'Silvae'),
    _row('vergil.aeneid.tess', 'Vergil', 'Aeneid'),
    _row('vergil.aeneid.part.1.tess', 'Vergil', 'Aeneid', part=True),
    _row('catullus.carmina.part.64.tess', 'Catullus', 'Carmina', part=True),
    _row('apollonius_rhodius.argonautica.part.3.tess', 'Apollonius Rhodius',
         'Argonautica', language='grc', part=True),
]


@pytest.fixture
def listing(monkeypatch):
    monkeypatch.setattr(corpus_lookup, '_all_texts', lambda language=None: [
        r for r in ROWS if language in (None, r['language'])])


# 1. Two titles, one author -------------------------------------------------

def test_two_titles_with_a_leading_verb_resolve_to_two_works(listing):
    ids = lambda q: [h['id'] for h in corpus_lookup.named_texts(q)]
    want = ['statius.thebaid.part.1.tess', 'vergil.aeneid.part.1.tess']
    assert ids('Compare Statius Thebaid 1 with Aeneid 1 and tell me the three strongest parallels.') == want
    assert ids('Compare Statius Thebaid 1 with Vergil Aeneid 1') == want


def test_an_author_then_one_of_that_authors_works_is_one_text(listing):
    assert [h['id'] for h in corpus_lookup.named_texts('Compare Statius Thebaid')] == ['statius.thebaid.tess']


# 2. A Greek-Latin pair -----------------------------------------------------

CROSS_RESULTS = [{'source': {'ref': 'ap. rhod. 3.1', 'text': 'x'}, 'target': {'ref': 'catull. 64.1', 'text': 'y'},
                  'overall_score': 5.0, 'channels': 'semantic (85%)', 'matched_words': []}]


def test_cross_language_page_calls_the_polled_route(monkeypatch):
    seen = {}

    def fake_get(path, params):
        seen.update(path=path, params=params)
        return {'status': 'complete', 'parallels': CROSS_RESULTS}
    monkeypatch.setattr(searches, '_get', fake_get)
    page = searches.crosslingual_page('apollonius_rhodius.argonautica.part.3', 'catullus.carmina.part.64', 'grc', 'la', 10)
    assert page == CROSS_RESULTS
    assert seen['path'] == '/crosslingual-search-poll'
    assert seen['params']['source'].endswith('.tess') and seen['params']['target_language'] == 'la'


def test_fusion_results_runs_the_cross_language_search_for_two_languages(monkeypatch):
    monkeypatch.setattr(searches, 'crosslingual_page', lambda s, t, sl, tl, n: CROSS_RESULTS)
    monkeypatch.setattr(searches, 'fusion_page', lambda *a: pytest.fail('same-language search used'))
    page = agent._fusion_results('a', 'b', 'la', 'A', 'B', None, target_language='grc')
    assert page == CROSS_RESULTS


def test_the_cross_language_link_chooses_both_texts_in_the_tabs_order():
    link = actions._cross_texts('catullus.carmina.part.64', 'apollonius_rhodius.argonautica.part.3', 'la', 'grc')
    assert link['kind'] == 'cross_language'
    # The tab's pair is Greek to Latin, so the Greek text comes first.
    assert 'pair=grc-la' in link['url']
    assert link['url'].index('apollonius') < link['url'].index('catullus')
    assert actions._cross_texts('x', 'y', 'la', 'cop') is None


def test_a_greek_latin_comparison_runs_the_cross_language_search(listing, monkeypatch):
    monkeypatch.setattr(agent.model, 'is_available', lambda: True)
    monkeypatch.setattr(agent, '_named_works', lambda q: {})
    monkeypatch.setattr(searches, 'corpus_census', lambda: {})
    monkeypatch.setattr(searches, 'crosslingual_page', lambda s, t, sl, tl, n: CROSS_RESULTS)
    steps = []
    out = agent._prepare('Compare Catullus 64 with Apollonius Argonautica 3. What do they share?', steps.append)
    assert out.get('fusion_results') == CROSS_RESULTS
    assert any('running the comparison' in s for s in steps)


def test_a_cross_language_pair_that_did_not_finish_names_the_tab(listing, monkeypatch):
    monkeypatch.setattr(agent.model, 'is_available', lambda: True)
    monkeypatch.setattr(agent, '_named_works', lambda q: {})
    monkeypatch.setattr(searches, 'corpus_census', lambda: {})
    monkeypatch.setattr(agent, '_fusion_results', lambda *a, **k: None)
    out = agent._prepare('Compare Catullus 64 with Apollonius Argonautica 3.', lambda s: None)
    fact = next(f for f in out['facts'] if f['kind'].startswith('TWO TEXTS'))
    assert 'Cross-Language tab' in fact['kind'] and 'Greek and Latin' in fact['kind']
    links = actions.build(out['facts'], 'x')
    assert links and links[0]['kind'] == 'cross_language' and 'pair=grc-la' in links[0]['url']


# 3. The Help page covers the Scholarship tab -------------------------------

@pytest.fixture
def help_chunks(monkeypatch):
    monkeypatch.setattr(site_help, '_chunks', site_help._extract())


@pytest.mark.parametrize('question,needle', [
    ('What does the Scholarship tab show and where does it come from?', 'Scholarship lists the public-domain commentary'),
    ('What does the Collections button do?', 'The Collections button'),
    ('What are Inscriptions & Papyri?', 'Inscriptions & Papyri'),
    ('What is the Events page?', 'The Events page gathers'),
])
def test_the_help_excerpt_covers_these_sections(help_chunks, question, needle):
    assert any(needle in c for c in site_help.relevant(question, k=4))


# 4. Translations of a named work -------------------------------------------

def test_a_translation_fact_names_the_translator(monkeypatch):
    monkeypatch.setattr(searches, 'translations_available', lambda lang: {
        'vergil.aeneid': {'attribution': 'Dryden (1697)', 'coverage': 0.98, 'confidence': 'high'}})
    fact = agent._translation_fact(ROWS[3])
    assert fact['translation_attached'] and fact['attribution'] == 'Dryden (1697)'
    assert fact['share_of_lines_aligned_percent'] == 98


def test_no_translation_is_said_plainly(monkeypatch):
    monkeypatch.setattr(searches, 'translations_available', lambda lang: {})
    fact = agent._translation_fact(ROWS[3])
    assert fact['translation_attached'] is False and 'no aligned translation' in fact['note']


def test_which_translations_for_the_aeneid_reads_the_translation_record(listing, monkeypatch):
    monkeypatch.setattr(agent.model, 'is_available', lambda: True)
    monkeypatch.setattr(agent, '_named_works', lambda q: {})
    monkeypatch.setattr(searches, 'corpus_census', lambda: {})
    monkeypatch.setattr(searches, 'translations_available', lambda lang: {
        'vergil.aeneid': {'attribution': 'Dryden (1697)', 'coverage': 1.0}})
    monkeypatch.setattr(searches, 'run', lambda *a: pytest.fail('a listing was fetched'))
    out = agent._prepare('Which translations do you show for the Aeneid?', lambda s: None)
    fact = next(f for f in out['facts'] if f.get('search') == 'translations')
    assert fact['attribution'] == 'Dryden (1697)'
    assert 'translations' in out['ran']


# 5. The number check -------------------------------------------------------

def test_a_number_with_a_thousands_comma_is_one_number():
    ok, bad = numbers_preserved('{"works": 1,326}', 'The corpus holds 1,326 Greek works.')
    assert ok and bad == []
    ok, bad = numbers_preserved('{"works": 1326}', 'The corpus holds 1,326 Greek works.')
    assert ok and bad == []
    ok, bad = numbers_preserved('{"works": 1,326}', 'The corpus holds 2,500 Greek works.')
    assert not ok


def test_a_number_word_that_counts_a_listing_is_not_flagged():
    ok, bad = numbers_preserved('{"works": 40}', 'The corpus holds four specific works by Iqbal.')
    assert ok and bad == []


def test_a_number_word_that_counts_results_is_still_flagged():
    ok, bad = numbers_preserved('{"results": 25}', 'Only seven parallels are verbatim.')
    assert not ok and bad == ['seven']
