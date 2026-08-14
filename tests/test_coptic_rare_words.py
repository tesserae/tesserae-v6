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


class TestCopticCollation:
    """_rare_lemmata_sort_key collates Coptic by the normalized lemma so the
    Demotic-derived letters (ϣ ϥ ϩ ϫ ϭ) sort last, as in traditional Coptic
    order — not first, as they would by the manuscript display's legacy block."""

    def _order(self, language):
        from backend.blueprints.hapax import _rare_lemmata_sort_key
        recs = [
            {'lemma': 'ⲳⲏⲣⲉ', 'display': 'ϣⲏⲣⲉ', 'count': 1},   # shai
            {'lemma': 'ⲁⲣⲭⲏ', 'display': 'ⲁⲣⲭⲏ', 'count': 1},   # alfa
            {'lemma': 'ⲹⲛ', 'display': 'ϩⲛ', 'count': 1},        # hori
            {'lemma': 'ⲣⲱⲙⲉ', 'display': 'ⲣⲱⲙⲉ', 'count': 1},   # ro
        ]
        return [r['display'] for r in sorted(recs, key=lambda w: _rare_lemmata_sort_key(w, 'lemma', language))]

    def test_coptic_demotic_letters_sort_last(self):
        assert self._order('cop') == ['ⲁⲣⲭⲏ', 'ⲣⲱⲙⲉ', 'ϣⲏⲣⲉ', 'ϩⲛ']

    def test_non_coptic_unchanged_uses_display(self):
        # For non-cop the key is the display (legacy block), so ϣ/ϩ sort first
        assert self._order('la')[0] in ('ϣⲏⲣⲉ', 'ϩⲛ')


class TestScanTextLemmaLocations:
    """_scan_text_lemma_locations builds per-text locations from the current
    lemmatizer (used for Coptic, whose index lemma forms have drifted)."""

    def test_builds_locations_with_positions(self, monkeypatch):
        import backend.blueprints.hapax as hx
        monkeypatch.setattr(hx, '_texts_dir', '/texts')
        monkeypatch.setattr(hx, 'resolve_text_path', lambda *a, **k: '/texts/x.tess')

        class FakeTP:
            def process_file(self, path, language):
                return [
                    {'ref': 'sahidic.genesis.1.1', 'text': 'ⲁ ⲃ ⲅ',
                     'lemmas': ['ⲣⲱⲙⲉ', 'ⲛⲟⲩⲧⲉ', 'ⲣⲱⲙⲉ']},
                    {'ref': 'sahidic.genesis.1.2', 'text': 'ⲇ ⲉ',
                     'lemmas': ['ⲕⲁⲕⲉ', 'ⲛⲟⲩⲧⲉ']},
                ]
        monkeypatch.setattr(hx, '_text_processor', FakeTP())

        out = hx._scan_text_lemma_locations('sahidic.bible.tess', 'cop', {'ⲣⲱⲙⲉ', 'ⲛⲟⲩⲧⲉ'})
        assert out['ⲣⲱⲙⲉ'][0]['ref'] == 'sahidic.genesis.1.1'
        assert out['ⲣⲱⲙⲉ'][0]['positions'] == [0, 2]
        assert out['ⲣⲱⲙⲉ'][0]['text'] == 'ⲁ ⲃ ⲅ'
        assert len(out['ⲛⲟⲩⲧⲉ']) == 2
        assert out['ⲣⲱⲙⲉ'][0]['text_id'] == 'sahidic.bible.tess'

    def test_unresolvable_path_returns_empty(self, monkeypatch):
        import backend.blueprints.hapax as hx
        monkeypatch.setattr(hx, 'resolve_text_path', lambda *a, **k: None)
        assert hx._scan_text_lemma_locations('missing.tess', 'cop', {'x'}) == {}
