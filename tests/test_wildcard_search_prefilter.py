"""The wildcard scan finds the same lines as testing every line.

backend/wildcard_search.py folds a file once, finds the lines that can match
(the lines holding a match of a term the query requires) and tests only those
lines exactly. These tests hold the shortcut to the plain way: a reference
that tests every line with matches_query, as the code did before, run over
files with the awkward cases (a phrase split across a line break, blank and
untagged lines, carriage returns, decomposed Greek, u/v and -om in Latin,
Coptic strokes) and over many queries.
"""
import os
import random
import re
import unicodedata

import pytest

import backend.utils as utils
from backend import wildcard_search as ws


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.setattr(utils, '_resolve_text_filepath', lambda *a, **k: None)


def reference_search_file(filepath, parsed_query, case_sensitive, language):
    """The rows search_file returned before the shortcut: every line tested."""
    is_greek, is_latin, is_coptic = language == 'grc', language == 'la', language == 'cop'
    is_prose = utils.detect_text_type(os.path.basename(filepath), language=language) == 'prose'
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    flags = 0 if case_sensitive else re.IGNORECASE
    rows = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.match(r'^<([^>]+)>\s*(.+)$', line)
        if not match:
            continue
        ref, text = match.group(1), match.group(2)
        if is_greek:
            search_text = ws.normalize_greek(text)
        elif is_latin:
            search_text = ws.normalize_latin(text)
        elif is_coptic:
            search_text = ws.normalize_coptic(text)
        else:
            search_text = text
        if not ws.matches_query(search_text, parsed_query, flags, is_greek, is_latin, is_coptic):
            continue
        token_normalizer = ws.normalize_coptic if is_coptic else (ws.normalize_greek if is_greek else None)
        if token_normalizer:
            hi = ws.get_token_highlight_indices(text, parsed_query, flags, token_normalizer)
        else:
            hi = ws.get_highlight_indices(text, parsed_query, flags, is_greek, is_latin)
        display = text
        if is_prose and len(text) > 150:
            display = ws.extract_sentences_with_matches(text, hi)
            if token_normalizer:
                hi = ws.get_token_highlight_indices(display, parsed_query, flags, token_normalizer)
            else:
                hi = ws.get_highlight_indices(display, parsed_query, flags, is_greek, is_latin)
        rows.append({'ref': ref, 'text': display, 'highlighted_text': ws.apply_highlighting(display, hi),
                     'is_prose': is_prose})
    return rows


LATIN = (
    "# a comment line\n"
    "<t. 1.1> Arma virumque cano, Troiae qui primus ab oris\n"
    "<t. 1.2> Italiam fato profugus Laviniaque venit\n"
    "\n"
    "<t. 1.3> litora, multum ille et terris iactatus et alto\r\n"
    "<t. 1.4> vi superum saevae memorem Iunonis ob iram; arma\n"
    "virumque untagged line that starts with the second word\n"
    "<t. 1.5>virum without a space after the tag, divom and diuom and Diuom\n"
    "<t. 1.6> arma\n"
    "<t. 1.7> virum arma virum arma virum\n"
    "<t. 1.8>    \n"
    "<t. 1.9> AMOR et Amor et amor omnia vincit; dolor, amori, amorem\n"
    "<t. 2.1> bellum amor dolor bellum\n"
    "   <t. 2.2> indented tag amor\n"
    "<t. 2.3> uirum nostrum Vergilium Juvenalem iuvenes\n"
    "<t. 2.4> arma virumque arma virumque\n"
)

GREEK_NFD = unicodedata.normalize(
    'NFD',
    "<il. 1.1> μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος\n"
    "<il. 1.2> οὐλομένην, ἣ μυρί᾽ Ἀχαιοῖς ἄλγε᾽ ἔθηκε\n"
    "<il. 1.3> πολλὰς δ᾽ ἰφθίμους ψυχὰς Ἄϊδι προΐαψεν\n"
    "<il. 1.4> ἡρώων, αὐτοὺς δὲ ἑλώρια τεῦχε κύνεσσιν\n"
    "<il. 1.5> θεὰ θεὰ ἄνδρα μοι ἔννεπε μοῦσα\n")

COPTIC = (
    "<mt. 1.1> ⲡⲛⲟⲩⲧⲉ ⲁ̅ⲡ̅ⲛ̅ⲁ̅ ⲡⲉⲛⲧⲁϥ ⲛⲟⲩⲧⲉ\n"
    "<mt. 1.2> ⲛⲟⲩⲧⲉ ⲡⲉ ⲡⲛⲟⲩⲧⲉ ⲛⲉⲛⲟⲩⲧⲉ\n"
    "<mt. 1.3> ⲁⲛⲟⲕ ⲡⲉ ⲡⲉⲛⲟⲩⲧⲉ\n")

ENGLISH = (
    "<h. 1.1> To be, or not to be, that is the question\n"
    "<h. 1.2> love and death; Love is a smoke, death\n"
    "<h. 1.3> thou art LOVED, and loving\n"
    "<h. 1.4> the the the\n")

