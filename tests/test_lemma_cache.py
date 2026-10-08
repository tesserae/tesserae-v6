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

    def test_default_cache_dir_param_is_identical_to_the_pre_param_behaviour(self, isolated_cache_dirs):
        """get_cache_path gained an optional `cache_dir` param (2026-09-19,
        for backend/reuse_table.py, which needs the same hashed filename
        computed against its OWN lemma cache directory rather than this
        module's CACHE_DIR). Every other caller -- get_cached_units and
        save_cached_units in this module, plus every test above this one
        in this file -- calls it with only (text_id, language), and must
        keep resolving to exactly this module's CACHE_DIR, not None, not
        the caller's own working directory, and not a stale value captured
        before a test monkeypatches CACHE_DIR (the default is looked up by
        name inside the function body, not bound at def time)."""
        cache_dir, _ = isolated_cache_dirs
        text_id = "vergil.aeneid.tess"

        omitted = lemma_cache.get_cache_path(text_id, "la")
        explicit_default = lemma_cache.get_cache_path(text_id, "la", cache_dir=str(cache_dir))
        explicit_module_constant = lemma_cache.get_cache_path(text_id, "la", cache_dir=lemma_cache.CACHE_DIR)

        assert omitted == explicit_default == explicit_module_constant
        assert omitted.startswith(str(cache_dir))


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


class _StubTextProcessor:
    """Records every process_file call instead of really lemmatizing, so
    the tests below can assert exactly when (and only when) the slow path
    is reached, without needing CLTK models loaded."""

    def __init__(self):
        self.calls = []

    def process_file(self, filepath, language, unit_type):
        self.calls.append((os.path.basename(filepath), language, unit_type))
        ref = "1"
        return [{"ref": ref, "text": "stub", "tokens": ["stub"],
                 "original_tokens": ["stub"], "lemmas": ["stub_lemma"],
                 "pos_tags": ["N"], "variant_lemmas": [], "hemistich_breaks": []}]


class TestRebuildLemmaCacheNewParamsDefaultUnchanged:
    """`file_filter` and `fast_greek` were added to `rebuild_lemma_cache`
    for the documents build (stage 3b-1 follow-up). Every existing
    caller -- the live site's cache rebuild, `tests/test_batch_lemma_cache_*`,
    and this file's own tests above -- calls it with neither, and must
    keep going through `text_processor.process_file` for every file,
    unchanged."""

    def test_no_new_args_processes_every_file_via_text_processor(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "la", "a.tess")
        _write_text_file(texts_dir, "la", "b.tess")
        stub = _StubTextProcessor()

        result = lemma_cache.rebuild_lemma_cache("la", stub)

        assert result["success"] is True
        assert result["total"] == 2
        assert result["processed"] == 2
        # Both files went through the stub's process_file, for BOTH unit
        # types: the exact pre-existing behavior.
        assert sorted(stub.calls) == [
            ("a.tess", "la", "line"), ("a.tess", "la", "phrase"),
            ("b.tess", "la", "line"), ("b.tess", "la", "phrase"),
        ]

    def test_grc_with_no_fast_greek_arg_still_uses_text_processor(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "grc", "x.tess")
        stub = _StubTextProcessor()

        lemma_cache.rebuild_lemma_cache("grc", stub)

        assert stub.calls == [("x.tess", "grc", "line"), ("x.tess", "grc", "phrase")]

    def test_fast_greek_true_is_a_no_op_for_latin(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "la", "a.tess")
        stub = _StubTextProcessor()

        lemma_cache.rebuild_lemma_cache("la", stub, fast_greek=True)

        # fast_greek only ever applies when language == 'grc'; for 'la' it
        # must still go through the text_processor, exactly as before.
        assert stub.calls == [("a.tess", "la", "line"), ("a.tess", "la", "phrase")]


class TestRebuildLemmaCacheFileFilter:
    def test_file_filter_restricts_to_the_given_subset(self, isolated_cache_dirs):
        cache_dir, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "la", "a.tess")
        _write_text_file(texts_dir, "la", "b.tess")
        stub = _StubTextProcessor()

        result = lemma_cache.rebuild_lemma_cache("la", stub, file_filter=["a.tess"])

        assert result["total"] == 1
        assert [c[0] for c in stub.calls] == ["a.tess", "a.tess"]
        assert os.path.exists(os.path.join(str(cache_dir), "la"))
        cached_a = lemma_cache.get_cached_units("a.tess", "la")
        assert cached_a is not None
        cached_b = lemma_cache.get_cached_units("b.tess", "la")
        assert cached_b is None


