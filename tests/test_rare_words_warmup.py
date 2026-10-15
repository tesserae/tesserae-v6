"""The rare-words warm-up at worker start (TESSERAE_WARM_RAREWORDS)."""
from backend import runtime
from backend.blueprints import hapax


def test_off_by_default(monkeypatch):
    monkeypatch.delenv('TESSERAE_WARM_RAREWORDS', raising=False)
    assert runtime.start_rare_words_warmup() is None


def test_on_starts_a_thread_that_warms_each_language(monkeypatch):
    calls = []
    monkeypatch.setattr(hapax, 'warm_rare_word_caches', lambda lang: calls.append(lang) or 1)
    monkeypatch.setenv('TESSERAE_WARM_RAREWORDS', 'la, grc')
    t = runtime.start_rare_words_warmup()
    assert t is not None
    t.join(5)
    assert calls == ['la', 'grc']


def test_a_failing_fill_is_logged_not_raised(monkeypatch):
    def boom(lang):
        raise RuntimeError('no index')
    monkeypatch.setattr(hapax, 'warm_rare_word_caches', boom)
    assert runtime.warm_rare_words(['la']) == []


def test_the_fill_runs_the_search_on_each_sample_pair(monkeypatch):
    seen = []
    monkeypatch.setattr(hapax, '_texts_dir', 'x')
    monkeypatch.setattr(hapax, '_text_processor', object())
    monkeypatch.setattr(hapax, '_compute_rare_words',
                        lambda *a: seen.append(a[:3]))
    assert hapax.warm_rare_word_caches('grc') == len(hapax.WARM_SAMPLE_PAIRS['grc'])
    assert seen[0] == (*hapax.WARM_SAMPLE_PAIRS['grc'][0], 'grc')
    assert hapax.warm_rare_word_caches('fa') == 0


def test_a_missing_work_is_skipped(monkeypatch):
    monkeypatch.setattr(hapax, '_texts_dir', 'x')
    monkeypatch.setattr(hapax, '_text_processor', object())

    def missing(*a):
        raise hapax.SearchInputError('Could not process source text')
    monkeypatch.setattr(hapax, '_compute_rare_words', missing)
    assert hapax.warm_rare_word_caches('la') == 0