LATIN_QUERIES = [
    'arma', 'arma virumque', '"arma virumque"', '"arma\nvirumque"', 'virum*', '*um', '?rma', 'am*',
    'amor AND dolor', 'amor OR bellum', 'amor NOT bellum', 'amor ~ dolor', 'arma ~ virum',
    'amor AND dolor NOT bellum', 'amor OR bellum AND dolor', 'divum', 'diuom', 'diuum', 'Diuom',
    'virumque AND arma', '#amor#', 'am#', 'a*a ~ v*m', 'uirum', 'vir*', 'iuvenes', 'Iuvenalem',
    'zzzz', 'zzz AND amor', 'amor AND zzz', 'zzz OR amor', 'amor NOT zzz', 'omnia', 'x*',
    '"virum arma"', '"arma virum arma"', 'virum arma', 'et', 'tag', 'with*', 'the', 'second',
]
GREEK_QUERIES = ['θεα', 'θεά', 'μηνιν', 'Ἀχιλῆος', 'αχιληος', 'θεα AND μοι', 'θεα OR ανδρα', 'θεα NOT μοι',
                 'θεα ~ ανδρα', 'ανδρα ~ μοι', '"θεα θεα"', 'αι*', '*ος', 'ε?νεπε', 'προιαψεν', 'zz']
COPTIC_QUERIES = ['ⲡⲛⲟⲩⲧⲉ', 'ⲛⲟⲩⲧⲉ', 'ⲡⲉⲛ*', 'ⲡⲛⲟⲩⲧⲉ AND ⲡⲉ', 'ⲡⲉ ~ ⲛⲟⲩⲧⲉ', 'ⲛⲟⲩⲧⲉ NOT ⲡⲉ', 'ⲁⲡⲛⲁ', '*ⲧⲉ']
ENGLISH_QUERIES = ['love', 'lov*', '*ing', 'love AND death', 'love OR the', 'love NOT death', 'love ~ death',
                   '"to be"', '"to be or not to be"', 'the', 'th?', '#the#', 'to AND be AND question']


def write(tmp_path, name, text):
    p = tmp_path / name
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    return str(p)


CASES = [
    ('la', LATIN, LATIN_QUERIES), ('grc', GREEK_NFD, GREEK_QUERIES),
    ('cop', COPTIC, COPTIC_QUERIES), ('en', ENGLISH, ENGLISH_QUERIES),
]


@pytest.mark.parametrize('language,text,queries', CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize('case_sensitive', [False, True])
def test_scan_equals_testing_every_line(tmp_path, language, text, queries, case_sensitive):
    path = write(tmp_path, 'x.sample.tess', text)
    for q in queries:
        parsed = ws.parse_query(q)
        got = ws.search_file(path, parsed, case_sensitive, language)
        want = reference_search_file(path, parsed, case_sensitive, language)
        assert got == want, (language, q, case_sensitive)


def test_a_phrase_across_a_blank_line_marks_both_lines(tmp_path):
    path = write(tmp_path, 'x.sample.tess', "<a. 1> arma\n\n<a. 2> virum cano\n<a. 3> arma virum\n")
    for q in ('"arma virum"', 'arma AND virum', 'arma ~ virum', 'virum NOT arma'):
        parsed = ws.parse_query(q)
        assert ws.search_file(path, parsed, False, 'la') == reference_search_file(path, parsed, False, 'la')


def test_random_queries_over_the_latin_sample(tmp_path):
    path = write(tmp_path, 'x.sample.tess', LATIN)
    rng = random.Random(7)
    words = ['arma', 'virum*', 'amor', 'dol?r', 'bellum', 'et', '*um', 'zz', 'ar*a', 'AMOR', '#amor', 'uirum']
    ops = [' AND ', ' OR ', ' NOT ', ' ~ ']
    for _ in range(300):
        n = rng.randint(1, 4)
        q = words[rng.randrange(len(words))]
        for _ in range(n - 1):
            q += rng.choice(ops) + words[rng.randrange(len(words))]
        for cs in (False, True):
            parsed = ws.parse_query(q)
            assert ws.search_file(path, parsed, cs, 'la') == reference_search_file(path, parsed, cs, 'la'), q


def test_required_leaves():
    leaves = lambda q: [t['value'] for t in (ws._required_leaves(ws.parse_query(q)) or [])]  # noqa: E731
    assert leaves('amor') == ['amor']
    assert leaves('amor AND dolor') == ['amor']
    assert leaves('amor OR dolor') == ['amor', 'dolor']
    assert leaves('amor NOT dolor') == ['amor']
    assert leaves('amor ~ dolor') == ['amor']
    assert leaves('a OR b AND c') == ['a', 'b']
    assert ws._required_leaves({'type': 'empty', 'terms': []}) is None
    assert ws._required_leaves({'type': 'weird'}) is None


def test_normalize_greek_equals_the_per_character_rule():
    def reference(text):
        return ''.join(ch for ch in unicodedata.normalize('NFD', text) if not unicodedata.combining(ch))
    rng = random.Random(3)
    pool = (list('abcαβγδεζηθικλμνξοπρστυφχψω ') + [chr(c) for c in range(0x0300, 0x0370)]
            + ['ἀ', 'Ἀ', 'ᾳ', 'ᾧ', 'ͅ', 'Ⲳ', '̅', 'ً', '่',
               '़', '᷀', '\U0001e944', '\U0001d165', '゙', 'é', 'ḍ̇'])
    for _ in range(2000):
        s = ''.join(rng.choice(pool) for _ in range(rng.randint(0, 30)))
        assert ws.normalize_greek(s) == reference(s)
    assert ws.normalize_greek('plain ascii') == 'plain ascii'
    assert ws.normalize_greek('') == ''
    every_mark = ''.join(chr(c) for c in range(0x110000) if unicodedata.combining(chr(c)))
    assert ws.normalize_greek('a' + every_mark + 'b') == 'ab'
