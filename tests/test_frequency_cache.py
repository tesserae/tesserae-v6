import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend import frequency_cache


def test_get_corpus_checksum_uses_safe_filenames(tmp_path, monkeypatch):
    texts_dir = tmp_path / "texts"
    lang_dir = texts_dir / "grc"
    lang_dir.mkdir(parents=True, exist_ok=True)
    filename = "aelius_herodianus.περι_καθολικης_προσῳδιας.tess"
    text_path = lang_dir / filename
    text_path.write_text("test line\n", encoding="utf-8")

    monkeypatch.setattr(frequency_cache, "TEXTS_DIR", str(texts_dir))
    monkeypatch.setattr(frequency_cache, "safe_listdir", lambda path: [filename])

    checksum = frequency_cache.get_corpus_checksum("grc")

    assert isinstance(checksum, str)
    assert len(checksum) == 32


def test_save_frequency_cache_counts_texts_with_safe_listdir(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    texts_dir = tmp_path / "texts"
    lang_dir = texts_dir / "grc"
    lang_dir.mkdir(parents=True, exist_ok=True)
    (lang_dir / "ascii_text.tess").write_text("alpha\n", encoding="utf-8")
    (lang_dir / "aelius_herodianus.περι_καθολικης_προσῳδιας.tess").write_text("beta\n", encoding="utf-8")

    monkeypatch.setattr(frequency_cache, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(frequency_cache, "TEXTS_DIR", str(texts_dir))
    os.makedirs(cache_dir, exist_ok=True)

    data = frequency_cache.save_frequency_cache("grc", {"lemma": 2}, 2, "checksum")

    assert data["text_count"] == 2
