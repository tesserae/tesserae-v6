"""String Search spelling variants for Persian, Urdu, Arabic and Hebrew.

Unit tests for backend/string_fold.py, the separator rule, the trimming of the
query and the match notes, on synthetic lines; then acceptance tests against
the real corpus. The corpus tests read texts/fa, texts/ur and texts/he of the
checkout, or the folder named by TESSERAE_TEST_TEXTS_DIR, and skip when the
folder is absent.
"""
import os
import re

import pytest

from backend import wildcard_search as ws
from backend.string_fold import RULES_LABEL, fold_arabic_script, fold_hebrew_script

IGN = re.IGNORECASE
ZW = '‌'


# ---- the two fold functions ------------------------------------------------

def test_fold_removes_vowel_marks_and_ornaments():
    assert fold_arabic_script('کاغذِ') == 'کاغذ'                 # kasra
    assert fold_arabic_script('مُحَمَّد') == 'محمد'               # damma, fatha, shadda
    assert fold_arabic_script('الرَّحْمٰن') == 'الرحمن'            # dagger alef
    assert fold_arabic_script('عـــرب') == 'عرب'                  # tatweel
    assert fold_arabic_script('a‍b') == 'ab'                # zero-width joiner
    assert fold_arabic_script('‏دل‬') == 'دل'          # direction marks


def test_fold_letter_variants():
    assert fold_arabic_script('كتاب') == 'کتاب'                   # Arabic kaf
    assert fold_arabic_script('يد') == 'ید'                       # Arabic yeh
    assert fold_arabic_script('على') == 'علی'                     # alef maqsura
    h = fold_arabic_script('ه')
    assert fold_arabic_script('ہ') == h                           # heh goal
    assert fold_arabic_script('ة') == h                           # teh marbuta
    assert fold_arabic_script('ۃ') == h                           # teh marbuta goal
    assert fold_arabic_script('أحمد') == 'احمد'
    assert fold_arabic_script('إسلام') == 'اسلام'
    assert fold_arabic_script('ٱلکتاب') == 'الکتاب'


def test_fold_keeps_distinct_letters_and_the_non_joiner():
    for kept in ('آ', 'ے', 'ۓ', 'ھ', 'ں', 'ٹ', 'ڈ', 'ڑ', 'ژ', 'گ', 'پ', 'چ', 'ۀ', ZW):
        assert fold_arabic_script(kept) == kept
    assert fold_arabic_script('آتش' + ZW + 'زده') == 'آتش' + ZW + 'زده'


def test_fold_no_op_line_folds_to_itself():
    line = 'دل من آتش' + ZW + 'زده گل'
    assert fold_arabic_script(line) == line
    assert fold_arabic_script('plain ascii') == 'plain ascii'
    assert fold_hebrew_script('דבר') == 'דבר'


def test_fold_families_can_be_left_out():
    assert fold_arabic_script('كِتاب', marks=False) == 'کِتاب'
    assert fold_arabic_script('كِتاب', letters=False) == 'كتاب'


def test_fold_hebrew():
    assert fold_hebrew_script('קֹהֶ֣לֶת') == 'קהלת'
    assert fold_hebrew_script('בֶּן־דָּוִ֔ד') == 'בן־דוד'          # maqaf kept
    assert fold_hebrew_script('שָׁלוֹם') == 'שלום'
    assert fold_hebrew_script('דבר', marks=False) == 'דבר'


# ---- the separator rule and trimming, on synthetic lines ------------------------

def hit(query, line, language='fa', spelling='variants'):
    mode = ws.spelling_mode(language, spelling)
    node = ws.parse_query(query, mode)
    matcher = ws._build_matcher(node, IGN, language, spelling)
    return matcher(ws._search_text(line, language, spelling))


SPACED = 'مزرعی چون آتش زده گل'
NONJOINED = 'مزرعی چون آتش' + ZW + 'زده گل'
JOINED = 'مزرعی چون آتشزده گل'


@pytest.mark.parametrize('query', ['آتش زده', 'آتش' + ZW + 'زده', 'آتش ' + ZW + 'زده', '"آتش زده"'])
def test_separator_in_query_matches_any_separator_or_none(query):
    assert hit(query, SPACED) and hit(query, NONJOINED) and hit(query, JOINED)


def test_joined_query_matches_only_the_joined_spelling():
    assert hit('آتشزده', JOINED)
    assert not hit('آتشزده', SPACED)
    assert not hit('آتشزده', NONJOINED)


def test_strict_mode_matches_the_characters_as_typed():
    assert hit('آتش زده', SPACED, spelling='strict')
    assert not hit('آتش زده', NONJOINED, spelling='strict')
    assert not hit('آتش زده', JOINED, spelling='strict')
    assert hit('آتش' + ZW + 'زده', NONJOINED, spelling='strict')
    assert not hit('آتش' + ZW + 'زده', SPACED, spelling='strict')


