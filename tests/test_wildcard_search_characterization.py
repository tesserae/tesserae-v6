"""Characterization tests for backend/wildcard_search.py.

Expected values come from running the current code and reading each one.

Search runs against tests/fixtures/tess/la/test.mini.tess (six lines of the
opening of the Aeneid, under a made-up author name) and against small files
written into a temporary folder. The texts folder is pointed at the fixture
folder, the author-dates lookup is stubbed (it would import the whole web
app), and the prose-detection step that reads real text files is switched off,
so nothing outside tests/fixtures/ is read.

Two things about the functions' contract that the tests rely on and that are
easy to miss. matches_term, matches_query and matches_proximity expect the
TEXT to have been normalised already by the caller (search_file does this);
they normalise only the query pattern. And parse_query reads operators in a
fixed order (proximity, then AND, then OR, then NOT), so a query that mixes
them is read by the first operator found.
"""
import os
import re

import pytest

import backend.utils as utils
from backend import wildcard_search as ws

FIX_ROOT = os.path.join(os.path.dirname(__file__), 'fixtures', 'tess')
FIX_FILE = os.path.join(FIX_ROOT, 'la', 'test.mini.tess')
IGN = re.IGNORECASE


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.setattr(utils, '_resolve_text_filepath', lambda *a, **k: None)
    monkeypatch.setattr(ws, 'get_author_dates',
                        lambda: {'la': {'test': {'era': 'Augustan', 'year': -19}}})


def term(kind, value, pattern, **extra):
    return dict({'type': kind, 'value': value, 'pattern': pattern}, **extra)


# ---- the two normalisers ---------------------------------------------------

def test_normalize_greek_strips_accents_keeps_case():
    assert ws.normalize_greek('λόγος') == 'λογος'
    assert ws.normalize_greek('Ἄνδρα') == 'Ανδρα'       # case kept; breathing and accent gone
    assert ws.normalize_greek('Ῥώμη') == 'Ρωμη'
    assert ws.normalize_greek('plain') == 'plain'        # non-Greek text passes through
    assert ws.normalize_greek('') == ''


def test_normalize_latin_is_the_surface_fold():
    assert ws.normalize_latin('jam') == 'iam'
    assert ws.normalize_latin('Iuppiter') == 'Iuppiter'  # case kept
    assert ws.normalize_latin('Juppiter') == 'Iuppiter'
    assert ws.normalize_latin('VIRUM') == 'UIRUM'
    assert ws.normalize_latin('diuom') == 'diuum'        # archaic -om folded to -um


# ---- parse_query and parse_term --------------------------------------------

def test_parse_query_empty():
    assert ws.parse_query('') == {'type': 'empty', 'terms': []}
    assert ws.parse_query('   ') == {'type': 'empty', 'terms': []}


def test_parse_query_simple_wildcard_phrase():
    assert ws.parse_query('amor') == {'type': 'simple', 'terms': [
        term('exact', 'amor', 'amor', word_break=False)]}
    assert ws.parse_query('am*')['terms'][0] == term('wildcard', 'am*', r'am\w*', word_break=False)
    assert ws.parse_query('?or')['terms'][0]['pattern'] == r'\wor'
    assert ws.parse_query('"arma virumque"')['terms'][0] == term(
        'phrase', 'arma virumque', r'\barma\s+virumque\b')


def test_parse_query_operators():
    and_ = ws.parse_query('amor AND dolor')
    assert and_['type'] == 'and' and [t['value'] for t in and_['terms']] == ['amor', 'dolor']
    or_ = ws.parse_query('virtus or honos')            # operator words are case-insensitive
    assert or_['type'] == 'or' and [t['value'] for t in or_['terms']] == ['virtus', 'honos']
    not_ = ws.parse_query('amor NOT bellum')
    assert not_['type'] == 'not' and not_['include']['value'] == 'amor' and not_['exclude']['value'] == 'bellum'
    prox = ws.parse_query('amor ~ dolor')
    assert prox['type'] == 'proximity' and prox['distance'] == 100
    assert prox['term1']['value'] == 'amor' and prox['term2']['value'] == 'dolor'


