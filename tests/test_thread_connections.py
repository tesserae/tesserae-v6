"""Each thread gets its own sqlite3 connection: one connection shared by Apache's threads failed under load."""
import sqlite3
import threading

from backend.thread_connections import PerThreadConnections


def test_threads_do_not_share_a_connection():
    cache = PerThreadConnections()
    cache['la'] = sqlite3.connect(':memory:', check_same_thread=False)
    seen = {}

    def other():
        seen['has'] = 'la' in cache
        cache['la'] = sqlite3.connect(':memory:', check_same_thread=False)
        seen['conn'] = cache['la']

    t = threading.Thread(target=other)
    t.start()
    t.join()
    assert seen['has'] is False
    assert seen['conn'] is not cache['la']


def test_clear_reaches_every_thread_and_pop_only_this_one():
    cache = PerThreadConnections()
    cache['la'] = 1
    cache['grc'] = 2
    assert cache.pop('grc') == 2 and 'grc' not in cache and cache.get('la') == 1
    out = {}
    ready, go = threading.Event(), threading.Event()

    def other():
        cache['la'] = 3
        ready.set()
        go.wait()
        out['after_clear'] = 'la' in cache

    t = threading.Thread(target=other)
    t.start()
    ready.wait()
    cache.clear()
    go.set()
    t.join()
    assert 'la' not in cache and out['after_clear'] is False


def test_line_search_index_gives_each_thread_its_own_connection(tmp_path, monkeypatch):
    """Fails with the old shared dict, where every thread got the same connection object."""
    from backend import inverted_index
    sqlite3.connect(tmp_path / 'xx_index.db').close()
    monkeypatch.setattr(inverted_index, 'INDEX_DIR', str(tmp_path))
    monkeypatch.setattr(inverted_index, '_connections', PerThreadConnections())
    here = inverted_index.get_connection('xx')
    seen = {}
    t = threading.Thread(target=lambda: seen.setdefault('other', inverted_index.get_connection('xx')))
    t.start()
    t.join()
    assert here is not None and seen['other'] is not None
    assert here is not seen['other']
    assert inverted_index.get_connection('xx') is here
