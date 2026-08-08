"""Unit tests for the Coptic rare-words helpers in backend/blueprints/hapax.py.

Pure-function tests (no server, DB, or corpus needed):
  - _coptic_manuscript_form: normalized lemma -> manuscript spelling
  - _is_coptic_aggregate: excludes combined/duplicate corpus files
  - _clean_coptic_lemma: trims transcription-artifact edges

Run: pytest tests/test_coptic_rare_words.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestCopticManuscriptForm:
    def test_reverses_normalized_special_letters(self):
        from backend.blueprints.hapax import _coptic_manuscript_form
        # normalized ⲳⲏⲣⲉ (son) -> manuscript ϣⲏⲣⲉ; ⲹⲛ (in) -> ϩⲛ
        assert _coptic_manuscript_form('ⲳⲏⲣⲉ') == 'ϣⲏⲣⲉ'
        assert _coptic_manuscript_form('ⲹⲛ') == 'ϩⲛ'
        assert _coptic_manuscript_form('ⲡⲉⲵ') == 'ⲡⲉϥ'

    def test_roundtrips_with_normalize_coptic(self):
        from backend.blueprints.hapax import _coptic_manuscript_form
        from backend.coptic.processor import normalize_coptic
        for norm in ['ⲳⲏⲣⲉ', 'ⲥⲹⲓⲙⲉ', 'ⲉⲹⲣⲁⲓ', 'ⲛⲧⲟⲵ']:
            assert normalize_coptic(_coptic_manuscript_form(norm)) == norm

    def test_plain_letters_unchanged(self):
        from backend.blueprints.hapax import _coptic_manuscript_form
        assert _coptic_manuscript_form('ⲣⲱⲙⲉ') == 'ⲣⲱⲙⲉ'  # "man" — no special letters


class TestIsCopticAggregate:
    def test_excludes_combined_corpora(self):
        from backend.blueprints.hapax import _is_coptic_aggregate
        for base in ['sahidic.bible', 'sahidic.ot', 'sahidica.nt',
                     'bohairic.bible', 'bohairic.ot', 'bohairic.nt', 'shenoute.all']:
            assert _is_coptic_aggregate(base) is True

    def test_excludes_hash_suffixed_variants(self):
        from backend.blueprints.hapax import _is_coptic_aggregate
        assert _is_coptic_aggregate('sahidic.bible-d26057f6d34d7007d4cef76e14fd6922') is True

    def test_keeps_individual_works(self):
        from backend.blueprints.hapax import _is_coptic_aggregate
        for base in ['sahidic.genesis', 'shenoute.abraham', 'mercurius',
                     'helias', 'besa.letters', 'sahidica.luke']:
            assert _is_coptic_aggregate(base) is False


class TestCleanCopticLemma:
    def test_strips_edge_artifacts(self):
        from backend.blueprints.hapax import _clean_coptic_lemma
        # inputs are normalized lemmas (special letters live in the Coptic block)
        assert _clean_coptic_lemma('(ⲣⲱⲙⲉ') == 'ⲣⲱⲙⲉ'
        assert _clean_coptic_lemma(' ⲣⲱⲙⲉ ') == 'ⲣⲱⲙⲉ'
        assert _clean_coptic_lemma('0ⲁ') == 'ⲁ'
        assert _clean_coptic_lemma('[.....]ⲩⲟ') == 'ⲩⲟ'

    def test_empty_and_all_junk(self):
        from backend.blueprints.hapax import _clean_coptic_lemma
        assert _clean_coptic_lemma('') == ''
        assert _clean_coptic_lemma('[...]') == ''
