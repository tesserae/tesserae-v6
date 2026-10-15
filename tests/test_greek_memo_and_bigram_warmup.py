"""The memoized Greek normalizers and the single-read bigram loader."""
import json
import threading
import time

import pytest

from backend import bigram_frequency as bf
from backend import matcher


WORDS = ["ἄνδρα", "μοι", "ἔννεπε", "Μοῦσα", "πολύτροπον", "ὃς", "μάλα", "πολλὰ", "ΠΛΑΓΧΘΗ", "ς", "", "arma"]


def test_normalize_greek_memoized_matches_uncached():
    for w in WORDS:
        assert matcher.normalize_greek(w) == matcher.normalize_greek.__wrapped__(w)
        assert isinstance(matcher.normalize_greek(w), str)
    assert matcher.normalize_greek.cache_info().maxsize == 200_000
    assert matcher.normalize_greek("Μοῦσα") == "μουσα"


def test_transliterate_memoized_matches_uncached():
    for w in WORDS:
        assert (matcher.transliterate_greek_to_latin(w)
                == matcher.transliterate_greek_to_latin.__wrapped__(w))
    assert matcher.transliterate_greek_to_latin("Μοῦσα") == "mousa"


def test_normalize_greek_cache_is_bounded():
    assert matcher.normalize_greek.cache_info().maxsize is not None
    assert matcher.transliterate_greek_to_latin.cache_info().maxsize is not None


@pytest.fixture
def table(tmp_path, monkeypatch):
    monkeypatch.setattr(bf, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(bf, "_bigram_cache", {})
    monkeypatch.setattr(bf, "_loaded", {})
    data = {"language": "zz", "frequencies": {"a|b": 2}, "total_bigrams": 2,
            "doc_frequencies": {"a|b": 1}, "total_docs": 5}
    path = tmp_path / "zz_bigrams.json"
    path.write_text(json.dumps(data))
    return path, data


def test_concurrent_loads_parse_the_file_once(table, monkeypatch):
    path, data = table
    calls = []
    real = json.load

    def slow_load(f):
        calls.append(1)
        time.sleep(0.3)
        return real(f)

    monkeypatch.setattr(bf.json, "load", slow_load)
    out = []
    threads = [threading.Thread(target=lambda: out.append(bf.load_bigram_cache("zz"))) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert all(o == data for o in out)
    assert all(o is out[0] for o in out)


def test_changed_file_is_read_again(table):
    path, data = table
    first = bf.load_bigram_cache("zz")
    assert first == data
    assert bf.load_bigram_cache("zz") is first
    data2 = dict(data, total_docs=9)
    path.write_text(json.dumps(data2) + " ")
    again = bf.load_bigram_cache("zz")
    assert again["total_docs"] == 9


def test_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(bf, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(bf, "_bigram_cache", {})
    monkeypatch.setattr(bf, "_loaded", {})
    assert bf.load_bigram_cache("zz") is None


def test_warm_up_loads_named_languages_only(table, monkeypatch):
    from backend import runtime
    assert runtime.warm_bigram_tables(["zz", "qq", ""]) == ["zz"]
    assert "zz" in bf._bigram_cache


def test_warm_up_thread_is_off_by_default(monkeypatch):
    from backend import runtime
    monkeypatch.delenv("TESSERAE_WARM_BIGRAMS", raising=False)
    assert runtime.start_bigram_warmup() is None
    monkeypatch.setenv("TESSERAE_WARM_BIGRAMS", "qq")
    t = runtime.start_bigram_warmup()
    assert t is not None
    t.join(5)