def _shape(node):
    """A nested query reduced to tuples of values, to compare nesting at a glance."""
    t = node['type']
    if t in ('exact', 'wildcard', 'phrase'):
        return node['value']
    if t in ('and', 'or', 'simple'):
        return (t, [_shape(x) for x in node['terms']])
    if t == 'not':
        return ('not', _shape(node['include']), _shape(node['exclude']))
    if t == 'proximity':
        return ('prox', _shape(node['term1']), _shape(node['term2']))
    return t


def test_parse_query_mixed_operators_use_ordinary_precedence():
    # AND binds tighter than OR.
    assert _shape(ws.parse_query('amor AND dolor OR x')) == ('or', [('and', ['amor', 'dolor']), 'x'])
    assert _shape(ws.parse_query('x OR amor AND dolor')) == ('or', ['x', ('and', ['amor', 'dolor'])])
    # Proximity binds tighter than AND.
    assert _shape(ws.parse_query('a ~ b AND c')) == ('and', [('prox', 'a', 'b'), 'c'])
    assert _shape(ws.parse_query('c AND a ~ b')) == ('and', ['c', ('prox', 'a', 'b')])
    # NOT binds tighter than AND and OR.
    assert _shape(ws.parse_query('a AND b NOT c')) == ('and', ['a', ('not', 'b', 'c')])
    assert _shape(ws.parse_query('a NOT b OR c')) == ('or', [('not', 'a', 'b'), 'c'])
    # Left to right among equals.
    assert _shape(ws.parse_query('a NOT b NOT c')) == ('not', ('not', 'a', 'b'), 'c')
    assert _shape(ws.parse_query('a OR b AND c OR d')) == ('or', ['a', ('and', ['b', 'c']), 'd'])
    # A NOT inside a proximity operand covers the pair.
    assert _shape(ws.parse_query('a ~ b NOT c')) == ('not', ('prox', 'a', 'b'), 'c')
    assert _shape(ws.parse_query('a NOT b ~ c')) == ('not', ('prox', 'a', 'c'), 'b')
    # Nested leaves keep the ordinary term shape.
    node = ws.parse_query('am* AND dolor OR x')
    assert node['terms'][0]['terms'][0] == term('wildcard', 'am*', r'am\w*', word_break=False)


def test_mixed_query_matches_by_the_nesting():
    line = 'amor et dolor in pectore'
    def check(q):
        return ws.matches_query(line, ws.parse_query(q), IGN)

    assert check('amor AND dolor OR zzz') is True
    assert check('zzz OR amor AND dolor') is True
    assert check('zzz OR amor AND yyy') is False
    assert check('amor OR zzz AND yyy') is True           # the old fixed order read (amor OR zzz) AND yyy: False
    assert check('amor AND pectore NOT zzz') is True
    assert check('amor AND pectore NOT dolor') is False
    assert check('amor ~ dolor AND pectore') is True
    assert check('amor ~ pectore AND zzz') is False


def test_mixed_query_highlights_leaf_terms_only():
    idx = ws.get_highlight_indices('amor et dolor', ws.parse_query('amor AND dolor OR zzz'), IGN)
    assert idx == [[0, 4], [8, 13]]
    idx = ws.get_highlight_indices('amor et dolor', ws.parse_query('amor AND et NOT dolor'), IGN)
    assert idx == [[0, 4], [5, 7]]       # the excluded term is not marked


def test_parse_term_word_break_and_escaping():
    assert ws.parse_term('amor#') == term('exact', 'amor', 'amor', word_break=True)   # # is removed
    assert ws.parse_term('a.b')['pattern'] == r'a\.b'                              # regex characters escaped
    assert ws.parse_term(' "x y" ')['type'] == 'phrase'                              # surrounding space ignored
    assert ws.parse_term('"x')['type'] == 'exact'                                  # unbalanced quote is text


def test_wildcard_to_regex_and_phrase_to_regex():
    assert ws.wildcard_to_regex('a*b?c.') == r'a\w*b\wc\.'
    assert ws.wildcard_to_regex('') == ''
    assert ws.phrase_to_regex('arma  virumque') == r'\barma\s+virumque\b'    # runs of spaces become one gap
    assert ws.phrase_to_regex('') == r'\b\b'


# ---- matching --------------------------------------------------------------

LINE = 'Arma uirumque cano'      # already folded, as search_file would pass it


