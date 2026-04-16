import json
import os
import sys
import unicodedata

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend import lemma_cache


@pytest.fixture
def isolated_cache_dirs(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache" / "lemmas"
    texts_dir = tmp_path / "texts"
    monkeypatch.setattr(lemma_cache, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(lemma_cache, "TEXTS_DIR", str(texts_dir))
    return cache_dir, texts_dir


def _write_text_file(texts_dir, language, filename, content="line one\nline two\n"):
    lang_dir = texts_dir / language
    lang_dir.mkdir(parents=True, exist_ok=True)
    path = lang_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestCachePathNaming:
    def test_greek_text_id_produces_ascii_only_cache_path(self, isolated_cache_dirs):
        cache_dir, _ = isolated_cache_dirs
        text_id = "tryphon_i_grammaticus.περὶ_τρόπων.tess"

        cache_path = lemma_cache.get_cache_path(text_id, "grc")

        assert cache_path.startswith(str(cache_dir))
        assert cache_path.endswith(".json")
        assert all(ord(ch) < 128 for ch in cache_path)
        assert "tryphon_i_grammaticus" in os.path.basename(cache_path)

    def test_unicode_normalization_variants_map_to_same_cache_path(self, isolated_cache_dirs):
        nfc_text_id = "tryphon_i_grammaticus.περὶ_τρόπων.tess"
        nfd_text_id = unicodedata.normalize("NFD", nfc_text_id)

        assert nfc_text_id != nfd_text_id
        assert lemma_cache.get_cache_path(nfc_text_id, "grc") == lemma_cache.get_cache_path(nfd_text_id, "grc")


class TestCachedUnitLoading:
    def test_save_and_load_cached_units_for_greek_text_id(self, isolated_cache_dirs):
        cache_dir, texts_dir = isolated_cache_dirs
        text_id = "tryphon_i_grammaticus.περὶ_τρόπων.tess"
        text_path = _write_text_file(texts_dir, "grc", text_id)
        file_hash = lemma_cache.get_file_hash(str(text_path))

        units_line = [{"ref": "1", "text": "alpha"}]
        units_phrase = [{"ref": "1", "text": "alpha beta"}]

        assert lemma_cache.save_cached_units(text_id, "grc", units_line, units_phrase, file_hash) is True

        cache_path = lemma_cache.get_cache_path(text_id, "grc")
        assert os.path.exists(cache_path)
        assert all(ord(ch) < 128 for ch in cache_path)

        cached = lemma_cache.get_cached_units(text_id, "grc")

        assert cached is not None
        assert cached["text_id"] == text_id
        assert cached["units_line"] == units_line
        assert cached["units_phrase"] == units_phrase
        assert cached["file_hash"] == file_hash
        assert not os.path.exists(lemma_cache._legacy_cache_path(text_id, "grc"))

    def test_ascii_text_id_can_still_load_legacy_cache_file(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        text_id = "vergil.aeneid.tess"
        text_path = _write_text_file(texts_dir, "la", text_id)
        file_hash = lemma_cache.get_file_hash(str(text_path))

        legacy_path = lemma_cache._legacy_cache_path(text_id, "la")
        os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "text_id": text_id,
                    "language": "la",
                    "file_hash": file_hash,
                    "units_line": [{"ref": "1", "text": "arma"}],
                    "units_phrase": [{"ref": "1", "text": "arma virumque"}],
                },
                f,
            )

        hashed_path = lemma_cache.get_cache_path(text_id, "la")
        assert hashed_path != legacy_path
        assert not os.path.exists(hashed_path)

        cached = lemma_cache.get_cached_units(text_id, "la")

        assert cached is not None
        assert cached["text_id"] == text_id
        assert cached["file_hash"] == file_hash
        assert cached["units_line"] == [{"ref": "1", "text": "arma"}]
