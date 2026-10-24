"""The literal prefilter of Line Search's exact-phrase scan changes nothing but the time.

A file whose folded text lacks a spelling of some query word is skipped without
being read or scanned. These tests hold that to the plain scan (the same code
with the folded-text budget at zero, so no file is ever skipped) on files built
to be awkward, and hold the folding to the regex engine's own idea of case.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import utils  # noqa: E402
from backend.blueprints import line_search as LS  # noqa: E402
from backend.line_search_params import _read_params  # noqa: E402

FILES = {
    # Holds every word of "arma virum" but in the other order: kept by the
    # prefilter, rejected by the regex.
    'a.reversed.tess': '<a 1>\tvirum cano et arma\n<a 2>\tnihil\n',
    # Holds both words, adjacent, in Latin spellings with u for v.
    'a.match_u.tess': '<m 1>\tcano ARMA UIRUMQUE Troiae\n<m 2>\tnihil\n',
    # Lacks "virum": skipped.
    'a.lacks.tess': '<l 1>\tarma ferunt et bella\n<l 2>\tmulta\n',
    # A phrase across a line break does not match, as today.
    'a.break.tess': '<b 1>\tcano arma\n<b 2>\tvirumque Troiae\n',
    # Long s and a capital: the engine treats them as the same letters.
    'a.longs.tess': '<s 1>\tARMA VIRUMQUE ſunt\n',
    # A combining long solidus after a tag's bracket: scanned line by line.
    'a.solidus.tess': '<c 1≯\tarma virum cano\n',
    # The dotted capital I changes length when lower-cased: never skipped.
    'a.dotted.tess': '<d 1>\tİ arma virum\n',
}


@pytest.fixture
def lang_dir(tmp_path):
    for name, text in FILES.items():
        (tmp_path / name).write_text(text, encoding='utf-8')
    return str(tmp_path)


def scan(lang_dir, query, language='la', budget=None):
    saved = (dict(LS._EXACT_KEY_CACHE), LS.EXACT_KEY_BUDGET_BYTES, LS._EXACT_KEY_BYTES[0])
    LS._EXACT_KEY_CACHE.clear()
    LS._EXACT_KEY_BYTES[0] = 0
    if budget is not None:
        LS.EXACT_KEY_BUDGET_BYTES = budget
    try:
        params = _read_params({'query': query, 'language': language, 'search_type': 'exact', 'max_results': 500})
        first, _ = LS._scanned_candidates(params, lang_dir, {}, set(), set(), {}, {}, False)
        second, _ = LS._scanned_candidates(params, lang_dir, {}, set(), set(), {}, {}, False)
        return first, second
    finally:
        LS._EXACT_KEY_CACHE.clear()
        LS._EXACT_KEY_CACHE.update(saved[0])
        LS.EXACT_KEY_BUDGET_BYTES = saved[1]
        LS._EXACT_KEY_BYTES[0] = saved[2]


def loci(results):
    return [(r['text_id'], r['locus']) for r in results]


@pytest.mark.parametrize('query', ['arma virum', 'ARMA UIRUM', 'virum arma', 'arma virumque', 'cano', 'sunt',
                                   'arma vir', 'virumque troiae', 'nihil', 'absent word', 'arma  virum'])
def test_prefiltered_scan_equals_the_plain_scan(lang_dir, query):
    plain_first, plain_second = scan(lang_dir, query, budget=0)
    fast_first, fast_second = scan(lang_dir, query)
    assert plain_first == plain_second
    assert fast_first == plain_first        # first search: files read, folded text kept
    assert fast_second == plain_first       # second search: cached folded text used


def candidate_lines(text, query, language='la'):
    """The lines the kept-key route offers for a file, as the scan would compute them."""
    plan = utils.exact_prefilter_plan(query, language)
    key = LS._exact_key_store('x', (1, 1, plan['latin']), text)
    rxs = [re.compile(piece, re.IGNORECASE) for piece in plan['pieces']]
    return LS._exact_key_candidate_lines(key, plan, rxs, LS._exact_prefilter_pattern(query, language))


def test_words_out_of_order_are_kept_then_rejected(lang_dir):
    first, second = scan(lang_dir, 'arma virum')
    assert not any('reversed' in t for t, _ in loci(first))
    plan = utils.exact_prefilter_plan('arma virum', 'la')
    key = LS._exact_key_store('x', (1, 1, True), FILES['a.reversed.tess'])
    assert all(n in key for n in plan['needles'])                  # both words are there, so the file is not skipped by the word test
    assert not utils.exact_phrase_pattern('arma virum', 'la').search(FILES['a.reversed.tess'])
    assert candidate_lines(FILES['a.reversed.tess'], 'arma virum') == []   # and the order check rejects it


def test_a_file_lacking_a_word_is_skipped(lang_dir):
    assert candidate_lines(FILES['a.lacks.tess'], 'arma virum') == []
    key = LS._exact_key_store('x', (1, 1, True), FILES['a.lacks.tess'])
    assert not all(n in key for n in utils.exact_prefilter_plan('arma virum', 'la')['needles'])


def test_u_v_and_i_j_spellings_are_found(lang_dir):
    first, _ = scan(lang_dir, 'arma virum')
    texts = {t for t, _ in loci(first)}
    assert any('match_u' in t for t in texts)
    assert any('longs' in t for t in texts)
    assert candidate_lines('<a 1>\tIVVENIS erat\n<a 2>\tjuvenis erat\n<a 3>\tnihil\n', 'iuvenis') == [0, 1]
    assert candidate_lines('<a 1>\tIVVENIS erat\n', 'juuenis') == [0]


def test_a_phrase_over_several_blank_lines_and_odd_spaces(lang_dir):
    text = '<a 1>\tcano arma\n\n\n<a 2>\u00a0\u2003virum Troiae\n<a 3>\tarma\tvirum\n'
    truth = utils.exact_phrase_pattern('arma virum', 'la')
    want = {i for i, line in enumerate(text.split('\n')) if truth.search(line)}
    assert want <= set(candidate_lines(text, 'arma virum'))


def test_a_phrase_across_a_line_break_behaves_as_today(lang_dir):
    plain, _ = scan(lang_dir, 'cano arma virumque', budget=0)
    fast, _ = scan(lang_dir, 'cano arma virumque')
    assert fast == plain


def test_files_that_must_be_scanned_in_full_are_never_skipped(lang_dir):
    # Folding cannot be trusted here, so the entry is None and the file is scanned.
    assert LS._exact_key_store('x', (1, 1, True), FILES['a.solidus.tess']) is None
    assert LS._exact_key_store('x', (1, 1, True), FILES['a.dotted.tess']) is None


def test_a_changed_file_is_read_again(lang_dir, tmp_path):
    path = os.path.join(lang_dir, 'a.match_u.tess')
    params = _read_params({'query': 'tertium quid', 'language': 'la', 'search_type': 'exact'})
    LS._EXACT_KEY_CACHE.clear()
    LS._EXACT_KEY_BYTES[0] = 0
    assert LS._scanned_candidates(params, lang_dir, {}, set(), set(), {}, {}, False)[0] == []
    with open(path, 'a', encoding='utf-8') as f:
        f.write('<m 3>\ttertium quid est\n')
    results, _ = LS._scanned_candidates(params, lang_dir, {}, set(), set(), {}, {}, False)
    assert [r['locus'] for r in results] == ['3']
    LS._EXACT_KEY_CACHE.clear()
    LS._EXACT_KEY_BYTES[0] = 0


def test_budget_keeps_the_cache_bounded(lang_dir):
    first, second = scan(lang_dir, 'arma virum', budget=160)
    plain, _ = scan(lang_dir, 'arma virum', budget=0)
    assert first == second == plain


def test_prefold_agrees_with_the_regex_engines_case_rules():
    """Whatever the engine matches case-insensitively folds to the same text."""
    cased = [chr(c) for c in range(0x110000)
             if not 0xD800 <= c < 0xE000 and (chr(c).lower() != chr(c) or chr(c).upper() != chr(c))]
    chars = [chr(c) for c in range(0x20, 0x80)] + cased
    haystack = ''.join(chars)
    assert len(chars) < 5000
    for a in chars:
        fa = utils.exact_prefold(a)
        if fa is None:
            continue
        for m in re.findall(re.escape(a), haystack, re.IGNORECASE):
            fm = utils.exact_prefold(m)
            if fm is None:      # a text holding it is never skipped
                continue
            assert fm == fa, (hex(ord(a)), hex(ord(m)))


def test_the_dotted_capital_i_is_the_only_unsafe_character():
    odd = [chr(c) for c in range(0x110000) if len(chr(c).lower()) != 1]
    assert tuple(odd) == utils._PREFOLD_UNSAFE


def test_literals_for_a_greek_phrase_and_final_sigma():
    assert candidate_lines('<a 1>\tΟΔΥΣΣΕΎΣ ΘΕΆ\n', 'Οδυσσεύς θεά', 'grc') == [0]
    assert candidate_lines('<a 1>\tΟδυσσεύσ θεά\n', 'Οδυσσεύς θεά', 'grc') == [0]
    assert candidate_lines('<a 1>\tΟδυσσεύς ἀνήρ\n', 'Οδυσσεύς θεά', 'grc') == []
    assert utils.exact_prefold('ς') == utils.exact_prefold('σ')
    assert utils.exact_prefold('Σ') == utils.exact_prefold('ς')


def test_candidate_lines_hold_every_line_the_scan_would_match():
    import random
    rng = random.Random(21)
    alphabet = ['a', 'b', 'u', 'v', 'i', 'j', 'V', 'I', 'A', '\u017f', 's', ' ', ' ', '\n', '\t', '\u00a0', 'q']
    checked = 0
    for _ in range(4000):
        lines = [''.join(rng.choice(alphabet) for _ in range(rng.randint(0, 14))) for _ in range(rng.randint(1, 6))]
        text = '\n'.join(lines)
        words = [''.join(rng.choice(alphabet[:11]) for _ in range(rng.randint(1, 3))) for _ in range(rng.randint(1, 3))]
        query = ' '.join(words)
        for language in ('la', None):
            pattern = utils.exact_phrase_pattern(query, language)
            want = {i for i, line in enumerate(text.split('\n')) if pattern.search(utils.exact_search_text(line))}
            plan = utils.exact_prefilter_plan(query, language)
            if plan is None:
                continue
            got = set(candidate_lines(text, query, language))
            assert want <= got, (text, query, language, want, got)
            checked += len(want)
    assert checked > 200


def test_a_very_common_word_is_fast_and_finds_the_lines_the_one_pass_scan_finds():
    import time
    lines = [f'<a {i}>\tet cano et arma et virum et {"x" * (i % 7)} et' for i in range(6000)]
    lines[17] = '<a 17>\tnihil aliud'
    text = '\n'.join(lines) + '\n'
    started = time.time()
    got = candidate_lines(text, 'et')
    assert time.time() - started < 5            # a pass per match over the whole file took minutes
    old = LS._exact_candidate_lines(text, LS._exact_prefilter_pattern('et', 'la'))
    assert got == old
    assert 17 not in got and 16 in got
    two = candidate_lines(text, 'et cano')
    assert two == LS._exact_candidate_lines(text, LS._exact_prefilter_pattern('et cano', 'la'))
