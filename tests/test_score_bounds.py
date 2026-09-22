"""A parallel's score is not capped at 1.0, and one default governs it.

The ceiling flattened every score above 1.0 to exactly 1.0. On Lucan book 1
against all twelve books of the Aeneid that was 317 of 1,923 results, 16% of
the list, in blocks of 19 to 35 per search that carried an identical score
and were therefore shown in arbitrary order. Twenty of the 47
commentator-attested parallels the search retrieved were inside those
blocks.

The default has to agree across three modules. The scorer and the feature
extractor decide whether to clamp; `backend/cache.py` writes the same
setting into the key it stores results under. If those disagreed, two runs
that scored differently would share one cache entry, and the second reader
would be served the first reader's numbers.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import cache  # noqa: E402
from backend.score_bounds import UNBOUNDED_DEFAULT, is_unbounded  # noqa: E402


class TestTheDefault:
    def test_scores_are_uncapped_unless_asked_otherwise(self):
        assert UNBOUNDED_DEFAULT is True
        assert is_unbounded({}) is True
        assert is_unbounded(None) is True

    def test_a_caller_can_still_ask_for_the_ceiling(self):
        assert is_unbounded({'unbounded_scoring': False}) is False

    def test_an_explicit_true_is_honoured(self):
        assert is_unbounded({'unbounded_scoring': True}) is True


class TestTheThreeModulesAgree:
    def test_the_scorer_reads_the_shared_default(self):
        import backend.scorer as scorer
        src = open(scorer.__file__.replace('.pyc', '.py'), encoding='utf-8').read()
        assert 'is_unbounded(settings)' in src
        assert "settings.get('unbounded_scoring', False)" not in src

    def test_the_feature_extractor_reads_the_shared_default(self):
        import backend.feature_extractor as fe
        src = open(fe.__file__.replace('.pyc', '.py'), encoding='utf-8').read()
        assert 'is_unbounded(settings)' in src
        assert "settings.get('unbounded_scoring', False)" not in src

    def test_the_cache_key_carries_the_same_default(self):
        """Two searches that score differently must not share a cache key."""
        capped = cache.get_cache_key('a.tess', 'b.tess', 'la',
                                     {'unbounded_scoring': False})
        default = cache.get_cache_key('a.tess', 'b.tess', 'la', {})
        uncapped = cache.get_cache_key('a.tess', 'b.tess', 'la',
                                       {'unbounded_scoring': True})
        assert default == uncapped
        assert default != capped


class TestFusionIsUnchanged:
    def test_fusion_already_asked_for_this(self):
        """Every fusion channel set the flag itself, so the default search on
        the site was never capped. This change only brings the single-channel
        path into line with it."""
        import backend.fusion as fusion
        src = open(fusion.__file__.replace('.pyc', '.py'), encoding='utf-8').read()
        assert '"unbounded_scoring": True' in src