class TestRebuildLemmaCacheFastGreek:
    def test_fast_greek_true_skips_text_processor_and_matches_table_lookup(self, isolated_cache_dirs):
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from scripts.build_inverted_index import (
            lemmatize_fast, load_lemma_table, tokenize_greek_fast)

        _, texts_dir = isolated_cache_dirs
        # A real Greek funerary-formula word, so the real lemma table has
        # an entry for it (not a synthetic token the table would miss).
        _write_text_file(texts_dir, "grc", "x.tess", content="<x.1>\tχαῖρε\n")
        stub = _StubTextProcessor()

        result = lemma_cache.rebuild_lemma_cache("grc", stub, fast_greek=True)

        assert result["success"] is True
        # The slow path was never reached.
        assert stub.calls == []

        cached = lemma_cache.get_cached_units("x.tess", "grc")
        assert cached is not None
        cache_lemmas = cached["units_line"][0]["lemmas"]

        table = load_lemma_table("grc")
        expected_tokens = tokenize_greek_fast("χαῖρε")
        expected_lemmas = lemmatize_fast(expected_tokens, table, "grc")

        assert cache_lemmas == expected_lemmas
        # pos_tags/variant_lemmas/hemistich_breaks are always empty for the
        # fast path, matching the index build's own fast mode.
        assert cached["units_line"][0]["pos_tags"] == []

    def test_fast_greek_phrase_units_group_by_sentence_end(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "grc", "y.tess",
                          content="<y.1>\tχαῖρε τέκνον.\n<y.2>\tἄλυπε.\n")
        stub = _StubTextProcessor()

        lemma_cache.rebuild_lemma_cache("grc", stub, fast_greek=True)

        cached = lemma_cache.get_cached_units("y.tess", "grc")
        phrase_units = cached["units_phrase"]
        # Two sentences (each line ends in a period), so two phrase units,
        # each carrying its own line_refs.
        assert [u["ref"] for u in phrase_units] == ["y.1", "y.2"]
        assert phrase_units[0]["line_refs"] == ["y.1"]


class TestRebuildLemmaCacheBuildPhraseUnitsDefaultUnchanged:
    """build_phrase_units was added to rebuild_lemma_cache (stage 3b-1
    follow-up), after measuring a real memory risk in process_file's own
    phrase-accumulation logic against the documents corpus's largest
    bucket file (see the function's own docstring). Every existing
    caller never passes it and must keep building phrase units exactly
    as before."""

    def test_no_arg_still_builds_phrase_units(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "la", "a.tess")
        stub = _StubTextProcessor()

        lemma_cache.rebuild_lemma_cache("la", stub)

        assert ("a.tess", "la", "phrase") in stub.calls
        cached = lemma_cache.get_cached_units("a.tess", "la")
        assert cached["units_phrase"] != []

    def test_build_phrase_units_false_skips_phrase_entirely(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "la", "a.tess")
        stub = _StubTextProcessor()

        result = lemma_cache.rebuild_lemma_cache("la", stub, build_phrase_units=False)

        assert result["success"] is True
        assert ("a.tess", "la", "phrase") not in stub.calls
        assert ("a.tess", "la", "line") in stub.calls
        cached = lemma_cache.get_cached_units("a.tess", "la")
        assert cached["units_phrase"] == []
        assert cached["units_line"] != []

    def test_build_phrase_units_false_with_fast_greek(self, isolated_cache_dirs):
        _, texts_dir = isolated_cache_dirs
        _write_text_file(texts_dir, "grc", "x.tess", content="<x.1>\tχαῖρε\n")
        stub = _StubTextProcessor()

        lemma_cache.rebuild_lemma_cache("grc", stub, fast_greek=True, build_phrase_units=False)

        assert stub.calls == []
        cached = lemma_cache.get_cached_units("x.tess", "grc")
        assert cached["units_phrase"] == []
        assert cached["units_line"] != []
