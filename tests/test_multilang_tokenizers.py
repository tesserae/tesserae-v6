"""Unit tests for the Persian/Urdu/Arabic tokenizers ported in Phase 3 of the
multilang deploy plan (DEPLOY_PLAN_2026-09-03.md).

Pure-function tests only (no server, DB, corpus, or Stanza model load): each
processor's tokenize_*/normalize_* functions are plain regex/string code, so
these run fast and need no network or GPU. Lemmatization (which lazy-loads a
Stanza pipeline) is intentionally NOT exercised here -- see the language
plugins' own degrade-gracefully behavior, covered by registration, not by
loading a ~100s-cold-start model in the standard suite.

Run: pytest tests/test_multilang_tokenizers.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestPersianTokenizer:
    def test_tokenizes_perso_arabic_script(self):
        from backend.persian.processor import tokenize_persian
        original, normalized = tokenize_persian('به نام خداوند جان و خرد')
        assert original == ['به', 'نام', 'خداوند', 'جان', 'و', 'خرد']
        assert len(normalized) == len(original)

    def test_normalize_folds_ya_and_kaf_to_arabic_forms(self):
        from backend.persian.processor import normalize_persian
        # Persian ya (U+06CC) -> Arabic ya (U+064A)
        assert normalize_persian('ی') == 'ي'
        # Persian kaf (U+06A9) -> Arabic kaf (U+0643)
        assert normalize_persian('ک') == 'ك'

    def test_normalize_strips_tashkeel_and_zwnj(self):
        from backend.persian.processor import normalize_persian
        # fatha (U+064B) and ZWNJ (U+200C) should both disappear
        assert 'ً' not in normalize_persian('بً')
        assert '‌' not in normalize_persian('می‌نویسیم')

    def test_strips_tess_reference_tags(self):
        from backend.persian.processor import tokenize_persian
        original, _ = tokenize_persian('<saadi.bustan.1.1> به نام خداوند جان')
        assert 'saadi' not in ''.join(original)
        assert original == ['به', 'نام', 'خداوند', 'جان']

    def test_handler_registers_expected_interface(self):
        from backend.persian.processor import PersianLanguageHandler
        h = PersianLanguageHandler()
        for method in ('tokenize', 'lemmatize_word', 'split_into_phrases', 'ends_sentence'):
            assert callable(getattr(h, method))


class TestArabicTokenizer:
    def test_tokenizes_arabic_script(self):
        from backend.arabic.processor import tokenize_arabic
        original, normalized = tokenize_arabic('بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ')
        assert len(original) == 4
        assert len(normalized) == 4

    def test_normalize_strips_tashkeel(self):
        from backend.arabic.processor import normalize_arabic
        vocalized = 'بِسْمِ'
        stripped = normalize_arabic(vocalized)
        # no diacritics (fatha/kasra/sukun) should survive
        assert not any(0x064B <= ord(c) <= 0x0652 for c in stripped)

    def test_normalize_folds_alif_variants(self):
        from backend.arabic.processor import normalize_arabic
        for variant in ('أ', 'إ', 'آ', 'ٱ'):
            assert normalize_arabic(variant) == 'ا'

    def test_shared_hemistich_shares_normalized_tokens(self):
        # T-A1 flagship pair from the audit: Imru' al-Qays / Tarafa share 9 of
        # 10 normalized tokens in this hemistich (differ only in rhyme word).
        from backend.arabic.processor import tokenize_arabic
        iq = 'وقوفا بها صحبي علي مطيهم يقولون لا تهلك اسي وتجملي'
        tf = 'وقوفا بها صحبي علي مطيهم يقولون لا تهلك اسي وتجلدي'
        _, iq_norm = tokenize_arabic(iq)
        _, tf_norm = tokenize_arabic(tf)
        shared = sum(1 for a, b in zip(iq_norm, tf_norm) if a == b)
        assert shared >= 9


class TestUrduTokenizer:
    def test_tokenizes_urdu_script(self):
        from backend.urdu.processor import tokenize_urdu
        original, normalized, breaks = tokenize_urdu('دل ناداں تجھے ہوا کیا ہے')
        assert original == ['دل', 'ناداں', 'تجھے', 'ہوا', 'کیا', 'ہے']
        assert len(normalized) == len(original)
        assert breaks == []  # no hemistich separator in this line

    def test_normalize_folds_ya_and_kaf(self):
        from backend.urdu.processor import normalize_urdu
        assert normalize_urdu('ی') == 'ي'
        assert normalize_urdu('ک') == 'ك'

    # --- Hemistich fix (gap A6, AUDIT_2026-09-03.md #6) ---
    #
    # Urdu couplets are stored as two hemistichs joined by a literal '|':
    # "<mir.diwan.1.1>  misra1 | misra2". The radif (refrain) and qafia
    # (rhyme) sit at the end of EACH hemistich. Before this fix the
    # tokenizer silently dropped '|', fusing both hemistichs into one
    # undifferentiated token run with the boundary unrecoverable. These
    # tests prove both positions poetics analysis needs are now recoverable
    # straight from tokenize_urdu's output.

    def test_hemistich_break_recovers_last_word_of_first_hemistich(self):
        from backend.urdu.processor import tokenize_urdu
        # A synthetic couplet: two words per hemistich.
        original, normalized, breaks = tokenize_urdu('پہلا مصرعہ | دوسرا مصرعہ')
        assert original == ['پہلا', 'مصرعہ', 'دوسرا', 'مصرعہ']
        assert breaks == [1]
        # tokens[breaks[0]] is the last word of the FIRST hemistich
        assert original[breaks[0]] == 'مصرعہ'

    def test_final_word_of_line_is_always_the_last_token(self):
        from backend.urdu.processor import tokenize_urdu
        original, normalized, breaks = tokenize_urdu('پہلا مصرعہ | دوسرا لفظ')
        # end-of-line word (radif/qafia position for the second hemistich)
        # is simply the last token -- unaffected by the fix, still recoverable
        assert original[-1] == 'لفظ'
        assert original[-1] != original[breaks[0]]

    def test_pipe_is_never_emitted_as_a_token(self):
        from backend.urdu.processor import tokenize_urdu
        original, normalized, breaks = tokenize_urdu('پہلا مصرعہ | دوسرا مصرعہ')
        assert '|' not in original
        assert '|' not in normalized

    def test_line_without_pipe_has_no_hemistich_breaks(self):
        # Both Ghalib editions are one hemistich per .tess line (no '|') --
        # confirm behavior for those files is unchanged by the fix.
        from backend.urdu.processor import tokenize_urdu
        original, normalized, breaks = tokenize_urdu('دل ناداں تجھے ہوا کیا ہے')
        assert breaks == []

    def test_multiple_hemistich_breaks_in_one_line(self):
        from backend.urdu.processor import tokenize_urdu
        original, normalized, breaks = tokenize_urdu('اے | بی | سی')
        assert original == ['اے', 'بی', 'سی']
        assert breaks == [0, 1]

    def test_handler_exposes_get_hemistich_breaks(self):
        from backend.urdu.processor import UrduLanguageHandler
        h = UrduLanguageHandler()
        breaks = h.get_hemistich_breaks('پہلا مصرعہ | دوسرا مصرعہ')
        assert breaks == [1]

    def test_handler_tokenize_and_lemmatize_returns_six_tuple_with_breaks(self):
        # text_processor._tokenize_and_lemmatize expects a 6th element
        # (hemistich_breaks) alongside the existing 5-tuple contract; confirm
        # the handler's shape without invoking Stanza (lemmatize_urdu
        # degrades to normalized forms when no Stanza pipeline is available,
        # so this does not require a model download).
        from backend.urdu.processor import UrduLanguageHandler
        h = UrduLanguageHandler()
        result = h.tokenize_and_lemmatize('پہلا مصرعہ | دوسرا مصرعہ')
        assert len(result) == 6
        original_tokens, tokens, lemmas, pos_tags, variant_lemmas, hemistich_breaks = result
        assert hemistich_breaks == [1]
        assert variant_lemmas == []
        assert len(lemmas) == len(tokens) == len(pos_tags) == 4


<<<<<<< HEAD
=======
@pytest.mark.skip(
    reason="stage 2b: backend.text_processor.TextProcessor._tokenize_and_lemmatize "
           "returns a 5-tuple on main (no hemistich_breaks) and process_line() does "
           "not set a hemistich_breaks key; the hemistich-break propagation hook for "
           "Persian/Urdu/Arabic line splitting is not yet applied to text_processor.py."
)
>>>>>>> origin/main
class TestTextProcessorHemistichPropagation:
    """Confirm text_processor.py's dispatcher (the shared module) carries the
    6th tuple element through additively -- Latin/Greek/English/Coptic/Hebrew
    all still get an empty hemistich_breaks list, and process_line surfaces
    it in the returned unit dict for Urdu."""

    def test_latin_gets_empty_hemistich_breaks(self):
        from backend.text_processor import TextProcessor
        tp = TextProcessor()
        original_tokens, tokens, lemmas, pos_tags, variant_lemmas, hemistich_breaks = \
            tp._tokenize_and_lemmatize('arma virumque cano', 'la')
        assert hemistich_breaks == []

    def test_process_line_surfaces_hemistich_breaks_for_urdu(self):
        from backend.urdu import register as register_urdu
        register_urdu()
        from backend.text_processor import TextProcessor
        tp = TextProcessor()
        unit = tp.process_line('پہلا مصرعہ | دوسرا مصرعہ', language='ur')
        assert unit['hemistich_breaks'] == [1]
        assert unit['tokens'][unit['hemistich_breaks'][0]] == unit['tokens'][1]
