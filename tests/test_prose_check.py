"""The prose checker has to catch what NC actually catches, and nothing else.

Every rule traces to a correction he made. The tests below quote the real
case where possible, so a later reader can tell a rule from a preference.

The false-positive tests matter as much as the others. A checker that cries
about ordinary prose gets switched off, and then it protects nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.review.prose_check import RULES, check  # noqa: E402


def keys(text):
    return {r.key for _n, _c, r, _s in check(text)}


class TestTheRulesNCActuallyGave:
    def test_the_filler_he_cut_from_the_nancy_draft(self):
        """His words: "Don't give me the AI, 'and it is worth explaining,
        because it shapes . . .' filler." """
        text = ('Data for Research does not look like a match on its own, and '
                'it is worth explaining why, because it shapes what I should '
                'ask for instead.')
        assert 'meta-framing' in keys(text)

    def test_em_dash(self):
        assert 'em-dash' in keys('The reader wants one thing — clarity.')

    def test_semicolon(self):
        assert 'semicolon' in keys('It loaded; then it failed.')

    def test_surface_as_a_verb(self):
        assert 'surface-verb' in keys('The search surfaces parallels.')
        assert 'surface-verb' in keys('This could surface a problem.')

    def test_the_noun_surface_is_allowed(self):
        """NC banned the verb and kept the noun."""
        assert 'surface-verb' not in keys(
            'Two surface tokens matched, in their surface form.')

    def test_dropped_subject(self):
        assert 'subjectless' in keys('Hope Plutarch Camp is going well.')
        assert 'subjectless' not in keys('I hope Plutarch Camp is going well.')

    def test_engineering_register(self):
        assert 'engineering-register' in keys('It has a tighter memory footprint.')
        assert 'engineering-register' not in keys('It uses less memory.')

    def test_hedges_that_narrow_nothing(self):
        assert 'hedge' in keys('To be clear, the index is stale.')
        assert 'hedge' not in keys('The index is stale.')


class TestItLeavesOrdinaryProseAlone:
    def test_a_plain_paragraph_is_clean(self):
        text = ('The Greek index holds 1,268 texts. Eleven of them were filed '
                'under a French form of the name, so the site listed '
                'Archimedes twice. They are now filed under one name.')
        assert check(text) == []

    def test_a_colon_introducing_a_list_is_fine(self):
        text = 'Three things changed: the index, the caches and the margins.'
        assert 'colon-joining-clauses' not in keys(text)

    def test_a_citation_semicolon_is_still_flagged_for_a_human(self):
        """Narrow exceptions are for a reader to apply, not for the checker to
        guess at. It reports and the writer decides."""
        assert 'semicolon' in keys('(Smith 2020; Jones 2021)')


class TestWhatItMustNotRead:
    def test_code_fences_are_skipped(self):
        text = 'Run this:\n\n```\nfoo; bar --baz\n```\n\nThen look.'
        assert 'semicolon' not in keys(text)
        assert 'em-dash' not in keys(text)

    def test_inline_code_is_skipped(self):
        assert 'semicolon' not in keys('Run `foo; bar` first.')

    def test_urls_are_skipped(self):
        assert 'em-dash' not in keys('See https://example.com/a--b for more.')

    def test_line_numbers_survive_the_skipping(self):
        """Blanking code must not shift the lines a report points at."""
        text = 'clean line\n`a; b`\nHope this helps.\n'
        hits = check(text)
        assert hits, 'the third line should be caught'
        assert hits[0][0] == 3


class TestTheRulesAreTraceable:
    def test_every_rule_says_where_it_came_from(self):
        for rule in RULES:
            assert rule.why and len(rule.why) > 30, (
                f'{rule.key} has no explanation; a rule without a source '
                f'cannot be told from a preference')

    def test_every_rule_has_a_key_and_a_message(self):
        assert len({r.key for r in RULES}) == len(RULES), 'keys must be unique'
        for rule in RULES:
            assert rule.message, f'{rule.key} has no message'
