"""Tessa hands the reader a control, and the control has to be real.

A link is a promise that something exists. If the model composed these it would
eventually offer a search of a work that is not in the corpus, in a language the
page does not accept, and the reader would land on an empty page believing the
corpus had been consulted. So every action is built in code from arguments a
search has already run with, and these tests pin that.
"""
from backend.assistant import actions
from backend.assistant.agent import _wants_listing

EXACT_FACT = {
    'kind': 'phrase occurrences',
    'args': {'query': 'arma virumque', 'search_type': 'exact', 'language': 'la'},
}
VARIANT_FACT = {
    'kind': 'VARIANT FORMS of the same phrase, found by lemma search.',
    'phrase': 'arma virumque',
}


def test_the_search_that_ran_becomes_the_first_action():
    built = actions.build([EXACT_FACT])
    assert built, 'a search that ran produced no way to open it'
    first = built[0]
    assert first['url'] == '/line-search?q=arma+virumque&type=exact'
    assert 'arma virumque' in first['label']


def test_the_other_search_type_is_offered_too():
    """Exact and lemma answer different questions, and which one you want is the
    commonest thing a reader gets wrong. Both are offered."""
    urls = [a['url'] for a in actions.build([EXACT_FACT])]
    assert '/line-search?q=arma+virumque&type=lemma' in urls


def test_a_variant_offer_becomes_a_clickable_lemma_search():
    urls = [a['url'] for a in actions.build([VARIANT_FACT])]
    assert '/line-search?q=arma+virumque&type=lemma' in urls


def test_the_same_url_is_never_offered_twice():
    built = actions.build([EXACT_FACT, VARIANT_FACT])
    assert len(built) == len({a['url'] for a in built})


def test_no_more_than_a_handful():
    built = actions.build([EXACT_FACT, VARIANT_FACT] * 6)
    assert len(built) <= actions.MAX_ACTIONS


def test_a_language_the_page_cannot_search_is_refused():
    assert actions.for_suggestion('line_search', phrase='x y z',
                                  search_type='exact', language='klingon') is None


def test_an_unknown_search_type_is_refused():
    assert actions.for_suggestion('line_search', phrase='x y z',
                                  search_type='fuzzy', language='la') is None


def test_facts_with_no_arguments_contribute_nothing():
    """A fact that records no search arguments must produce no link, rather than
    a link built from a guess."""
    assert actions.build([{'kind': 'phrase occurrences'}]) == []
    assert actions.build([{'kind': 'corpus listing', 'works': 2100}]) == []
    assert actions.build([]) == []
    assert actions.build(None) == []


def test_every_action_carries_what_the_page_needs_to_render_it():
    for a in actions.build([EXACT_FACT, VARIANT_FACT]):
        assert a['url'].startswith('/'), 'actions must stay inside the site'
        assert a['label'] and a['kind']


def test_the_query_is_url_encoded():
    a = actions.for_suggestion('theme_search', query='a warrior arms himself')
    assert ' ' not in a['url']
    assert a['url'].startswith('/theme-search?query=')


def test_reader_action_selects_the_whole_span_with_a_translation():
    a = actions.for_suggestion('read', work='vergil.aeneid',
                               ref='6.258', ref_end='6.263')
    assert 'work=vergil.aeneid.tess' in a['url']
    assert 'refEnd=6.263' in a['url']
    assert 'tab=translation' in a['url']


def test_compare_needs_both_texts():
    assert actions.for_suggestion('compare', source='vergil.aeneid',
                                  target='', language='la') is None
    a = actions.for_suggestion('compare', source='vergil.aeneid',
                               target='ovid.metamorphoses', language='la')
    # Membership, not a prefix: the parameter order is not part of the contract.
    assert a['url'].startswith('/?')
    assert 'source=vergil.aeneid' in a['url']
    assert 'target=ovid.metamorphoses' in a['url']


# --- when a listing is warranted, decided in code rather than by the prompt ---
#
# The prompt alone did not hold: asked "where does the exact phrase arma virumque
# appear?", the model read "where" as a request for the loci and printed all
# twelve, which is the duplication the handoff exists to end.

def test_a_plain_question_is_not_a_request_for_a_listing():
    for q in ('Where does the exact phrase "arma virumque" appear?',
              'How common is arma virumque?',
              'Is arma virumque in Ovid?',
              'What does the corpus hold in Hebrew?'):
        assert not _wants_listing(q), q


def test_asking_for_the_passages_is():
    for q in ('list the instances',
              'can you give the Eobanus instances?',
              'show me the passages',
              'what lines contain it?',
              'give me the occurrences',
              'cite each one'):
        assert _wants_listing(q), q


