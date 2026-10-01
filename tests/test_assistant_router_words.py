"""The router matches whole words: "across" is not "cross"."""
from backend.assistant import router


def test_across_does_not_reach_the_cross_language_answer():
    answer = router.route('How do I find rare words across the whole corpus and compare them?')
    assert not (answer and 'Cross-Language' in answer and 'different language' in answer.lower()) or answer is None


def test_cross_language_question_still_routes():
    answer = router.route('How do I search across Greek and Latin, a cross-language comparison?')
    assert answer and ('cross' in answer.lower() or 'language' in answer.lower())
