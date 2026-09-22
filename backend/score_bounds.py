"""Whether a parallel's score may exceed 1.0, in one place.

`backend/scorer.py` divides a match's summed word rarity by a normaliser and
then, historically, ran the answer through `min(score, 1.0)`. Anything that
computed higher was flattened to exactly 1.0.

That ceiling threw away real ordering. Measured on 2026-09-22, Lucan book 1
against all twelve books of the Aeneid, lemma search, min_matches 2, run
against production: 317 of 1,923 results computed above 1.0 and landed on
the ceiling together, 16% of the list. Within a single search that is a
block of 19 to 35 results carrying an identical score and therefore shown in
arbitrary order. Twenty of the 47 commentator-attested parallels that the
search retrieved (`evaluation/benchmarks/lucan_vergil_lexical_benchmark.json`)
were inside that block. Letting the scores through ranks five of those
twenty first in their block and thirteen in the top half, and lifts attested
parallels in the top ten of a search from 5 to 13.

`backend/fusion.py` had already set `unbounded_scoring: True` on every
channel it scores, so the default search on the site was never capped and
returns scores up to about 1.43. Only a single-channel search, which is what
a reader gets after changing the match type away from fusion, was affected.
The ceiling was an inconsistency between two paths rather than a decision,
so the default is now True on both and a caller must ask for the ceiling.

The constant lives here rather than being written out at each site because
three modules read it -- the scorer, the feature extractor that applies the
boosts, and the cache that keys results on the settings -- and a default
that disagrees between them would let two runs with different behaviour
share one cache entry.

Recorded in docs/DECISIONS.md, 2026-09-22.
"""

# A score may exceed 1.0. Pass `unbounded_scoring: False` in a search's
# settings to restore the ceiling for one search.
UNBOUNDED_DEFAULT = True


def is_unbounded(settings):
    """True when this search's scores may exceed 1.0."""
    if not settings:
        return UNBOUNDED_DEFAULT
    return settings.get('unbounded_scoring', UNBOUNDED_DEFAULT)