def test_matches_term_flags_and_wildcards():
    assert ws.matches_term(LINE, ws.parse_term('arma'), IGN) is True
    assert ws.matches_term(LINE, ws.parse_term('arma'), 0) is False          # case-sensitive
    assert ws.matches_term(LINE, ws.parse_term('uirum*'), IGN) is True
    assert ws.matches_term(LINE, ws.parse_term('uirum'), IGN) is False         # whole words only
    assert ws.matches_term(LINE, ws.parse_term('"arma uirumque"'), IGN) is True


def test_matches_term_folds_the_query_by_language():
    assert ws.matches_term('Uirumque', ws.parse_term('virumque'), IGN, is_latin=True) is True    # v folded in query
    assert ws.matches_term('Uirumque', ws.parse_term('virumque'), IGN) is False                  # no language: not folded
    assert ws.matches_term('λογος', ws.parse_term('λόγος'), IGN, is_greek=True) is True          # accent dropped in query
    assert ws.matches_term('λόγος', ws.parse_term('λογος'), IGN, is_greek=True) is False         # text must be normalised by caller


@pytest.mark.parametrize('query,expected', [
    ('arma', True),
    ('arma AND cano', True),
    ('arma AND bellum', False),
    ('bellum OR cano', True),
    ('bellum OR amor', False),
    ('arma NOT bellum', True),
    ('arma NOT cano', False),
    ('bellum NOT cano', False),
    ('arma ~ cano', True),
    ('', False),                      # empty query matches nothing
])
def test_matches_query(query, expected):
    assert ws.matches_query(LINE, ws.parse_query(query), IGN) is expected


def test_matches_query_unknown_type():
    assert ws.matches_query(LINE, {'type': 'weird'}, IGN) is False


def test_matches_proximity_distances():
    q = ws.parse_query('amor ~ dolor')
    assert ws.matches_proximity('amor et multa verba dolor', q, IGN) is True
    assert ws.matches_proximity('dolor amor', q, IGN) is True                     # either order
    assert ws.matches_proximity('amor ' + 'x' * 120 + ' dolor', q, IGN) is False  # gap over 100 characters
    assert ws.matches_proximity('amor ' + 'x' * 98 + ' dolor', q, IGN) is True    # a gap of exactly 100 passes
    assert ws.matches_proximity('amor ' + 'x' * 99 + ' dolor', q, IGN) is False   # 101 does not
    assert ws.matches_proximity('amor', q, IGN) is False                          # second term missing


def test_matches_proximity_folds_by_language():
    q = ws.parse_query('diuum ~ iam')
    assert ws.matches_proximity('diuom jam', q, IGN, is_latin=True) is True      # -om, j both folded
    assert ws.matches_proximity('diuom jam', q, IGN) is False


# ---- highlighting ----------------------------------------------------------

TEXT = 'Arma uirumque cano, arma gerit'


def test_get_highlight_indices_by_query_type():
    assert ws.get_highlight_indices(TEXT, ws.parse_query('arma'), IGN) == [[0, 4], [20, 24]]
    assert ws.get_highlight_indices(TEXT, ws.parse_query('arma OR cano'), IGN) == [[0, 4], [14, 18], [20, 24]]
    assert ws.get_highlight_indices(TEXT, ws.parse_query('arma NOT cano'), IGN) == [[0, 4], [20, 24]]   # only the included term
    assert ws.get_highlight_indices(TEXT, ws.parse_query('arma ~ cano'), IGN) == [[0, 4], [14, 18], [20, 24]]
    assert ws.get_highlight_indices(TEXT, {'type': 'empty'}, IGN) == []
    assert ws.get_highlight_indices(TEXT, ws.parse_query('absent'), IGN) == []


def test_get_highlight_indices_greek_and_latin_folding():
    assert ws.get_highlight_indices('Ἄνδρα μοι', ws.parse_query('ανδρα'), IGN, is_greek=True) == [[0, 5]]
    assert ws.get_highlight_indices('Virumque', ws.parse_query('uirumque'), IGN, is_latin=True) == [[0, 8]]


def test_get_token_highlight_indices():
    g = 'Ἄνδρα μοι ἔννεπε'
    assert ws.get_token_highlight_indices(g, ws.parse_query('ανδρα'), IGN, ws.normalize_greek) == [[0, 5]]
    assert ws.get_token_highlight_indices(g, ws.parse_query('μοι OR εννεπε'), IGN, ws.normalize_greek) == [[6, 9], [10, 16]]
    assert ws.get_token_highlight_indices(g, {'type': 'empty'}, IGN, ws.normalize_greek) == []
    assert ws.get_token_highlight_indices(g, ws.parse_query('absent'), IGN, ws.normalize_greek) == []


