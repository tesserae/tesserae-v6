"""Issue #580, part A: breathing and accent marks stored before the Greek
letter they belong to (` ̔Ηροδότου` where the text should read
`Ἡροδότου`). scripts/corpus/fix_greek_capital_marks.py moves the marks onto
the letter and applies NFC. Restricted to vowels and rho (3 October 2026):
a breathing or accent only ever belongs on a vowel, or a rough breathing on
rho, so a mark before any other consonant -- capital or lowercase -- is
left alone, as a stray case for a human to check (Achilles Tatius 2.11.3,
` ̓μέθυστος`, a damaged ἀμέθυστος missing its alpha, is the case that
found this; the script had moved the breathing onto the following mu,
producing the nonsense `μ̓έθυστος`).

These tests exercise the line-level fix logic directly (process_line), not
the file-rewriting CLI.
"""
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.corpus.fix_greek_capital_marks import process_line, invariant_key  # noqa: E402


def nfc(s):
    return unicodedata.normalize('NFC', s)


def test_single_breathing_before_capital():
    # ` ̔Ηροδότου` (space, U+0314, Η...) -> ` Ἡροδότου`
    raw = '<hdt. 1.1.0>\t ' + '̔' + 'Ηροδότου\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert new == '<hdt. 1.1.0>\t ' + nfc('Η' + '̔') + 'ροδότου\n'
    assert 'Ἡροδότου' in new


def test_double_mark_breathing_plus_acute():
    # ̔́Ομηρος -> Ὅμηρος (breathing U+0314 + acute U+0301 before Omicron)
    raw = 'x\t ' + '̔́' + 'Ομηρος\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert 'Ὅμηρος' in new


def test_double_mark_breathing_plus_grave():
    # ̓̀Αν -> Ἂν (smooth breathing U+0313 + grave U+0300 before Alpha)
    raw = 'x\t ' + '̓̀' + 'Αν\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert 'Ἂν' in new


def test_smooth_breathing_before_capital():
    # ̓Αθήναιος -> Ἀθήναιος
    raw = 'x\t ' + '̓' + 'Αθήναιος\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert 'Ἀθήναιος' in new


def test_capital_with_iota_subscript():
    # breathing + iota subscript before capital Alpha -> capital alpha with
    # psili and prosgegrammeni (U+1F88), the precomposed capital-iota-
    # subscript form.
    raw = 'x\t ' + '̓ͅ' + 'Αι τίνες\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert 'ᾈ' in new


def test_line_start_also_triggers():
    raw = 'x\t' + '̔' + 'Ρώμη εστιν\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert new.startswith('x\t') and 'Ῥώμη' in new


def test_tag_with_greek_is_never_touched():
    # A Greek-named tag (as some .tess files use) must pass through exactly
    # as stored, even though it contains marks-before-capital text that
    # would otherwise match.
    raw = '<nicomachus_of_gerasa. ̔Αριθμητικη 1.1>\t̔Αριθμητικη εστιν\n'
    new, changed, ok = process_line(raw)
    assert ok
    tag_part = new.split('\t', 1)[0]
    assert tag_part == '<nicomachus_of_gerasa. ̔Αριθμητικη 1.1>'
    # the text after the tab (line start case) must still be fixed
    assert 'Ἁριθμητικη' in new.split('\t', 1)[1]


def test_stray_mark_on_consonant_is_untouched():
    # Part B: a mark on a consonant, not before a vowel or rho. Must not be
    # touched by this script (it is handled by hand, not here).
    raw = 'x\tγαπ' + '́' + ' δικ\n'
    new, changed, ok = process_line(raw)
    assert not changed
    assert new == raw
    assert ok


def test_mark_before_lowercase_consonant_is_untouched():
    # Achilles Tatius 2.11.3: ` ̓μέθυστος`, a damaged ἀμέθυστος missing its
    # alpha. The smooth breathing precedes a lowercase mu, a consonant, so
    # it must be left exactly as stored, not moved onto the mu.
    raw = 'x\tοἴνου καὶ ' + '̓' + 'μέθυστος ἦν\n'
    new, changed, ok = process_line(raw)
    assert not changed
    assert new == raw
    assert ok


def test_mark_before_capital_consonant_is_untouched():
    # A capital consonant (other than rho) with a mark in front of it is as
    # wrong to move as a lowercase one: it stays untouched here too.
    raw = 'x\t' + '̔' + 'Γεφυραῖοι ἦσαν\n'
    new, changed, ok = process_line(raw)
    assert not changed
    assert new == raw
    assert ok


def test_invariant_key_ignores_mark_position():
    a = ' ' + '̔' + 'Ηροδότου'
    b = ' ' + nfc('̔' + 'Η') + 'ροδότου'
    assert invariant_key(a) == invariant_key(b)


def test_lowercase_at_line_start():
    # Scope grew to lowercase on 3 October 2026: the same fault also hits a
    # lowercase word-initial vowel at a line start (Strabo: marks before
    # "ετι" for "ἔτι").
    raw = 'x\t' + '̓́' + 'ετι δὲ παχυμερ\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert new.startswith('x\t') and 'ἔτι' in new


def test_lowercase_after_a_space():
    raw = 'x\tἔτι φησὶν ὁ ' + '̓́' + 'ετι τε καὶ\n'
    new, changed, ok = process_line(raw)
    assert changed and ok
    assert 'ὁ ἔτι τε' in new


def test_ordinary_line_unchanged():
    raw = '<hom. il. 1.1>\tμῆνιν ἄειδε θεὰ\n'
    new, changed, ok = process_line(raw)
    assert not changed and ok
    assert new == raw
