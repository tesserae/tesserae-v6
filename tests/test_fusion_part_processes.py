"""The parts of a large comparison run in worker processes and give the same answer.

Covers the two-process path against the single-process path, cancellation (no
process left behind), a worker that dies or fails, and the semantic floor of
Persian, Urdu and Arabic, which is set once from the whole pair so that a
comparison run in parts scores each pair as a run in one piece does.
"""
import os
import random
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from backend import fusion  # noqa: E402
from backend import semantic_similarity as ss  # noqa: E402
from backend.matcher import Matcher  # noqa: E402
from backend.scorer import Scorer  # noqa: E402
from backend.search_cancellation import SearchCancelled  # noqa: E402

CHANNELS = ['lemma', 'lemma_min1', 'exact']


def make_units(prefix, n, seed, pool=60):
    rng = random.Random(seed)
    vocab = [f'w{i}' for i in range(pool)]
    units = []
    for i in range(1, n + 1):
        words = [rng.choice(vocab) for _ in range(rng.randint(4, 7))]
        units.append({
            'ref': f'{prefix}. 1.{i}',
            'text': ' '.join(words),
            'tokens': list(words),
            'original_tokens': list(words),
            'lemmas': list(words),
            'pos_tags': [],
        })
    return units


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(fusion, '_get_corpus_doc_freqs',
                        lambda lemmas, language='la': {w: 3 + (len(w) % 5) for w in lemmas})
    monkeypatch.setattr(fusion, '_get_total_texts', lambda language='la': 1429)
    # The test machine may be short of memory; the memory rule has its own test.
    monkeypatch.setattr('backend.memory_util.get_available_memory_gb', lambda: 1000.0)
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 10)


def run(src, tgt, language='la', channels=CHANNELS, cancellation=None, **kw):
    return list(fusion.iter_fusion_search(
        src, tgt, Matcher(), Scorer(), 'a.tess', 'b.tess', language=language,
        enabled_channels=channels, max_results=5000, in_parts=True,
        cancellation=cancellation, **kw))


def complete(events):
    done = [d for t, d in events if t == 'complete']
    assert len(done) == 1
    return done[0]


def test_two_processes_give_the_single_process_answer(monkeypatch):
    src = make_units('a', 53, 1)
    tgt = make_units('b', 40, 2)
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '1')
    one = run(src, tgt)
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    two = run(src, tgt)
    a, b = complete(one), complete(two)
    assert len(a['results']) > 100
    assert a['results'] == b['results']
    assert a['total_results'] == b['total_results']
    # the events a visitor's page follows arrive in part order, once each
    for events in (one, two):
        assert [d['part'] for t, d in events if t == 'parts'] == [1, 2, 3, 4, 5, 6]
        assert [d['part'] for t, d in events if t == 'intermediate'] == [1, 2, 3, 4, 5, 6]
    previews_one = [d['results'] for t, d in one if t == 'intermediate']
    previews_two = [d['results'] for t, d in two if t == 'intermediate']
    assert previews_one == previews_two


def test_three_processes_also_match(monkeypatch):
    src = make_units('a', 53, 5)
    tgt = make_units('b', 30, 6)
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '1')
    one = complete(run(src, tgt))
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '3')
    three = complete(run(src, tgt))
    assert one['results'] == three['results']


def test_low_memory_runs_in_one_process(monkeypatch):
    monkeypatch.setattr('backend.memory_util.get_available_memory_gb', lambda: 3.0)
    assert fusion._part_process_count(6) == 1
    monkeypatch.setattr('backend.memory_util.get_available_memory_gb', lambda: 40.0)
    assert fusion._part_process_count(6) == 2
    assert fusion._part_process_count(1) == 1


class FlagCancellation:
    def __init__(self):
        self.flag = False

    def check(self):
        if self.flag:
            raise SearchCancelled()


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f'/proc/{pid}/stat') as f:
            return f.read().split(')')[-1].split()[0] != 'Z'
    except OSError:
        return False


def test_cancellation_stops_workers_within_a_beat_and_leaves_none(monkeypatch):
    import multiprocessing
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    real = fusion._fusion_block
    parent = os.getpid()

    def slow_block(*a, **k):
        if os.getpid() != parent:
            time.sleep(120)
        yield from real(*a, **k)

    monkeypatch.setattr(fusion, '_fusion_block', slow_block)
    cancel = FlagCancellation()
    gen = fusion.iter_fusion_search(
        make_units('a', 53, 1), make_units('b', 40, 2), Matcher(), Scorer(), 'a.tess', 'b.tess',
        language='la', enabled_channels=CHANNELS, max_results=5000, in_parts=True, cancellation=cancel)
    pids = []
    t_cancel = None
    with pytest.raises(SearchCancelled):
        for etype, _data in gen:
            if not pids:
                pids = [p.pid for p in multiprocessing.active_children()]
                assert len(pids) == 2
                cancel.flag = True
                t_cancel = time.monotonic()
    assert time.monotonic() - t_cancel < 3.0
    time.sleep(0.5)
    assert not any(alive(p) for p in pids)
    assert multiprocessing.active_children() == []


