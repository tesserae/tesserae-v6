"""A large pairwise fusion search runs in parts and never gives different results.

Splitting the source into blocks must leave every row, score and the order of
the rows unchanged, and one large comparison runs at a time in a process.
"""
import os
import random
from collections import Counter
import sys
import threading

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest  # noqa: E402

from backend import fusion  # noqa: E402
from backend.matcher import Matcher  # noqa: E402
from backend.scorer import Scorer  # noqa: E402

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
def offline_frequencies(monkeypatch):
    """Document frequencies from the lemma alone, no inverted index."""
    monkeypatch.setattr(fusion, '_get_corpus_doc_freqs',
                        lambda lemmas, language='la': {w: 3 + (len(w) % 5) for w in lemmas})
    monkeypatch.setattr(fusion, '_get_total_texts', lambda language='la': 1429)


def run(src, tgt, **kw):
    events = []
    for etype, data in fusion.iter_fusion_search(
            src, tgt, Matcher(), Scorer(), 'a.tess', 'b.tess', language='la',
            enabled_channels=CHANNELS, max_results=5000, **kw):
        events.append((etype, data))
    return events


def final_rows(events):
    complete = [d for t, d in events if t == 'complete']
    assert len(complete) == 1
    return [(r['source']['ref'], r['target']['ref'], r['fused_score'])
            for r in complete[0]['results']], complete[0]


def tied_in_fixed_order(monkeypatch):
    """Make the run without parts break score ties the way the parts path does.

    Rows of equal score reach the overlap removal in the order their pairs
    entered the pair table, which depends on the part. The parts path fixes
    that order (score, source ref, target ref); the path without parts keeps
    its own. To compare the two, the run without parts is given the same order.
    """
    real = fusion.merge_line_and_window

    def ordered(line_results, window_results):
        return fusion._by_score(real(fusion._by_score(line_results),
                                     fusion._by_score(window_results)))

    monkeypatch.setattr(fusion, 'merge_line_and_window', ordered)


def test_parts_and_no_parts_give_identical_results(monkeypatch):
    src = make_units('a', 53, 1)
    tgt = make_units('b', 40, 2)
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 10)

    # Each level on its own: the same rows with the same scores, whatever the order of ties.
    for mode in ('line', 'window'):
        w, _ = final_rows(run(src, tgt, in_parts=False, mode=mode))
        p, _ = final_rows(run(src, tgt, in_parts=True, mode=mode))
        assert len(w) > 100
        assert Counter(p) == Counter(w)

    tied_in_fixed_order(monkeypatch)
    whole_rows, whole = final_rows(run(src, tgt, in_parts=False))
    parts_events = run(src, tgt, in_parts=True)
    part_rows, parted = final_rows(parts_events)

    assert len(whole_rows) > 100
    assert part_rows == whole_rows
    assert parted['total_results'] == whole['total_results']

    marks = [d for t, d in parts_events if t == 'parts']
    assert [m['part'] for m in marks] == [1, 2, 3, 4, 5, 6]
    assert all(m['total_parts'] == 6 for m in marks)
    inter = [d for t, d in parts_events if t == 'intermediate']
    assert [d['part'] for d in inter] == [1, 2, 3, 4, 5, 6]
    # the preview after the last part is the final best
    assert inter[-1]['results'][0]['fused_score'] == part_rows[0][2]
    # no row is lost to a part boundary: the ranked scores equal the whole search's
    assert part_rows[0][2] == whole_rows[0][2]


def test_a_window_across_a_part_boundary_is_kept(monkeypatch):
    # Source lines 10 and 11 hold one phrase between them: the window over
    # that pair spans the edge of the first part.
    src = make_units('a', 20, 3, pool=400)
    tgt = make_units('b', 12, 4, pool=400)
    src[9]['lemmas'] = src[9]['tokens'] = src[9]['original_tokens'] = ['zeta', 'alpha', 'pad1', 'pad2']
    src[10]['lemmas'] = src[10]['tokens'] = src[10]['original_tokens'] = ['pad3', 'pad4', 'omega', 'kappa']
    for u in src[9:11]:
        u['text'] = ' '.join(u['tokens'])
    tgt[5]['lemmas'] = tgt[5]['tokens'] = tgt[5]['original_tokens'] = ['zeta', 'qq1', 'qq2', 'alpha']
    tgt[6]['lemmas'] = tgt[6]['tokens'] = tgt[6]['original_tokens'] = ['qq3', 'omega', 'kappa', 'qq4']
    for u in tgt[5:7]:
        u['text'] = ' '.join(u['tokens'])
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 10)

    tied_in_fixed_order(monkeypatch)
    whole_rows, _ = final_rows(run(src, tgt, in_parts=False))
    part_rows, _ = final_rows(run(src, tgt, in_parts=True))
    assert part_rows == whole_rows
    assert any(r[0].startswith('a. 1.10-') for r in part_rows)