def test_apply_highlighting():
    m = '<mark class="bg-yellow-200">'
    assert ws.apply_highlighting('abcdef', [[0, 2], [1, 3], [4, 5]]) == f'{m}abc</mark>d{m}e</mark>f'   # overlap merged
    assert ws.apply_highlighting('abc', []) == 'abc'
    assert ws.apply_highlighting('abc', [[0, 3]]) == f'{m}abc</mark>'
    assert ws.apply_highlighting('abcd', [[2, 4], [0, 1]]) == f'{m}a</mark>b{m}cd</mark>'               # unsorted input


LONG = ('This is the first sentence about arma. Here is another sentence. '
        'And a third one mentions cano here! Final words.')


def test_extract_sentences_short_text():
    assert ws.extract_sentences_with_matches(LONG, [[34, 38]]) == 'This is the first sentence about arma.'
    two = ws.extract_sentences_with_matches(LONG, [[34, 38], [86, 90]])
    assert two == 'This is the first sentence about arma. ... And a third one mentions cano here!'   # gap marked
    assert ws.extract_sentences_with_matches(LONG, []) == LONG                       # no matches: unchanged
    assert ws.extract_sentences_with_matches('no stop here', [[0, 2]]) == 'no stop here'   # no sentence ends


def test_extract_sentences_long_text_uses_snippets():
    big = ('word ' * 40) + 'arma ' + ('word ' * 40) + ('filler ' * 80) + 'cano ' + ('word ' * 40)
    a, c = big.index('arma'), big.index('cano')
    out = ws.extract_sentences_with_matches(big, [[a, a + 4], [c, c + 4]])
    # two separate snippets, each with ellipses, joined by a space
    assert out.count('arma') == 1 and out.count('cano') == 1
    assert out.startswith('...') and out.endswith('...') and '... ...' in out
    one = ws.extract_sentences_with_matches(big, [[a, a + 4], [a + 1, a + 3]])      # second match already covered
    assert one.count('...') == 2 and 'cano' not in one


@pytest.mark.parametrize('filename,meta,expected', [
    ('vergil.aeneid.tess', {'author': 'Vergil', 'title': 'Aeneid'},
     {'author': 'Vergil', 'title': 'Aeneid', 'display_name': 'Vergil, Aeneid'}),
    ('vergil.aeneid.part.1.tess', {},                                   # title taken from the name, 'part' cut off
     {'author': 'Vergil', 'title': 'Aeneid', 'display_name': 'Vergil, Aeneid'}),
    ('cicero.de_oratore.tess', {'author': 'Cicero'},                    # one field missing: both rebuilt from the name
     {'author': 'Cicero', 'title': 'De Oratore', 'display_name': 'Cicero, De Oratore'}),
    ('onlyone.tess', {},                                                # nothing to build from
     {'author': '', 'title': '', 'display_name': 'onlyone.tess'}),
])
def test_format_title(filename, meta, expected):
    assert ws.format_title(filename, meta) == expected


# ---- search_file -----------------------------------------------------------

def refs(rows):
    return [r['ref'] for r in rows]


def test_search_file_latin_fixture():
    rows = ws.search_file(FIX_FILE, ws.parse_query('uirum*'), False, 'la')
    assert rows == [{
        'ref': 'test. 1.1',
        'text': 'Arma virumque cano, Troiae qui primus ab oris',
        'highlighted_text': 'Arma <mark class="bg-yellow-200">virumque</mark> cano, Troiae qui primus ab oris',
        'is_prose': False}]                                    # u in the query finds v in the text


def test_search_file_boolean_phrase_and_proximity():
    assert refs(ws.search_file(FIX_FILE, ws.parse_query('multa OR multum'), False, 'la')) == ['test. 1.3', 'test. 1.5']
    phrase = ws.search_file(FIX_FILE, ws.parse_query('"inferretque deos"'), False, 'la')
    assert refs(phrase) == ['test. 1.6'] and '<mark class="bg-yellow-200">inferretque deos</mark>' in phrase[0]['highlighted_text']
    prox = ws.search_file(FIX_FILE, ws.parse_query('litora ~ alto'), False, 'la')
    assert refs(prox) == ['test. 1.3'] and prox[0]['highlighted_text'].count('<mark') == 2
    assert ws.search_file(FIX_FILE, ws.parse_query('Iunonis NOT saevae'), False, 'la') == []   # both on line 1.4


