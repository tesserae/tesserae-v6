"""One work must not own a Theme Search page.

WHY THIS TEST EXISTS

"warrior arming scene" returned no Vergil and no Homer. The cause was not
relevance. Scores in this index are compressed to the point where rank barely
means anything -- the top window scored 0.8701 and rank 4546 scored 0.8174 -- so
what fills a page is repetition, not quality. Ferdowsi's and Nizami's Diwans are
each ONE work holding tens of thousands of windows, many described in nearly the
same words, and between them they held 13 of the top 20.

`find_by_text` therefore picks the works first, one window each, and only then
lets each chosen work show its other strong passages. This test pins both halves
of that: the cap is enforced, and the second pass is not skipped, because an
earlier version of it silently dropped works whose passages sat deep in the
global order and the page came back looking fine while the Aeneid was gone.

These tests run against the real index and skip without it.
"""
import pytest

from backend import passage_index as pi

pytestmark = pytest.mark.skipif(not pi.is_available(),
                                reason='passage index not present')


def _works(results):
    out = []
    for r in results:
        w = pi._norm_work(r.get('work'))
        if w not in out:
            out.append(w)
    return out


def test_no_work_exceeds_the_passage_cap():
    d = pi.find_by_text('warrior arming scene', limit=25)
    counts = {}
    for r in d['results']:
        w = pi._norm_work(r.get('work'))
        counts[w] = counts.get(w, 0) + 1
    assert counts, 'no results at all'
    worst = max(counts.values())
    assert worst <= pi.PASSAGES_PER_WORK, (
        f'one work contributed {worst} passages, cap is {pi.PASSAGES_PER_WORK}')


def test_every_chosen_work_survives_the_fill_pass():
    """The bug this catches: the fill pass ran in global score order with a flat
    budget, so works chosen in the first pass whose windows sat at raw rank 4000
    never got reached, and vanished from a page that still looked full."""
    limit = 25
    d = pi.find_by_text('warrior arming scene', limit=limit)
    works = _works(d['results'])
    assert len(works) == limit, (
        f'{len(works)} works on the page, expected {limit}; '
        'a work chosen in the first pass was dropped by the second')


def test_a_long_epic_still_shows_its_repeated_type_scenes():
    """A flat one-per-work cap would have solved the flooding by throwing away
    the Iliad's other arming scenes, which is the opposite of what a reader
    looking for a type-scene wants."""
    d = pi.find_by_text('warrior arming scene', limit=25)
    counts = {}
    for r in d['results']:
        w = pi._norm_work(r.get('work'))
        counts[w] = counts.get(w, 0) + 1
    assert counts.get('homer.iliad', 0) > 1, (
        'the Iliad shows only one arming scene; it has four canonical ones')


def test_the_same_query_gives_the_same_answer_twice():
    """A scholar who cites a result must be able to find it again.

    Two things had to be fixed for that to hold. Expansion ran at temperature
    0.3, and dropping it to 0 was NOT enough: identical calls still produced
    different sentences. Expansions are therefore written to a shared file and
    reused, which is also what makes the answer the same across the three
    Apache workers.
    """
    q = 'warrior arming scene'
    first = _works(pi.find_by_text(q, limit=25)['results'])
    second = _works(pi.find_by_text(q, limit=25)['results'])
    assert first == second, 'the same query returned a different page'


def test_an_expansion_is_reused_rather_than_regenerated(tmp_path, monkeypatch):
    """The in-memory cache alone would let each Apache worker answer a query
    differently, so the reuse has to survive losing that cache."""
    monkeypatch.setattr(pi, 'EXPAND_CACHE_PATH', str(tmp_path / 'exp.jsonl'))
    pi._expand_cache.clear()
    pi._expand_cache_mtime[0] = 0.0
    first = pi.expand_query('warrior arming scene')
    if not first:
        pytest.skip('expansion model unavailable')
    pi._expand_cache.clear()          # as if a different worker took the request
    pi._expand_cache_mtime[0] = 0.0
    assert pi.expand_query('warrior arming scene') == first