def test_closing_the_generator_stops_workers(monkeypatch):
    import multiprocessing
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    real = fusion._fusion_block
    parent = os.getpid()

    def slow_block(*a, **k):
        if os.getpid() != parent:
            time.sleep(120)
        yield from real(*a, **k)

    monkeypatch.setattr(fusion, '_fusion_block', slow_block)
    gen = fusion.iter_fusion_search(
        make_units('a', 53, 1), make_units('b', 40, 2), Matcher(), Scorer(), 'a.tess', 'b.tess',
        language='la', enabled_channels=CHANNELS, max_results=5000, in_parts=True)
    next(gen)
    pids = [p.pid for p in multiprocessing.active_children()]
    gen.close()
    time.sleep(0.5)
    assert pids and not any(alive(p) for p in pids)


def test_a_worker_that_dies_fails_the_comparison(monkeypatch):
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    real = fusion._fusion_block
    parent = os.getpid()

    def dying_block(*a, **k):
        if os.getpid() != parent:
            os._exit(9)
        yield from real(*a, **k)

    monkeypatch.setattr(fusion, '_fusion_block', dying_block)
    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match='stopped unexpectedly'):
        run(make_units('a', 53, 1), make_units('b', 40, 2))
    assert time.monotonic() - t0 < 10


def test_a_worker_that_raises_fails_the_comparison(monkeypatch):
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    real = fusion._fusion_block
    parent = os.getpid()

    def failing_block(*a, **k):
        if os.getpid() != parent:
            raise ValueError('bad part')
        yield from real(*a, **k)

    monkeypatch.setattr(fusion, '_fusion_block', failing_block)
    with pytest.raises(RuntimeError, match='failed'):
        run(make_units('a', 53, 1), make_units('b', 40, 2))


def test_a_killed_worker_with_a_held_pipe_is_still_noticed(monkeypatch):
    """A worker killed from outside while its pool children keep the pipe open."""
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    import signal
    real = fusion._fusion_block
    parent = os.getpid()

    def killed_block(*a, **k):
        if os.getpid() != parent:
            os.kill(os.getpid(), signal.SIGKILL)
        yield from real(*a, **k)

    monkeypatch.setattr(fusion, '_fusion_block', killed_block)
    with pytest.raises(RuntimeError, match='stopped unexpectedly'):
        run(make_units('a', 53, 1), make_units('b', 40, 2))


# --- the semantic floor, set once for the whole pair -------------------------

N_SRC, N_TGT, DIM = 250, 120, 64


@pytest.fixture
def persian(monkeypatch):
    """A synthetic Persian pair whose stored embeddings sit in a narrow band, as e5 vectors do."""
    rng = np.random.default_rng(7)
    base = np.ones(DIM, dtype=np.float32)
    src_emb = base + rng.normal(0, 0.15, (N_SRC, DIM)).astype(np.float32)
    tgt_emb = base + rng.normal(0, 0.15, (N_TGT, DIM)).astype(np.float32)
    # a few sources that stand out, so parts differ in their own percentile
    src_emb[:40] += rng.normal(0, 0.5, (40, DIM)).astype(np.float32)

    def row(unit):
        return int(unit['ref'].split('.')[-1]) - 1

    def fake_pair(source_units, target_units, settings, language):
        s = src_emb[[row(u) for u in source_units]]
        t = tgt_emb[[row(u) for u in target_units]]
        return s, t, True

    monkeypatch.setattr(ss, '_precomputed_pair', fake_pair)
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 100)
    return make_units('a', N_SRC, 11), make_units('b', N_TGT, 12)


def semantic_rows(events):
    return [(r['source']['ref'], r['target']['ref'], r['fused_score'])
            for r in complete(events)['results']]


def run_fa(src, tgt, in_parts):
    return list(fusion.iter_fusion_search(
        src, tgt, Matcher(), Scorer(), 'a.tess', 'b.tess', language='fa',
        enabled_channels=['semantic'], max_results=5000, in_parts=in_parts,
        source_path='a.tess', target_path='b.tess'))


def test_floor_is_the_same_whole_and_in_parts(persian, monkeypatch):
    src, tgt = persian
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '1')
    whole = semantic_rows(run_fa(src, tgt, False))
    parts = semantic_rows(run_fa(src, tgt, True))
    assert len(whole) > 10
    assert sorted(parts) == sorted(whole)