def test_separator_rule_in_wildcard_and_boolean_terms():
    assert hit('آتش* زده', NONJOINED)
    assert hit('چون AND آتش' + ZW + 'زده', SPACED)
    assert hit('گل ~ آتش زده', JOINED)


def test_edges_are_trimmed_in_both_modes():
    for spelling in ('variants', 'strict'):
        assert hit('آتش' + ZW, 'مزرعی آتش' + ZW + 'زده گل', spelling=spelling)
        assert hit(ZW + ' آتش ' + ZW, 'مزرعی آتش زده', spelling=spelling)
        assert hit('"آتش زده' + ZW + '"', SPACED, spelling=spelling)
        assert hit('آتش' + ZW + ' AND زده' + ZW, SPACED, spelling=spelling)
    assert ws.parse_query(ZW + ' ' + ZW, 'variants')['type'] == 'empty'


def test_word_boundary_before_a_non_joiner_in_the_text():
    assert hit('آتش', NONJOINED)
    assert hit('زده', NONJOINED)


def test_marks_and_letters_in_query_or_text():
    assert hit('کاغذ', 'کاغذِ آتش')
    assert hit('کاغذِ', 'کاغذ آتش')
    assert hit('كاغذ', 'کاغذ آتش')
    assert hit('کاغذ', 'کاغِذ آتش')
    assert not hit('کاغذ', 'کاغِذ آتش', spelling='strict')
    assert not hit('كاغذ', 'کاغذ آتش', spelling='strict')


def test_distinct_letters_stay_apart():
    assert not hit('اب', 'آب')
    assert not hit('دل', 'دںل')


def test_other_languages_are_not_trimmed_or_folded():
    assert ws.spelling_mode('la') == 'literal'
    assert ws.spelling_mode('fa') == 'variants'
    assert ws.spelling_mode('fa', 'strict') == 'strict'
    assert ws.spelling_mode('grc', 'strict') == 'literal'
    assert ws.parse_query('amor', 'literal') == ws.parse_query('amor')
    assert ws.parse_term('a b')['pattern'] == re.escape('a b')


# ---- a small synthetic corpus: the response block, notes and highlighting ----------

@pytest.fixture
def tiny(tmp_path, monkeypatch):
    d = tmp_path / 'ur'
    d.mkdir()
    (d / 'x.poem.tess').write_text(
        '<x.poem.1>\tبسان کاغذ آتش زدہ مرے گلرو\n'
        '<x.poem.2>\tبہ رنگِ کاغذِ آتش زدہ نیرنگ\n'
        '<x.poem.3>\tیک كاغذ آتش زدہ دشت\n', encoding='utf-8')
    monkeypatch.setattr(ws, 'TEXTS_DIR', str(tmp_path))
    monkeypatch.setattr(ws, 'get_author_dates', lambda: {})
    monkeypatch.setattr(ws, 'get_text_metadata', lambda p: {})
    return tmp_path


def test_matching_block_and_notes(tiny):
    r = ws.wildcard_search('ur', ' کاغذ آتش' + ZW, max_results=50)
    assert r['matching'] == {'mode': 'variants', 'rules': RULES_LABEL,
                             'query': ' کاغذ آتش' + ZW, 'query_used': 'کاغذ آتش'}
    notes = {x['ref']: x['match_note'] for x in r['results']}
    assert notes['x.poem.1'] == []
    assert notes['x.poem.2'] == ['vowel marks ignored']
    assert notes['x.poem.3'] == ['letter variant matched']


def test_strict_mode_response(tiny):
    r = ws.wildcard_search('ur', 'کاغذ آتش', max_results=50, spelling='strict')
    assert r['matching']['mode'] == 'strict'
    assert [x['ref'] for x in r['results']] == ['x.poem.1']
    assert 'match_note' not in r['results'][0]


def test_other_language_reports_literal(tiny, monkeypatch):
    (tiny / 'la').mkdir()
    (tiny / 'la' / 'a.b.tess').write_text('<a.b.1>\tarma virumque cano\n', encoding='utf-8')
    r = ws.wildcard_search('la', 'arma', max_results=5, spelling='strict')
    assert r['matching']['mode'] == 'literal'
    assert 'match_note' not in r['results'][0]


def test_highlight_covers_whole_tokens_and_phrases(tiny):
    r = ws.wildcard_search('ur', 'کاغذ آتش', max_results=50)
    row = [x for x in r['results'] if x['ref'] == 'x.poem.2'][0]
    assert '<mark class="bg-yellow-200">کاغذِ آتش</mark>' in row['highlighted_text']
    row3 = [x for x in r['results'] if x['ref'] == 'x.poem.3'][0]
    assert '<mark class="bg-yellow-200">كاغذ آتش</mark>' in row3['highlighted_text']


