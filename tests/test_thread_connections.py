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


def test_concurrent_line_search_index_reads_do_not_fail(tmp_path):
    from backend import inverted_index
    db = tmp_path / 'xx_index.db'
    c = sqlite3.connect(db)
    c.execute('CREATE TABLE t (k INTEGER, v TEXT)')
    c.executemany('INSERT INTO t VALUES (?, ?)', [(i, 'x' * 50) for i in range(20000)])
    c.commit()
    c.close()
    errors = []

    def read():
        try:
            for _ in range(5):
                conn = inverted_index._connections.get('xx')
                if conn is None:
                    conn = sqlite3.connect(db, check_same_thread=False)
                    inverted_index._connections['xx'] = conn
                assert len(conn.execute('SELECT k, v FROM t').fetchall()) == 20000
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=read) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert errors == []
