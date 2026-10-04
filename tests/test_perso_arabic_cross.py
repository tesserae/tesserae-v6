"""Cross-language matching among Persian, Urdu and Arabic through the shared
comparison form (backend/perso_arabic.py), 2026-09-05."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.persian import register as _rfa  # noqa: E402
from backend.urdu import register as _rur  # noqa: E402
from backend.arabic import register as _rar  # noqa: E402
_rfa(); _rur(); _rar()

from backend.perso_arabic import cross_form, cross_variants, cross_stoplist  # noqa: E402

# stage 2b: backend.blueprints.search._find_shared_script_matches is the
# cross-lingual search wiring for these three languages and is not on main
# yet. Everything else this module imports (perso_arabic, the processors)
# is already in place, so only this import is guarded.
try:
    from backend.blueprints.search import (_find_shared_script_matches,  # noqa: E402,F401
                                           _longest_translated_run,
                                           VALID_CROSSLINGUAL_PAIRS)
    _MISSING_HOOK = None
except ImportError as _e:
    _MISSING_HOOK = str(_e)

pytestmark = pytest.mark.skipif(
    _MISSING_HOOK is not None,
    reason=f'stage 2b: {_MISSING_HOOK}',
)


def test_urdu_and_persian_spellings_meet():
    assert cross_form('ہمیشہ', 'ur') == cross_form('همیشه', 'fa')
    assert cross_form('گئے', 'ur').endswith('ي')
    assert cross_form('ٹھیک', 'ur') == 'تهيك'
    assert cross_form('نہیں', 'ur') == 'نهين'


def test_arabic_ta_marbuta_meets_persian_te_and_heh():
    assert 'رحمت' in cross_variants('رحمة', 'ar')
    assert cross_form('رحمة', 'ar') in cross_variants('رحمه', 'fa') | {cross_form('رحمه', 'fa')}
    assert cross_variants('رحمت', 'fa') & cross_variants('رحمة', 'ar')
    assert cross_form('مصطفى', 'ar') == cross_form('مصطفی', 'fa')


def test_stoplists_are_in_comparison_form():
    assert cross_form('ہے', 'ur') in cross_stoplist('ur')
    assert 'در' in cross_stoplist('fa')


def _u(ref, text, lang):
    from backend.persian.processor import tokenize_persian
    from backend.urdu.processor import tokenize_urdu
    from backend.arabic.processor import tokenize_arabic
    tk = {'fa': tokenize_persian, 'ur': tokenize_urdu, 'ar': tokenize_arabic}[lang](text)
    toks = list(tk[1] if isinstance(tk, tuple) else tk)
    return {'ref': ref, 'text': text, 'tokens': toks, 'lemmas': list(toks)}


def test_shared_words_match_across_urdu_and_persian_and_function_words_do_not():
    src = [_u('g.1', 'دل ہمیشہ عشق میں ہے', 'ur')]
    tgt = [_u('h.1', 'دل همیشه در عشق است', 'fa'), _u('h.2', 'خاک در چشم است', 'fa')]
    res = _find_shared_script_matches(src, tgt, 'ur', 'fa')
    assert (0, 0) in res and (0, 1) not in res
    matched = {wm['source_lemma'] for wm in res[(0, 0)]}
    assert cross_form('دل', 'ur') in matched and cross_form('عشق', 'ur') in matched
    assert cross_form('ہمیشہ', 'ur') in matched
    assert cross_form('ہے', 'ur') not in matched and cross_form('میں', 'ur') not in matched


def test_quranic_phrase_inside_a_persian_line_is_a_run():
    """An Arabic phrase quoted verbatim inside a Persian line: the shared
    words sit at consecutive positions on both sides, which the
    translated-run score rewards."""
    ar = [_u('q.1', 'إنا لله وإنا إليه راجعون', 'ar')]
    fa = [_u('r.1', 'گفت شاعر انا لله وانا اليه راجعون و بگریست', 'fa')]
    res = _find_shared_script_matches(ar, fa, 'ar', 'fa')
    assert (0, 0) in res
    assert _longest_translated_run(res[(0, 0)]) >= 4
    assert any(wm.get('function_word') for wm in res[(0, 0)])


def test_pairs_registered():
    for a, b in (('fa', 'ur'), ('ar', 'fa'), ('ar', 'ur')):
        assert frozenset((a, b)) in VALID_CROSSLINGUAL_PAIRS


def test_function_words_alone_make_no_pair():
    ar = [_u('q.1', 'وإنا إليه', 'ar')]
    fa = [_u('r.1', 'وانا اليه رفتیم', 'fa')]
    assert _find_shared_script_matches(ar, fa, 'ar', 'fa') == {}


def test_function_word_phrase_kept_as_a_verbatim_run():
    """'min kulli bab' (Q 13:23) has one content word; three shared words in a
    row still make a pair."""
    ar = [_u('q.1', 'والملائكة يدخلون عليهم من كل باب', 'ar')]
    fa = [_u('a.1', 'حق همی داند بری الساحتم من کل باب', 'fa')]
    res = _find_shared_script_matches(ar, fa, 'ar', 'fa')
    assert (0, 0) in res and _longest_translated_run(res[(0, 0)]) >= 3