def test_separator_note(tiny):
    (tiny / 'ur' / 'y.poem.tess').write_text(
        '<y.poem.1>\tیک کاغذ آتش' + ZW + 'زدہ دشت\n', encoding='utf-8')
    r = ws.wildcard_search('ur', 'آتش زدہ', max_results=50)
    notes = {x['ref']: x['match_note'] for x in r['results']}
    assert notes['y.poem.1'] == ['separator variant matched']
    assert notes['x.poem.1'] == []


# ---- the real corpus ---------------------------------------------------------

def _texts_root():
    root = os.environ.get('TESSERAE_TEST_TEXTS_DIR')
    if root:
        return root
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')


@pytest.fixture
def corpus(monkeypatch):
    root = _texts_root()
    if not (os.path.isdir(os.path.join(root, 'ur')) and os.path.isdir(os.path.join(root, 'fa'))):
        pytest.skip('texts/ur and texts/fa are not present')
    monkeypatch.setattr(ws, 'TEXTS_DIR', root)
    monkeypatch.setattr(ws, 'get_author_dates', lambda: {})
    return root


def refs(language, query, spelling, **kw):
    r = ws.wildcard_search(language, query, max_results=100000, spelling=spelling, **kw)
    return {x['ref']: x for x in r['results']}


PLAIN = 'کاغذ آتش'
MARKED = 'کاغذِ آتش'
TRAILING = 'کاغذ آتش' + ZW
URDU_FOUR = {'dard.diwan_wikisource.21.4', 'azad.ab_e_hayat.22.176',
             'ghalib.diwan_wikisource.ghazal.79.3', 'ghalib.diwan_wikisource.ghazal.85.3'}


def test_urdu_variants_plain_and_marked_agree(corpus):
    plain = refs('ur', PLAIN, 'variants')
    marked = refs('ur', MARKED, 'variants')
    assert set(plain) == set(marked)
    present = {r for r in URDU_FOUR if os.path.exists(os.path.join(corpus, 'ur', r.rsplit('.', 2)[0] + '.tess'))
               or r.startswith('azad') is False}
    if not os.path.exists(os.path.join(corpus, 'ur', 'azad.ab_e_hayat.tess')):
        present.discard('azad.ab_e_hayat.22.176')
    assert present <= set(plain)
    assert len(present) >= 3


def test_urdu_match_notes(corpus):
    plain = refs('ur', PLAIN, 'variants')
    marked = refs('ur', MARKED, 'variants')
    for ref in ('ghalib.diwan_wikisource.ghazal.79.3', 'ghalib.diwan_wikisource.ghazal.85.3'):
        assert plain[ref]['match_note'] == ['vowel marks ignored']
        assert marked[ref]['match_note'] == []
    for ref in ('dard.diwan_wikisource.21.4', 'azad.ab_e_hayat.22.176'):
        if ref in plain:
            assert plain[ref]['match_note'] == []
            assert marked[ref]['match_note'] == ['vowel marks ignored']


def test_persian_variants_trailing_nonjoiner_and_plain_agree(corpus):
    plain = refs('fa', PLAIN, 'variants')
    trailing = refs('fa', TRAILING, 'variants')
    marked = refs('fa', MARKED, 'variants')
    assert set(plain) == set(trailing) == set(marked)
    assert len(plain) >= 29
    bidel = {'bidel.diwan.%d' % n for n in (13047, 18443, 19782, 41347, 54541)}
    assert bidel <= set(plain)


def test_strict_mode_counts(corpus):
    """Strict mode matches the characters as typed. The trailing non-joiner is
    trimmed in both modes, so the query that returned 5 Persian lines and 0
    Urdu lines before this change now returns the plain query's 29 and 2."""
    assert [len(refs('fa', q, 'strict')) for q in (TRAILING, PLAIN, MARKED)] == [29, 29, 0]
    ur = [len(refs('ur', q, 'strict')) for q in (TRAILING, PLAIN, MARKED)]
    assert ur[0] == ur[1] and ur[2] == 2
    assert ur[1] >= 1


@pytest.mark.parametrize('language,spelling', [('ur', 'variants'), ('ur', 'strict'),
                                               ('fa', 'variants'), ('fa', 'strict')])
def test_quoted_and_unquoted_phrase_agree(corpus, language, spelling):
    assert set(refs(language, PLAIN, spelling)) == set(refs(language, '"%s"' % PLAIN, spelling))


def test_hebrew_pointed_and_unpointed_agree(corpus):
    if not os.path.exists(os.path.join(corpus, 'he', 'hebrew_bible.ecclesiastes.tess')):
        pytest.skip('texts/he is not present')
    kw = {'target_text': 'hebrew_bible.ecclesiastes'}
    pointed = refs('he', 'קֹהֶ֣לֶת', 'variants', **kw)
    plain = refs('he', 'קהלת', 'variants', **kw)
    assert pointed and set(pointed) == set(plain)
    assert not refs('he', 'קהלת', 'strict', **kw)
