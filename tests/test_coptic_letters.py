"""The seven Coptic-only letters keep their own code points.

Shei, fei, khei, hori, gangia, shima and dei have one home in Unicode,
U+03E2-03EF. Until 2026-09-27 the normaliser moved them to U+2CB2-2CBF,
which Unicode assigns to seven other letters (Dialect-P alef, Old Coptic
ain, and so on). Matching never noticed, because both sides moved alike,
but every stored form carried the wrong letters, and two display
work-arounds existed only to move them back for the reader (issue #493).

In our texts U+2CB2-2CBF occur only as editorial marks, and the tokenizer
counted them as letters, so ':ⲻⲁⲗⲗⲁ' indexed as a word beginning with
gangia. They are stripped.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.coptic.processor import normalize_coptic, tokenize_coptic  # noqa: E402

SEVEN = 'ϣϥϧϩϫϭϯ'
WRONG = ''.join(chr(0x2CB2 + k) for k in range(14))


class TestTheSevenLettersStayPut:
    def test_each_letter_is_its_own_normal_form(self):
        for ch in SEVEN:
            assert normalize_coptic(ch) == ch

    def test_a_word_with_shei_keeps_shei(self):
        assert normalize_coptic('ϣⲏⲣⲉ') == 'ϣⲏⲣⲉ'
        assert normalize_coptic('Ϣⲏⲣⲉ') == 'ϣⲏⲣⲉ'

    def test_nothing_lands_in_the_wrong_block(self):
        out = normalize_coptic('ⲡⲉϩⲟⲟⲩ ⲛϣⲱⲡⲉ ϥⲉⲓ ⲧϭⲓⲛ ϯⲡⲟⲗⲉⲓⲥ')
        assert not re.search('[Ⲳ-ⲿ]', out)


class TestTheStrayMarksGo:
    def test_a_standalone_mark_vanishes(self):
        assert normalize_coptic('ⲻ') == ''
        assert normalize_coptic('ⲻⲻⲻ') == ''

    def test_a_mark_glued_to_a_word_leaves_the_word(self):
        # ':ⲻⲁⲗⲗⲁ' in the Apophthegmata; ⲻ is U+2CBB, which used to read as gangia
        assert normalize_coptic('ⲻⲁⲗⲗⲁ') == 'ⲁⲗⲗⲁ'

    def test_tokenizer_output_carries_no_marks(self):
        _orig, norm = tokenize_coptic('<x 1> ⲁⲛⲟⲕ :ⲻⲁⲗⲗⲁ ϩⲛ ⲧⲉϩⲟⲩⲉⲓⲧⲉ ⲻⲻⲻ')
        assert 'ⲁⲗⲗⲁ' in norm and 'ϩⲛ' in norm
        assert not any(re.search('[Ⲳ-ⲿ]', t) for t in norm)
        assert '' not in norm


class TestTheStoredFormsAreRight:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_the_dictionaries_and_stoplist_hold_no_wrong_letters(self):
        for rel in ('backend/synonymy/v6_additions/coptic_greek.csv',
                    'backend/synonymy/coptic_greek_loanwords.csv',
                    'backend/synonymy/coptic_greek_ddglc.csv',
                    'backend/coptic/stopwords.py'):
            text = open(os.path.join(self.ROOT, rel), encoding='utf-8').read()
            assert not re.search('[Ⲳ-ⲿ]', text), rel

    def test_the_stoplist_keeps_its_particles(self):
        from backend.coptic.stopwords import COPTIC_STOP_WORDS
        assert 'ϩⲛ' in COPTIC_STOP_WORDS or 'ϩⲉⲛ' in COPTIC_STOP_WORDS
        assert 'ϯ' in COPTIC_STOP_WORDS


class TestTheRestoreTool:
    def test_one_code_point_to_one_code_point(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'restore', os.path.join(self.ROOT if hasattr(self, 'ROOT') else os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    'scripts', 'corpus', 'restore_coptic_letters.py'))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        assert mod.restore(WRONG) == ''.join(chr(0x03E2 + k) for k in range(14))
        assert mod.restore('ⲳⲏⲣⲉ') == 'ϣⲏⲣⲉ'
        assert mod.count_wrong('ⲳⲏⲣⲉ ⲹⲛ') == 2
        assert mod.restore('ⲣⲱⲙⲉ') == 'ⲣⲱⲙⲉ'


class TestTheMatcherAndTheHelpPage:
    def test_the_greek_shadow_map_knows_the_seven_letters_once(self):
        from backend.matcher import _COPTIC_TO_GREEK
        for ch in SEVEN:
            assert ch in _COPTIC_TO_GREEK, ch
        for ch in WRONG:
            assert ch not in _COPTIC_TO_GREEK, hex(ord(ch))

    def test_the_stoplist_display_is_the_stoplist(self):
        from backend import matcher
        assert not hasattr(matcher, '_COPTIC_DISPLAY')
