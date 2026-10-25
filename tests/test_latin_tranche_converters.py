"""Converters of the Latin import tranche of 2026-10-24 (Servius, Corpus Thomisticum, Wikisource)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'corpus'))

import corpusthomisticum_to_tess as ct  # noqa: E402
import perseus_servius_to_tess as sv  # noqa: E402
import wikisource_prose_to_tess as wp  # noqa: E402


def test_beta_code_words_become_greek():
    assert sv.fix_betacode('quasi KAIOME/NHS DRUO\\S U(GRO\\N , id') == 'quasi καιομένης δρυὸς ὑγρὸν , id'
    assert sv.fix_betacode('Homerus ποταμῷ R(E/ONTI E)OIKW/S.') == 'Homerus ποταμῷ ῥέοντι ἐοικώς.'


def test_beta_code_ending_after_greek_letters_and_elided_particle():
    assert sv.fix_betacode('Homerus σκόLOPAS (vocat)') == 'Homerus σκόλοπας (vocat)'
    assert sv.fix_betacode("ὃς ᾔδη TA/ T' E)O/NTA") == "ὃς ᾔδη τά τ' ἐόντα"


def test_latin_capitals_are_left_alone():
    assert sv.fix_betacode('SPQR et DEO nihil, M. TULLIUS') == 'SPQR et DEO nihil, M. TULLIUS'


def test_thomisticum_text_cleaning():
    assert ct.strip_tags('<I>humano capiti</I> iungeretur , ut <B>dicitur</B> (XIII) .') == 'humano capiti iungeretur, ut dicitur (XIII).'


def test_roman_numerals_and_wikitext_cleaning():
    assert wp.roman('XII') == 12 and wp.roman('IX') == 9 and wp.roman('IV') == 4
    raw = "{{Liber\n|Ante=x\n}}\n[[Imago:a.jpg|thumb|x]]\n'''Bold''' and [[Link|text]] <div class=text>body</div>\n"
    out = wp.clean(raw)
    assert 'Liber' not in out and 'Imago' not in out and 'Bold and text' in out and 'body' in out


def test_chapter_headings_of_the_two_wikisource_works():
    g = "intro text\n\n== 1. De Adam. ==\n\nFirst chapter.\n\n== 2. De Cain. ==\n\nSecond chapter.\n"
    ch = wp.book_chapters(g, 'gregory')
    assert [c for c, _p in ch] == ['pr', '1', '2'] and ch[1][1] == ['First chapter.']
    h = "===1===\n'''SUMMARY OF ONE.'''\n\nBody one.\n\n===2===\nBody two.\n"
    ch = wp.book_chapters(h, 'geoffrey')
    assert [c for c, _p in ch] == ['1', '2'] and ch[0][1] == ['Body one.']