def test_floor_is_the_same_in_two_processes(persian, monkeypatch):
    src, tgt = persian
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '1')
    one = semantic_rows(run_fa(src, tgt, True))
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    two = semantic_rows(run_fa(src, tgt, True))
    assert one == two


def test_without_the_shared_floor_the_parts_differ(persian, monkeypatch):
    """The control: the test above is only meaningful if per-part floors would have differed."""
    src, tgt = persian
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '1')
    whole = semantic_rows(run_fa(src, tgt, False))
    monkeypatch.setattr(ss, 'pair_e5_floor', lambda *a, **k: None)
    parts = semantic_rows(run_fa(src, tgt, True))
    assert sorted(parts) != sorted(whole)


def test_other_languages_get_no_floor():
    units = make_units('a', 5, 1)
    assert ss.pair_e5_floor(units, units, {'language': 'la'}) is None
    assert ss.pair_e5_floor(units, units, {'language': 'grc'}) is None


# --- forking from a busy server process -------------------------------------

def test_a_forked_child_starts_without_its_parents_connections():
    import multiprocessing
    from backend.thread_connections import PerThreadConnections
    cache = PerThreadConnections()
    cache['k'] = object()
    assert 'k' in cache

    def child(q):
        q.put('k' in cache)

    ctx = multiprocessing.get_context('fork')
    q = ctx.Queue()
    p = ctx.Process(target=child, args=(q,))
    p.start()
    seen = q.get(timeout=10)
    p.join(10)
    assert seen is False
    assert 'k' in cache          # the parent keeps its own


def test_comparisons_complete_while_other_threads_log_read_and_multiply(monkeypatch, tmp_path):
    """Workers are forked from a process whose other threads are busy, as a web worker's are."""
    import logging
    import sqlite3
    import threading
    from backend.thread_connections import PerThreadConnections
    monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
    db = str(tmp_path / 'x.sqlite')
    c = sqlite3.connect(db)
    c.execute('create table t (a integer)')
    c.executemany('insert into t values (?)', [(i,) for i in range(1000)])
    c.commit()
    c.close()
    conns = PerThreadConnections()
    stop = threading.Event()
    log = logging.getLogger('busy')

    def busy():
        # The semantic channel's own matrix product, which holds the fork gate (backend/fork_gate.py).
        a = np.random.default_rng(0).random((600, 256)).astype(np.float32)
        b = np.random.default_rng(1).random((600, 256)).astype(np.float32)
        while not stop.is_set():
            if 'c' not in conns:
                conns['c'] = sqlite3.connect(db, check_same_thread=False)
            conns['c'].execute('select sum(a) from t').fetchone()
            log.info('busy %s', threading.get_ident())
            ss.sampled_percentile(a, b, 99.9)
            time.sleep(0.005)

    threads = [threading.Thread(target=busy, daemon=True) for _ in range(5)]
    for t in threads:
        t.start()
    try:
        src = make_units('a', 53, 1)
        tgt = make_units('b', 40, 2)
        monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '1')
        base = complete(run(src, tgt))['results']
        monkeypatch.setenv('TESSERAE_FUSION_PART_PROCESSES', '2')
        t0 = time.monotonic()
        for _ in range(5):
            assert complete(run(src, tgt))['results'] == base
        assert time.monotonic() - t0 < 120
    finally:
        stop.set()
        for t in threads:
            t.join(5)


def test_fork_gate_waits_for_products_and_holds_new_ones_back():
    import threading
    from backend import fork_gate
    order = []
    inside = threading.Event()
    release = threading.Event()

    def product():
        with fork_gate.shared():
            inside.set()
            release.wait(5)
            order.append('product done')

    t = threading.Thread(target=product)
    t.start()
    assert inside.wait(5)

    def fork():
        with fork_gate.exclusive():
            order.append('fork')

    f = threading.Thread(target=fork)
    f.start()
    time.sleep(0.2)
    assert order == []                      # the fork waits for the product

    def late():
        with fork_gate.shared():
            order.append('late product')

    late_t = threading.Thread(target=late)
    late_t.start()
    time.sleep(0.2)
    assert order == []                      # and a product that starts now waits for the fork
    release.set()
    for th in (t, f, late_t):
        th.join(5)
    assert order == ['product done', 'fork', 'late product']


def test_fork_gate_is_open_in_a_forked_child():
    import multiprocessing
    from backend import fork_gate
    ctx = multiprocessing.get_context('fork')
    q = ctx.Queue()

    def child():
        with fork_gate.shared():
            q.put('ran')

    with fork_gate.shared():              # held by the parent at the moment of the fork
        p = ctx.Process(target=child)
        p.start()
    assert q.get(timeout=10) == 'ran'
    p.join(10)
