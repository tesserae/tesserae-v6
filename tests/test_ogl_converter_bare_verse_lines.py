"""A leaf division of bare <l> verse lines gets one tess line per verse.

Perseus canonical-latinLit's Prudentius files (and Priscian's grammatical
verse) give a leaf textpart no <p> wrapper at all, just a run of <l>
elements with no shared verse-typesetting subtype. The converter's P5 path
used to fall through to its final "else" branch for this shape, calling
get_text_from_element() on the whole div and flattening every line inside
it into one oversized section, discarding per-verse citation entirely
(found staging the MQDQ-to-Perseus replacement for five Prudentius works,
2026-09-30). Split one output line per <l>, cited by the line's own @n (or
a 1-based position if @n is absent). This must not change the existing,
narrower fix for a leaf explicitly marked subtype="verse" (issue #276),
where several <l> elements typeset one single verse and must stay one
section; that case is covered by
tests/test_ogl_converter_verse_lines.py::test_lines_without_a_paragraph_are_still_one_section.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lxml import etree  # noqa: E402

from backend.ogl_converter import extract_sections  # noqa: E402

TEI = 'http://www.tei-c.org/ns/1.0'


def doc(body):
    return etree.fromstring(f'''<TEI xmlns="{TEI}"><text><body>
<div type="edition" n="urn:cts:latinLit:stoa0238.stoa005.perseus-lat2">
{body}
</div></body></text></TEI>'''.encode())


def test_bare_verse_lines_become_one_section_per_line():
    root = doc('''
<div type="textpart" n="1" subtype="section">
<l n="1">Bella bis quinis</l>
<l n="2">operata Iugurthae</l>
<l n="3">annis</l>
</div>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '1.1': 'Bella bis quinis',
        '1.2': 'operata Iugurthae',
        '1.3': 'annis',
    }


def test_bare_verse_lines_without_n_fall_back_to_position():
    root = doc('''
<div type="textpart" n="2" subtype="section">
<l>prima linea</l>
<l>secunda linea</l>
</div>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {'2.1': 'prima linea', '2.2': 'secunda linea'}


def test_a_leaf_marked_verse_still_stays_one_section():
    # Same shape (bare <l>, no <p>) but explicitly typed as one verse
    # typeset across several lines: must not be split (issue #276).
    root = doc('''
<div type="textpart" n="3" subtype="verse">
<l>Πῶς ἐκάθισεν μόνη ἡ πόλις</l>
<l>ἐγενήθη ὡς χήρα.</l>
</div>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {'3': 'Πῶς ἐκάθισεν μόνη ἡ πόλις ἐγενήθη ὡς χήρα.'}
