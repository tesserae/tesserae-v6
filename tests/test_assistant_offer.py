"""An offer that cannot be accepted is not an offer.

WHY THIS EXISTS

"Tessa offers the inflected forms, the reader says yes, and she prints the exact
list again" was reported three times and explained wrongly twice. The acceptance
logic in agent.py was correct the whole time. Two things around it were not, and
each defeated it on its own:

1. `blueprints/assistant.py` capped every history turn at `text[:600]`. The
   offer is appended to the END of an answer, and the answer that most needs the
   offer is a listing of a dozen quoted lines, which runs well past 600
   characters. So the offer never reached the server.

2. The server's own fallback wrote the offer to `session` from INSIDE the
   streaming generator. Flask sends the session cookie with the response
   headers, and a streamed body is produced after those have gone, so that
   assignment never reached the browser.

Every earlier test passed because a test sends the offer sentence by itself,
which is short and survives truncation. Only a browser sends the whole answer.
So these tests use a REALISTIC answer -- long, with the offer last.

They are pure functions over text: no model, no network, no corpus.
"""
from backend.assistant.agent import OFFER_MARK, _is_affirmative, _pending_offer_from
from backend.blueprints.assistant import TURN_HEAD, TURN_TAIL, _trim_turn


def _long_answer():
    """What Tessa actually sends: many quoted lines, then the offer."""
    body = '\n'.join(
        f'Vergil Aeneid {i}.{i * 7}: "arma virumque cano, Troiae qui primus ab '
        f'oris" with enough surrounding text to be realistic'
        for i in range(1, 13))
    offer = ('\n\n“arma virumque” also occurs in other inflected forms '
             '179 times, across 17 authors not listed above (Livy, William of '
             'Tyre, Silius Italicus and 14 more). Would you like those as well?')
    return body + offer


def test_the_realistic_answer_is_actually_long():
    """Guards the premise. If this stops being true the other tests prove nothing."""
    assert len(_long_answer()) > 600


def test_trimming_keeps_the_offer_at_the_end():
    trimmed = _trim_turn(_long_answer())
    assert OFFER_MARK in trimmed, 'the offer was trimmed away, so "yes" has nothing to accept'


def test_the_old_head_only_cap_would_have_lost_it():
    """The regression itself, stated so the fix cannot be quietly reverted."""
    assert OFFER_MARK not in _long_answer()[:600]


def test_trimming_still_bounds_what_reaches_a_prompt():
    trimmed = _trim_turn(_long_answer())
    assert len(trimmed) <= TURN_HEAD + TURN_TAIL + 16


def test_short_turns_are_left_alone():
    assert _trim_turn('  where does arma virumque appear?  ') == 'where does arma virumque appear?'


def test_yes_finds_the_pending_offer_in_a_trimmed_history():
    history = [
        {'role': 'user', 'text': 'where does arma virumque appear'},
        {'role': 'assistant', 'text': _trim_turn(_long_answer())},
    ]
    assert _is_affirmative('yes')
    assert _pending_offer_from(history) == 'arma virumque'


def test_yes_does_not_reach_back_past_a_later_turn():
    """An offer is only acceptable while it is the most recent thing said."""
    history = [
        {'role': 'assistant', 'text': _trim_turn(_long_answer())},
        {'role': 'user', 'text': 'what about Greek?'},
        {'role': 'assistant', 'text': 'The Greek corpus holds 113,531 windows.'},
    ]
    assert _pending_offer_from(history) is None
