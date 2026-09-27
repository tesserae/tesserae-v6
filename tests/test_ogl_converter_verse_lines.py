"""A verse keeps its lines when the source marks them as lines.

Swete's Septuagint, as encoded by Open Greek and Latin, gives each verse of
Lamentations a paragraph holding the acrostic letter ("Ἄλεφ.") followed by
the verse itself as <l> lines. The converter took the paragraphs of a leaf
section and ignored everything else, so 88 of the 150 verses in the corpus
held nothing but the letter name (issue #276). A leaf that mixes paragraphs
and lines now yields one section with all of them in document order. A leaf
with paragraphs alone keeps its old behaviour, one section per paragraph.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lxml import etree  # noqa: E402

from backend.ogl_converter import extract_sections  # noqa: E402

TEI = 'http://www.tei-c.org/ns/1.0'


def doc(body):
    return etree.fromstring(f'''<TEI xmlns="{TEI}"><text><body>
<div type="edition" n="urn:cts:greekLit:tlg0527.tlg051.1st1K-grc1">
{body}
</div></body></text></TEI>'''.encode())


def test_a_verse_of_letter_plus_lines_keeps_the_lines():
    root = doc('''
<div type="textpart" subtype="chapter" n="1">
 <div type="textpart" subtype="verse" n="1">
  <p>Ἄλεφ.</p><l>Πῶς ἐκάθισεν μόνη ἡ πόλις</l>
<l>ἐγενήθη ὡς χήρα,</l>
<l>ἄρχουσα ἐν χώραις.</l></div>
 <div type="textpart" subtype="verse" n="2">
  <p>Βήθ.</p><l>Κλαίουσα ἔκλαυσεν ἐν νυκτί.</l></div>
</div>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections['1.1'] == 'Ἄλεφ. Πῶς ἐκάθισεν μόνη ἡ πόλις ἐγενήθη ὡς χήρα, ἄρχουσα ἐν χώραις.'
    assert sections['1.2'] == 'Βήθ. Κλαίουσα ἔκλαυσεν ἐν νυκτί.'


def test_lines_without_a_paragraph_are_still_one_section():
    root = doc('''
<div type="textpart" subtype="chapter" n="5">
 <div type="textpart" subtype="verse" n="1">
<l>Μνήσθητι, Κύριε, ὅ τι ἐγενήθη ἡμῖν·</l>
<l>ἐπίβλεψον καὶ ἰδὲ τὸν ὀνειδισμὸν ἡμῶν.</l></div>
</div>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections['5.1'] == 'Μνήσθητι, Κύριε, ὅ τι ἐγενήθη ἡμῖν· ἐπίβλεψον καὶ ἰδὲ τὸν ὀνειδισμὸν ἡμῶν.'


def test_paragraphs_alone_keep_one_section_each():
    # Prose works were converted this way and their citations must not move.
    root = doc('''
<div type="textpart" subtype="chapter" n="2">
 <div type="textpart" subtype="section" n="3">
  <p>Πρῶτος λόγος.</p>
  <p>Δεύτερος λόγος.</p></div>
</div>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {'2.3.1': 'Πρῶτος λόγος.', '2.3.2': 'Δεύτερος λόγος.'}


def test_notes_inside_a_verse_are_still_dropped():
    root = doc('''
<div type="textpart" subtype="chapter" n="1">
 <div type="textpart" subtype="verse" n="3">
  <p>Γίμελ.</p><note type="marginal">B</note><l>Μετῳκίσθη Ἰουδαία.</l></div>
</div>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections['1.3'] == 'Γίμελ. Μετῳκίσθη Ἰουδαία.'


def test_the_edition_identifier_is_not_part_of_the_citation():
    # The edition division's n is the work's URN. Citations are the textpart
    # numbers beneath it, as every file in the corpus already has them.
    root = doc('''
<div type="textpart" subtype="chapter" n="1">
 <div type="textpart" subtype="verse" n="1"><p>Ἄλεφ.</p><l>Πῶς ἐκάθισεν.</l></div>
</div>''')
    assert [s['citation'] for s in extract_sections(root)] == ['1.1']
