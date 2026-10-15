"""The passage-index warm-up at worker start (TESSERAE_WARM_PASSAGES)."""
from backend import runtime


def test_off_by_default(monkeypatch):
    monkeypatch.delenv('TESSERAE_WARM_PASSAGES', raising=False)
    assert runtime.start_passage_warmup() is None


def test_on_starts_a_thread_that_calls_the_loader(monkeypatch):
    from backend import passage_index
    calls = []
    monkeypatch.setattr(passage_index, '_ensure_loaded', lambda: calls.append(1))
    monkeypatch.setenv('TESSERAE_WARM_PASSAGES', '1')
    t = runtime.start_passage_warmup()
    assert t is not None
    t.join(5)
    assert calls == [1]


def test_a_failing_load_is_logged_not_raised(monkeypatch):
    from backend import passage_index

    def boom():
        raise RuntimeError('no index')
    monkeypatch.setattr(passage_index, '_ensure_loaded', boom)
    assert runtime.warm_passage_index() is False