def test_search_file_case_sensitivity():
    assert refs(ws.search_file(FIX_FILE, ws.parse_query('Arma'), True, 'la')) == ['test. 1.1']
    assert ws.search_file(FIX_FILE, ws.parse_query('arma'), True, 'la') == []
    assert refs(ws.search_file(FIX_FILE, ws.parse_query('arma'), False, 'la')) == ['test. 1.1']


def test_search_file_no_match_empty_and_missing():
    assert ws.search_file(FIX_FILE, ws.parse_query('zzz'), False, 'la') == []
    assert ws.search_file(FIX_FILE, ws.parse_query(''), False, 'la') == []
    assert ws.search_file('/nonexistent/x.tess', ws.parse_query('a'), False, 'la') == []     # unreadable: no rows


def test_search_file_greek_ignores_accents_and_highlights_whole_word(tmp_path):
    p = tmp_path / 'homer.iliad.tess'
    p.write_text('<il. 1.1>\tμῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος\n# a comment\n\nnot a line\n'
                 '<il. 1.2>\tοὐλομένην, ἣ μυρί᾽ Ἀχαιοῖς ἄλγε᾽ ἔθηκε\n', encoding='utf-8')
    rows = ws.search_file(str(p), ws.parse_query('μηνιν'), False, 'grc')
    assert refs(rows) == ['il. 1.1']
    assert rows[0]['highlighted_text'].startswith('<mark class="bg-yellow-200">μῆνιν</mark>')   # raw word kept, accents and all
    assert refs(ws.search_file(str(p), ws.parse_query('Ἀχιλῆος'), False, 'grc')) == ['il. 1.1']  # accented query also finds it
    assert refs(ws.search_file(str(p), ws.parse_query('αχιληος'), False, 'grc')) == ['il. 1.1']


def test_search_file_english_and_coptic(tmp_path):
    en = tmp_path / 'milton.paradise_lost.tess'
    en.write_text("<pl. 1.1>\tOf Man's first disobedience, and the fruit\n", encoding='utf-8')
    rows = ws.search_file(str(en), ws.parse_query('fruit'), False, 'en')
    assert rows[0]['highlighted_text'].endswith('the <mark class="bg-yellow-200">fruit</mark>')
    cop = tmp_path / 'shenoute.test.tess'
    cop.write_text('<s. 1>\tⲁⲩⲱ ⲡⲛⲟⲩⲧⲉ ⲙⲁⲣⲉϥ\n', encoding='utf-8')
    rows = ws.search_file(str(cop), ws.parse_query('ⲡⲛⲟⲩⲧⲉ'), False, 'cop')
    assert refs(rows) == ['s. 1'] and 'ⲁⲩⲱ <mark class="bg-yellow-200">ⲡⲛⲟⲩⲧⲉ</mark>' in rows[0]['highlighted_text']


def test_search_file_types_a_coptic_file_as_prose_by_its_language(tmp_path):
    # No author or marker in the name, so only the language says prose.
    cop = tmp_path / 'zzunlisted.sample.tess'
    cop.write_text('<z. 1>\t' + 'ⲁⲩⲱ ⲡⲛⲟⲩⲧⲉ ⲙⲁⲣⲉϥ ' * 3 + '\n', encoding='utf-8')
    rows = ws.search_file(str(cop), ws.parse_query('ⲡⲛⲟⲩⲧⲉ'), False, 'cop')
    assert rows[0]['is_prose'] is True


def test_search_file_prose_line_is_cut_to_the_matching_sentence(tmp_path):
    p = tmp_path / 'cicero.in_catilinam.tess'
    long = 'Quo usque tandem abutere, Catilina, patientia nostra. ' * 3 + 'Quam diu etiam furor iste tuus nos eludet! Nihil agis. '
    p.write_text('<cat. 1.1>\t' + long + '\n', encoding='utf-8')
    rows = ws.search_file(str(p), ws.parse_query('furor'), False, 'la')
    assert rows == [{
        'ref': 'cat. 1.1',
        'text': 'Quam diu etiam furor iste tuus nos eludet!',
        'highlighted_text': 'Quam diu etiam <mark class="bg-yellow-200">furor</mark> iste tuus nos eludet!',
        'is_prose': True}]