def test_default_splits_only_above_the_threshold(monkeypatch):
    src = make_units('a', 25, 5)
    tgt = make_units('b', 20, 6)
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 10)
    monkeypatch.setattr(fusion, 'FUSION_PART_THRESHOLD', 10_000)
    assert not [t for t, _ in run(src, tgt) if t == 'parts']
    monkeypatch.setattr(fusion, 'FUSION_PART_THRESHOLD', 100)
    assert [d['part'] for t, d in run(src, tgt) if t == 'parts'] == [1, 2, 3]
    assert not [t for t, _ in run(src, tgt, in_parts=False) if t == 'parts']


def test_a_source_that_fits_one_part_is_not_split(monkeypatch):
    src = make_units('a', 8, 7)
    tgt = make_units('b', 8, 8)
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 10)
    assert not [t for t, _ in run(src, tgt, in_parts=True) if t == 'parts']


def test_context_confirmation_runs_once_over_the_merged_rows(monkeypatch):
    src = make_units('a', 30, 9)
    tgt = make_units('b', 20, 10)
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 10)
    seen = []
    real = fusion.apply_context_confirmation

    def spy(merged, **kw):
        seen.append(len(merged))
        return real(merged, **kw)

    monkeypatch.setattr(fusion, 'apply_context_confirmation', spy)
    run(src, tgt, in_parts=True)
    assert len(seen) == 2          # one over the line rows, one over the window rows
    assert min(seen) > 0


def test_second_large_comparison_queues_until_the_first_ends(monkeypatch):
    monkeypatch.setattr(fusion, 'HEARTBEAT_INTERVAL', 0.01)

    def fake_parts(*args, cancellation=None, **kwargs):
        yield ('parts', {'part': 1, 'total_parts': 1})
        yield ('complete', {'results': [], 'total_results': 0})

    monkeypatch.setattr(fusion, '_run_parts', fake_parts)

    first = fusion._iter_fusion_in_parts()
    assert next(first)[0] == 'parts'          # the first holds the slot

    second = fusion._iter_fusion_in_parts()
    assert next(second) == ('queued', {'position': 1, 'large': True})
    assert next(second)[0] == 'heartbeat'     # still waiting, keeping the line alive

    third = fusion._iter_fusion_in_parts()
    assert next(third) == ('queued', {'position': 2, 'large': True})

    assert [t for t, _ in first] == ['complete']   # the first finishes and releases
    assert [t for t, _ in second if t != 'heartbeat'] == ['parts', 'complete']
    assert [t for t, _ in third if t != 'heartbeat'] == ['parts', 'complete']
    assert fusion._LARGE_SEMAPHORE.acquire(blocking=False)   # nothing left holding it
    fusion._LARGE_SEMAPHORE.release()
    assert fusion._large_waiters == []


def test_a_waiting_request_that_is_cancelled_leaves_the_line(monkeypatch):
    monkeypatch.setattr(fusion, 'HEARTBEAT_INTERVAL', 0.01)

    def fake_parts(*args, cancellation=None, **kwargs):
        yield ('parts', {'part': 1, 'total_parts': 1})
        yield ('complete', {'results': [], 'total_results': 0})

    monkeypatch.setattr(fusion, '_run_parts', fake_parts)

    class Cancelled(Exception):
        pass

    class Token:
        def check(self):
            raise Cancelled()

    first = fusion._iter_fusion_in_parts()
    next(first)
    waiting = fusion._iter_fusion_in_parts(cancellation=Token())
    assert next(waiting)[0] == 'queued'
    with pytest.raises(Cancelled):
        next(waiting)
    assert fusion._large_waiters == []
    first.close()
    assert fusion._LARGE_SEMAPHORE.acquire(blocking=False)
    fusion._LARGE_SEMAPHORE.release()


def test_the_semaphore_is_one_per_process():
    assert isinstance(fusion._LARGE_SEMAPHORE, type(threading.Semaphore(1)))


def test_collector_threshold_is_set_during_a_comparison_and_restored(monkeypatch):
    import gc
    from backend import fusion
    seen = []

    def fake_run_parts(*a, **k):
        seen.append(gc.get_threshold())
        yield ("complete", {})

    monkeypatch.setattr(fusion, "_run_parts", fake_run_parts)
    before = gc.get_threshold()
    list(fusion._iter_fusion_in_parts())
    assert seen == [fusion._LARGE_GC_THRESHOLD]
    assert gc.get_threshold() == before
    gen = fusion._iter_fusion_in_parts()
    next(gen)
    gen.close()
    assert gc.get_threshold() == before