# --- the guide half: a question where no search has run --------------------
#
# Names have to become REAL text ids or the link is a lie, so these use a stub
# corpus rather than the live one and assert the shape of what is built.

class _Corpus:
    ROWS = {
        'vergil': {'id': 'vergil.aeneid.tess', 'author': 'Vergil', 'language': 'la',
                   'display_name': 'Vergil, Aeneid', 'matched': 'author'},
        'statius': {'id': 'statius.silvae.tess', 'author': 'Statius', 'language': 'la',
                    'display_name': 'Statius, Silvae', 'matched': 'author'},
        'aeneid': {'id': 'vergil.aeneid.tess', 'author': 'Vergil', 'language': 'la',
                   'display_name': 'Vergil, Aeneid', 'matched': 'work'},
        'punica': {'id': 'silius_italicus.punica.tess', 'author': 'Silius Italicus',
                   'language': 'la', 'display_name': 'Silius Italicus, Punica',
                   'matched': 'work'},
    }

    def named_texts(self, question, limit=2):
        out = []
        for key, row in self.ROWS.items():
            if key in question.lower() and row not in out:
                out.append(row)
            if len(out) >= limit:
                break
        return out


def test_two_named_AUTHORS_become_an_author_level_comparison():
    """Naming an author but no work is not a licence to pick one. An id-length
    tiebreak once made Statius the Silvae and Ovid the Ibis."""
    built = actions.suggest('how do I find echoes of Vergil in Statius?',
                            lookup=_Corpus())
    assert built, 'a comparison question produced nothing'
    url = built[0]['url']
    assert 'source_author=Vergil' in url and 'target_author=Statius' in url
    assert 'source=' not in url.replace('source_author=', '')


def test_two_named_WORKS_become_a_text_level_comparison():
    built = actions.suggest('echoes of the Aeneid in the Punica', lookup=_Corpus())
    url = built[0]['url']
    assert 'source=vergil.aeneid' in url and 'target=silius_italicus.punica' in url


def test_a_thematic_question_becomes_a_theme_search():
    built = actions.suggest('are there any passages about a storm at sea?',
                            lookup=_Corpus())
    assert built[0]['url'] == '/theme-search?query=a+storm+at+sea'


def test_the_asking_is_stripped_from_the_subject():
    from backend.assistant.actions import _theme_subject
    assert _theme_subject('show me scenes where a city falls') == 'a city falls'
    assert _theme_subject('are there any passages about grief?') == 'grief'


def test_a_question_naming_nothing_resolvable_offers_nothing():
    """Better to say less than to link somewhere wrong."""
    assert actions.suggest('compare Blorgus with Snarf', lookup=_Corpus()) == []


def test_a_question_with_no_intent_at_all_offers_nothing():
    assert actions.suggest('what is the difference between lemma and exact search?',
                           lookup=_Corpus()) == []


def test_one_named_text_is_not_enough_to_compare():
    assert actions.suggest('echoes of Vergil somewhere', lookup=_Corpus()) == []


# --- ids from a MODEL-CHOSEN search are checked, unlike the phrase search's ---

def test_unreal_text_ids_from_rare_words_produce_no_link(monkeypatch):
    """rare_words is given its texts by the model, and it chose "Vergil_Aeneid"
    and "Statius_Thebaid" -- neither of which exists. The search still ran and
    still returned something, so "a search ran with these arguments" is not
    evidence that the texts are real."""
    monkeypatch.setattr(actions, '_real_text', lambda t: '.' in str(t))
    bad = [{'kind': 'rare shared words',
            'args': {'source': 'Vergil_Aeneid', 'target': 'Statius_Thebaid',
                     'language': 'la'}}]
    assert actions.build(bad) == []


def test_real_text_ids_from_rare_words_do_produce_a_link(monkeypatch):
    monkeypatch.setattr(actions, '_real_text', lambda t: '.' in str(t))
    good = [{'kind': 'rare shared words',
             'args': {'source': 'vergil.aeneid', 'target': 'statius.thebaid',
                      'language': 'la'}}]
    urls = [a['url'] for a in actions.build(good)]
    assert urls and 'source=vergil.aeneid' in urls[0]


def test_id_checking_fails_closed(monkeypatch):
    """If the corpus cannot be consulted, offer nothing rather than a guess."""
    def boom(*a, **k):
        raise RuntimeError('corpus unavailable')
    monkeypatch.setattr('backend.assistant.corpus_lookup.is_text_id', boom)
    assert actions._real_text('vergil.aeneid') is False
