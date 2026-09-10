"""Theme Search 'Show more' past the normal cap: offset pagination.

WHY THIS EXISTS

Theme Search's page length is set by `limit`, which the client could already
step from 25 up to 100 -- and 100 is where it stopped, because `_MAX_LIMIT` in
the blueprint caps `limit` itself. That is a real ceiling, not a display
choice: passages a scholar would want for a broad topos rank 300 to 3,000
(Alan of Lille Anticlaudianus 1.73, Nonnus Dionysiaca 3.147, Seneca Oedipus
525, Pliny Letters 5.6.5, all verified against the live query "a shaded
natural spot with trees, a meadow, and a spring or brook, often with birdsong
and a breeze"), and nothing below rank 100 could ever be reached.

`offset` on `backend.passage_index._rank` (and threaded through
`find_by_text` and the `/passages/theme-search` route) pages PAST that cap:
results (offset+1) to (offset+limit) of the identical ranking, not a fresh
ranking with a different cutoff. These tests use a small synthetic corpus
(monkeypatched onto `passage_index._records`) rather than the real 2GB index,
which is not present in CI or in a fresh worktree -- see is_available() guards
elsewhere in this directory for the integration-test alternative.

Split into three groups:
  * _rank itself, as a pure function over synthetic scores/records
  * the scripture-merge interaction, which is the one place offset has to do
    real bookkeeping rather than just "skip N rows"
  * the /passages/theme-search route, which must forward and clamp `offset`
    and otherwise leave the query untouched
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Before importing the app: backend/app.py raises without this outside dev.
os.environ.setdefault('SESSION_SECRET', 'test-only-not-a-secret')
os.environ.setdefault('TESSERAE_DIRECT_SERVER', '1')

from backend import passage_index as pi  # noqa: E402


def _rec(work, ref_start, ref_end, language='la', scale='fine', gist='x'):
    return {
        'id': f'{work}.{ref_start}',
        'language': language,
        'work': work,
        'scale': scale,
        'ref_start': ref_start,
        'ref_end': ref_end,
        'desc': {'gist': gist, 'themes': [], 'mode': None,
                 'names_in_text': None, 'names_unverified': []},
    }


def _synthetic_corpus(n_works=12, per_work=4):
    """`n_works` works of `per_work` passages each, strictly decreasing score
    in (work, passage) order: work0's passages score highest, work1's next,
    and so on. `_records` and the returned score array line up by row index,
    which is all `_rank` needs -- it never touches the embeddings directly.
    """
    records, scores = [], []
    score = 1000.0
    for w in range(n_works):
        for p in range(per_work):
            records.append(_rec(f'synth.work{w}', f'{p + 1}.1', f'{p + 1}.5'))
            scores.append(score)
            score -= 1.0
    return records, np.array(scores, dtype=np.float32)


@pytest.fixture
def synthetic(monkeypatch):
    records, scores = _synthetic_corpus()
    monkeypatch.setattr(pi, '_records', records)
    return records, scores


def _works(results):
    out = []
    for r in results:
        w = pi._norm_work(r.get('work'))
        if w not in out:
            out.append(w)
    return out


# --------------------------------------------------------------------------
# _rank: offset pages the same ranking rather than re-cutting it
# --------------------------------------------------------------------------

## All these calls pass an explicit `baseline` (rather than letting `_rank`
## take the median of a 48-row toy array) so the `floor = baseline +
## BASELINE_MARGIN` cutoff -- a real feature, unrelated to offset -- does not
## truncate the synthetic ranking and make failures here look like an offset
## bug when they are actually "the toy corpus's median was too close to its
## own top score." Real corpora are large enough that this never bites.

def test_offset_zero_matches_omitting_it(synthetic):
    _, scores = synthetic
    assert (pi._rank(scores, 5, per_work=1, baseline=0.0)
            == pi._rank(scores, 5, per_work=1, baseline=0.0, offset=0))


def test_offset_returns_the_next_slice_of_the_same_ranking(synthetic):
    _, scores = synthetic
    first = pi._rank(scores, 5, per_work=1, baseline=0.0)
    second = pi._rank(scores, 5, per_work=1, baseline=0.0, offset=5)
    assert _works(first) == [f'synth.work{i}' for i in range(5)]
    assert _works(second) == [f'synth.work{i}' for i in range(5, 10)]
    # The two pages must not overlap -- that is what "show more" promises.
    assert not set(_works(first)) & set(_works(second))


def test_paging_through_offset_reconstructs_one_long_page(synthetic):
    """Two offset-stepped calls must cover exactly what one bigger call would,
    in the same order, or repeated 'Show more' clicks would silently drop or
    reorder passages the reader has already seen."""
    _, scores = synthetic
    whole = pi._rank(scores, 20, per_work=1, baseline=0.0)
    part1 = pi._rank(scores, 10, per_work=1, baseline=0.0)
    part2 = pi._rank(scores, 10, per_work=1, baseline=0.0, offset=10)
    assert part1 + part2 == whole


def test_offset_past_the_end_returns_nothing(synthetic):
    """The signal the frontend uses to hide the 'Show more' button."""
    _, scores = synthetic
    assert pi._rank(scores, 5, per_work=1, baseline=0.0, offset=1000) == []


def test_offset_counts_the_same_unit_as_limit(synthetic):
    """With per_work=1, a work's other passages must not consume offset slots
    of their own: offset counts WORKS here, exactly what limit counts, so
    page 2 lines up with where page 1 (at the same limit) stopped."""
    _, scores = synthetic
    out = pi._rank(scores, 3, per_work=1, baseline=0.0, offset=3)
    assert _works(out) == ['synth.work3', 'synth.work4', 'synth.work5']


def test_offset_is_stable_across_repeated_calls(synthetic):
    """A scholar citing a result on page 2 must get the same page 2 again."""
    _, scores = synthetic
    a = pi._rank(scores, 5, per_work=1, baseline=0.0, offset=5)
    b = pi._rank(scores, 5, per_work=1, baseline=0.0, offset=5)
    assert a == b


# --------------------------------------------------------------------------
# Scripture merge vs. offset: the one place offset needs real bookkeeping
# --------------------------------------------------------------------------

def test_scripture_duplicate_still_merges_within_one_page(monkeypatch):
    """Baseline, unaffected by offset: the lower-scoring version of a
    scripture passage folds into the higher-scoring one as `also_in`."""
    records = [
        _rec('hebrew_bible.genesis', '1.1', '1.5', language='he'),
        _rec('vulgate.genesis', 'Genesis 1.1', 'Genesis 1.5', language='la'),
        _rec('synth.work0', '1.1', '1.5'),
    ]
    scores = np.array([10.0, 9.0, 8.0], dtype=np.float32)
    monkeypatch.setattr(pi, '_records', records)
    page = pi._rank(scores, 2, baseline=0.0)
    assert len(page) == 2
    assert page[0]['work'] == 'hebrew_bible.genesis'
    assert [d['work'] for d in page[0].get('also_in', [])] == ['vulgate.genesis']
    assert page[1]['work'] == 'synth.work0'


def test_scripture_duplicate_before_offset_does_not_leak_through(monkeypatch):
    """The bug this guards against: the Hebrew Genesis passage (rank slot 0)
    sits before `offset` and is skipped, as intended. Its Latin duplicate
    would normally merge INTO that entry -- but that entry was never added to
    this page, so the duplicate must be dropped too, not surfaced as a
    phantom new result with no `also_in` history behind it.
    """
    records = [
        _rec('hebrew_bible.genesis', '1.1', '1.5', language='he'),
        _rec('vulgate.genesis', 'Genesis 1.1', 'Genesis 1.5', language='la'),
        _rec('synth.work0', '1.1', '1.5'),
    ]
    scores = np.array([10.0, 9.0, 8.0], dtype=np.float32)
    monkeypatch.setattr(pi, '_records', records)
    page2 = pi._rank(scores, 2, baseline=0.0, offset=1)
    assert [r['work'] for r in page2] == ['synth.work0']


# --------------------------------------------------------------------------
# find_by_text: offset results are marked honestly, everything else the same
# --------------------------------------------------------------------------

def _spike_records_and_scores(n_spike=8, n_bg=60):
    """8 works with a real spike over a big flat background, so the
    confidence machinery (which needs a corpus-sized distribution to compute
    a meaningful median/head-lift) actually reports 'strong', the way a
    genuine subject does on the live index. `spike.work0` scores highest.
    """
    records = [_rec(f'spike.work{i}', '1.1', '1.5') for i in range(n_spike)]
    records += [_rec(f'bg.work{i}', '1.1', '1.5') for i in range(n_bg)]
    spike = [0.5 - 0.02 * i for i in range(n_spike)]
    bg = [-0.001 * i for i in range(n_bg)]
    return records, np.array(spike + bg, dtype=np.float32)


def _patch_index_for_find_by_text(monkeypatch, records, scores):
    """Enough of the loaded-index state for `find_by_text` to run without the
    real 2GB index or the embedding service: a fixed score array in place of
    the matrix multiply, and a fixed coherence in place of the top-k cosine
    computation (both operate on `_emb`, which stays a cheap zero array).
    """
    monkeypatch.setattr(pi, '_records', records)
    monkeypatch.setattr(pi, '_state', {'loaded': True, 'ok': True, 'error': None})
    monkeypatch.setattr(pi, '_undescribed', set())
    monkeypatch.setattr(pi, '_emb', np.zeros((len(records), 4), dtype=np.float32))
    monkeypatch.setattr(pi, '_score_all', lambda q: scores.copy())
    monkeypatch.setattr(pi, '_cluster_coherence', lambda s, k=pi.COHERENCE_K: 0.5)
    monkeypatch.setattr(pi, 'embed_query', lambda text: np.zeros(4, dtype=np.float32))


def test_find_by_text_forces_strong_false_beyond_the_offset(monkeypatch):
    """Reached only by paging past the default view: individual scores can
    still clear STRONG_LIFT this deep (rank is compressed, not
    confidence-ordered), so this has to be an explicit override, not a
    filter -- the confidence band was fitted to what page 1 shows.
    """
    records, scores = _spike_records_and_scores()
    _patch_index_for_find_by_text(monkeypatch, records, scores)
    q = 'a test query with more than six words in it'

    out = pi.find_by_text(q, limit=4, expand=False, offset=0)
    assert [r['work'] for r in out['results']] == [f'spike.work{i}' for i in range(4)]
    assert out['confidence']['level'] == 'strong', (
        'test corpus is not producing a strong verdict; the rest of this '
        'test proves nothing without one')
    # These are the query's best matches, well above STRONG_LIFT -- page 1
    # marks them strong on their merits, which is the contrast the override
    # on page 2 has to matter against.
    assert all(r['strong'] for r in out['results'])

    deep = pi.find_by_text(q, limit=4, expand=False, offset=4)
    assert [r['work'] for r in deep['results']] == [f'spike.work{i}' for i in range(4, 8)]
    # Same spike, same kind of score gap above baseline -- would read strong
    # on their own merits too. Forced False because they were reached only by
    # paging past what the confidence band vouches for.
    assert all(r['strong'] is False for r in deep['results'])


def test_find_by_text_offset_default_is_unchanged(monkeypatch):
    """Calling with offset=0 explicitly must be identical to omitting it."""
    records, scores = _spike_records_and_scores()
    _patch_index_for_find_by_text(monkeypatch, records, scores)
    q = 'a test query with more than six words in it'
    a = pi.find_by_text(q, limit=3, expand=False)
    b = pi.find_by_text(q, limit=3, expand=False, offset=0)
    assert a == b


# --------------------------------------------------------------------------
# The route: forwards offset, clamps it, and leaves everything else alone
# --------------------------------------------------------------------------

@pytest.fixture(scope='module')
def route():
    from backend.app import app
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/theme-search'))


@pytest.fixture
def client():
    from backend.app import app
    return app.test_client()


def _stub_find_by_text(calls):
    def fake(query, limit=25, languages=None, scale=None, expand=True, offset=0):
        calls.append({'query': query, 'limit': limit, 'offset': offset,
                      'languages': languages, 'scale': scale})
        return {'query': query, 'results': [], 'confidence': {'level': 'low'},
                'note': None}
    return fake


def test_route_forwards_offset_and_limit(monkeypatch, client, route):
    calls = []
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(calls))
    r = client.get(f'{route}?q=test&offset=150&limit=40')
    assert r.status_code == 200
    assert calls[-1]['offset'] == 150
    assert calls[-1]['limit'] == 40


def test_route_defaults_offset_to_zero(monkeypatch, client, route):
    calls = []
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(calls))
    client.get(f'{route}?q=test')
    assert calls[-1]['offset'] == 0


def test_route_clamps_offset_to_the_sane_maximum(monkeypatch, client, route):
    from backend.blueprints.passages import _MAX_OFFSET
    calls = []
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(calls))
    client.get(f'{route}?q=test&offset=999999999')
    assert calls[-1]['offset'] == _MAX_OFFSET


def test_route_clamps_negative_offset_to_zero(monkeypatch, client, route):
    calls = []
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(calls))
    client.get(f'{route}?q=test&offset=-5')
    assert calls[-1]['offset'] == 0


def test_route_ignores_a_non_numeric_offset(monkeypatch, client, route):
    """_int_arg falls back to the default on a bad value rather than 500ing."""
    calls = []
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(calls))
    r = client.get(f'{route}?q=test&offset=banana')
    assert r.status_code == 200
    assert calls[-1]['offset'] == 0