# ---- wildcard_search over the fixture folder -------------------------------

@pytest.fixture
def fixture_corpus(monkeypatch):
    monkeypatch.setattr(ws, 'TEXTS_DIR', FIX_ROOT)


def test_wildcard_search_exact_rows(fixture_corpus):
    out = ws.wildcard_search('la', 'arma OR multa')
    out['search_time'] = 0                                   # timing varies
    assert out == {
        'results': [
            {'ref': 'test. 1.1', 'text': 'Arma virumque cano, Troiae qui primus ab oris',
             'highlighted_text': '<mark class="bg-yellow-200">Arma</mark> virumque cano, Troiae qui primus ab oris',
             'is_prose': False, 'text_id': 'test.mini.tess', 'author': 'Test', 'title': 'Mini',
             'display_name': 'Test, Mini', 'era': 'Augustan', 'year': -19, 'is_poetry': True,
             'reference': 'test. 1.1'},
            {'ref': 'test. 1.5', 'text': 'multa quoque et bello passus, dum conderet urbem,',
             'highlighted_text': '<mark class="bg-yellow-200">multa</mark> quoque et bello passus, dum conderet urbem,',
             'is_prose': False, 'text_id': 'test.mini.tess', 'author': 'Test', 'title': 'Mini',
             'display_name': 'Test, Mini', 'era': 'Augustan', 'year': -19, 'is_poetry': True,
             'reference': 'test. 1.5'},
        ],
        'total_matches': 2, 'truncated': False, 'texts_searched': 1, 'total_texts': 1,
        'search_time': 0, 'query': 'arma OR multa', 'parsed_type': 'or',
        'matching': {'mode': 'literal', 'rules': 'string-fold-2',
                     'query': 'arma OR multa', 'query_used': 'arma OR multa'}}


def test_wildcard_search_target_text_truncation_and_errors(fixture_corpus):
    assert ws.wildcard_search('la', 'arma', target_text='test.mini')['total_matches'] == 1      # .tess added
    assert ws.wildcard_search('la', 'arma', target_text='test.mini.tess')['total_matches'] == 1
    assert ws.wildcard_search('la', 'arma', target_text='nope')['total_texts'] == 0
    cut = ws.wildcard_search('la', 'arma OR multa', max_results=1)
    assert cut['truncated'] is True and len(cut['results']) == 1 and cut['total_matches'] == 2
    assert ws.wildcard_search('xx', 'arma') == {
        'results': [], 'total_matches': 0, 'search_time': 0, 'error': 'No texts found for language: xx'}
    assert ws.wildcard_search('la', '') == {
        'results': [], 'total_matches': 0, 'search_time': 0, 'query': '',
        'parsed': {'type': 'empty', 'terms': []},
        'matching': {'mode': 'literal', 'rules': 'string-fold-2', 'query': '', 'query_used': ''}}


# ---- spelling modes leave the other languages alone ------------------------------

def test_spelling_parameter_changes_nothing_for_latin(tmp_path):
    f = tmp_path / 'a.b.tess'
    f.write_text('<a.b.1>\tarma virumque cano\n<a.b.2>\tAmor vincit omnia\n', encoding='utf-8')
    node = ws.parse_query('arma OR amor')
    base = ws.search_file(str(f), node, False, 'la')
    for spelling in (None, 'variants', 'strict'):
        assert ws.search_file(str(f), node, False, 'la', spelling) == base
    assert [r['ref'] for r in base] == ['a.b.1', 'a.b.2']


def test_strict_spelling_matches_old_literal_search_for_persian(tmp_path):
    f = tmp_path / 'a.b.tess'
    f.write_text('<a.b.1>\tکاغذِ آتش\n<a.b.2>\tکاغذ آتش\n', encoding='utf-8')
    node = ws.parse_query('کاغذ آتش', 'strict')
    rows = ws.search_file(str(f), node, False, 'fa', 'strict')
    assert [r['ref'] for r in rows] == ['a.b.2']
