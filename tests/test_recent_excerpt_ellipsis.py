from backend.scholarship_recent import _excerpt


def test_google_books_fragment_is_shown_whole():
    it = {'snippet': '... the author weighs the strengths and weaknesses of each.'}
    assert _excerpt(it, ['strengths', 'weaknesses', 'democracy']) == 'the author weighs the strengths and weaknesses of each.'


def test_tiny_match_gives_way_to_the_fragment():
    it = {'snippet': '… strength . Athenian democracy drew on the many for its'}
    assert _excerpt(it, ['strength']) == 'strength . Athenian democracy drew on the many for its'


def test_a_real_sentence_still_wins():
    it = {'abstract': 'Opening remark here. Democracy in Athens rested on the assembly and the courts. Closing remark.'}
    assert _excerpt(it, ['democracy']) == 'Democracy in Athens rested on the assembly and the courts.'
