"""The converter also reads the older TEI shape used by Corpus Corporum
(mlat.uzh.ch) and MGH/Perseus-derived files: numbered div1..div7 nesting
keyed by @n or @id, instead of P5's <div type="edition"> containing nested
<div type="textpart">. Found while extending the converter for a batch of
Latin works surveyed from Corpus Corporum (Varro, Hyginus, Justin, Velleius
Paterculus, Sidonius, Isidore): none of those files fit the P5 shape the
converter otherwise expects.

This legacy path only runs when the P5 path (_extract_sections_p5) finds
nothing, so it cannot change how an already-supported file converts; see
test_ogl_converter_verse_lines.py for that shape's own tests, all of which
must keep passing unchanged.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lxml import etree  # noqa: E402

from backend.ogl_converter import (  # noqa: E402
    extract_sections,
    roman_to_int,
    latin_ordinal_word_to_int,
    normalize_citation_token,
)

TEI = 'http://www.tei-c.org/ns/1.0'


def doc(body, ns=TEI):
    if ns:
        return etree.fromstring(
            f'<TEI xmlns="{ns}"><text><body>{body}</body></text></TEI>'.encode()
        )
    return etree.fromstring(f'<TEI><text><body>{body}</body></text></TEI>'.encode())


# --- Roman numeral / Latin ordinal helpers --------------------------------

def test_roman_to_int_handles_subtractive_pairs():
    assert roman_to_int('I') == 1
    assert roman_to_int('IV') == 4
    assert roman_to_int('XLIV') == 44
    assert roman_to_int('CCLXXVII') == 277


def test_roman_to_int_rejects_non_numerals():
    assert roman_to_int('') is None
    assert roman_to_int('pr') is None
    assert roman_to_int('LIBER') is None


def test_latin_ordinal_word_to_int():
    assert latin_ordinal_word_to_int('QUINTUS') == 5
    assert latin_ordinal_word_to_int('DECIMUS') == 10
    assert latin_ordinal_word_to_int('nonus') == 9
    assert latin_ordinal_word_to_int('PRIOR') == 1
    assert latin_ordinal_word_to_int('POSTERIOR') == 2
    assert latin_ordinal_word_to_int('FRIVOLUS') is None


def test_normalize_citation_token_prefers_arabic_but_keeps_literals():
    assert normalize_citation_token('IV') == '4'
    assert normalize_citation_token('5') == '5'
    assert normalize_citation_token('pr') == 'pr'
    assert normalize_citation_token('QUINTUS') == '5'


# --- div1/div2 with @n, bare <p> leaves (Hyginus Astronomica shape) -------

def test_numbered_div1_div2_with_n_and_plain_paragraphs():
    root = doc('''
<div1 n="1"><head>LIBER PRIMUS</head>
<div2 n="1"><head>&#167; I</head><p>Mundus appellatur.</p></div2>
<div2 n="2"><head>&#167; II</head><p>Centron est cuius.</p></div2>
</div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '1.1': 'Mundus appellatur.',
        '1.2': 'Centron est cuius.',
    }


# --- div1 keyed on Roman-numeral @id (Hyginus Fabulae / Sidonius letters) -

def test_roman_numeral_id_becomes_arabic_in_the_citation():
    root = doc('''
<div1 id="I"><head>I. THEMISTO.</head><p>Athamas Aeoli filius.</p></div1>
<div1 id="II"><head>II. INO.</head><p>Ino Cadmi filia.</p></div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {'1': 'Athamas Aeoli filius.', '2': 'Ino Cadmi filia.'}


# --- duplicate @id is disambiguated, never silently dropped --------------

def test_duplicate_id_keeps_both_texts_instead_of_dropping_one():
    # Modeled on the real Hyginus Fabulae file: two <div1> both stamped
    # id="CCLXI", the second a "desiderantur" placeholder for later,
    # separately-numbered lost fables.
    root = doc('''
<div1 id="CCLXI"><head>CCLXI. AGAMEMNON.</head><p>Cum de Graecia.</p></div1>
<div1 id="CCLXI"><head>CCLXI. - CCLXVIII desiderantur.</head><p>desiderantur.</p></div1>''')
    sections = extract_sections(root)
    citations = [s['citation'] for s in sections]
    assert len(citations) == len(set(citations)), "no citation should be dropped or overwritten"
    assert citations[0] == '261'
    assert citations[1] != '261'
    texts = {s['citation']: s['text'] for s in sections}
    assert texts[citations[0]] == 'Cum de Graecia.'
    assert texts[citations[1]] == 'desiderantur.'


# --- head-derived numbering when there is no @n/@id at all (Varro) -------

def test_book_number_parsed_from_liber_head_when_no_n_or_id():
    root = doc('''
<div1><head>LIBER QUINTUS</head>
<div2><head>I.</head><p>Quemadmodum vocabula.</p></div2>
<div2><head>VI.</head><p>Contra in quibus.</p></div2>
</div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '5.1': 'Quemadmodum vocabula.',
        '5.6': 'Contra in quibus.',
    }


# --- milestones splitting a single paragraph (Justin / Velleius shape) ---

def test_milestones_split_one_paragraph_into_several_sections():
    root = doc('''
<div1 id="I" type="lib"><head>LIBER I</head>
<div3 n="1"><head>[cap. 1]</head>
<p><milestone n="1" unit="section"/>Principio rerum gentium.
<milestone n="2" unit="section"/>Populus nullis legibus tenebatur.
<milestone n="3" unit="section"/>Fines imperii tueri magis.</p>
</div3></div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '1.1.1': 'Principio rerum gentium.',
        '1.1.2': 'Populus nullis legibus tenebatur.',
        '1.1.3': 'Fines imperii tueri magis.',
    }


# --- milestones with no paragraph wrapper at all (Varro / Isidore shape) -

def test_milestones_directly_inside_a_div_with_no_paragraph_wrapper():
    root = doc('''
<div1 n="1"><head>LIBER PRIMUS</head>
<div2 n="1"><head>&#167; 1</head>
<milestone n="1" unit="section"/>Disciplina a discendo nomen accepit.
<milestone n="2" unit="section"/>Ars vero dicta est.
</div2></div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '1.1.1': 'Disciplina a discendo nomen accepit.',
        '1.1.2': 'Ars vero dicta est.',
    }


# --- a type="work" wrapper is excluded from the citation (Sidonius) ------

def test_work_level_wrapper_div_is_not_part_of_the_citation():
    root = doc('''
<div1 n="Sidon. epp." type="work"><head>EPISTULARUM LIBER PRIMUS.</head>
<div1 type="part"><head>LIBER PRIMUS.</head>
<div2 id="I"><head>I.</head>
SIDONIUS CONSTANTIO SUO SALUTEM. Diu praecipis, domine maior.
</div2>
</div1></div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert list(sections.keys()) == ['1.1']
    assert sections['1.1'] == 'SIDONIUS CONSTANTIO SUO SALUTEM. Diu praecipis, domine maior.'


def test_work_wrapper_supplies_the_book_number_when_it_has_no_part_child():
    # Sidonius' real Corpus Corporum file gives books 2-9 their own
    # type="part" div, but book 1's letters attach directly to the
    # type="work" wrapper -- its <head> is the only place "LIBER PRIMUS"
    # appears for book 1. The wrapper must supply the book number here,
    # unlike test_work_level_wrapper_div_is_not_part_of_the_citation
    # above where a type="part" div also exists and makes the wrapper's
    # own label redundant.
    root = doc('''
<div1 n="Sidon. epp." type="work"><head>EPISTULARUM LIBER PRIMUS.</head>
<div2 id="I"><head>I.</head>
SIDONIUS CONSTANTIO SUO SALUTEM. Diu praecipis, domine maior.
</div2>
</div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {'1.1': 'SIDONIUS CONSTANTIO SUO SALUTEM. Diu praecipis, domine maior.'}


def test_work_wrapper_with_no_derivable_number_is_omitted_not_literal():
    # Sidonius' Carmina is never divided into books at all: its work
    # wrapper's <head> has no "LIBER" word, and its @n ("Sidon. carm.")
    # is the work's own abbreviation, not a citation number. It must be
    # dropped rather than showing up literally in the citation.
    root = doc('''
<div1 n="Sidon. carm." type="work"><head>GAI SOLLII APOLLINARIS SIDONII CARMINA.</head>
<div2 id="I"><head>I.</head>
<l>Cum iuvenem super astra Iovem natura locaret</l>
</div2>
</div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {'1.1': 'Cum iuvenem super astra Iovem natura locaret'}


# --- bare <l> lines with no verse-level subdivision get per-line cites ---

def test_bare_verse_lines_with_no_verse_subtype_get_one_citation_per_line():
    # Sidonius' Carmina: a whole poem's lines sit directly in the leaf div
    # with no per-verse grouping and no @n on <l>.
    root = doc('''
<div1 n="Sidon. carm." type="work">
<div2 id="I"><head>I.</head>
<l>Cum iuvenem super astra Iovem natura locaret</l>
<l>susciperetque novus regna vetusta deus,</l>
</div2></div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '1.1': 'Cum iuvenem super astra Iovem natura locaret',
        '1.2': 'susciperetque novus regna vetusta deus,',
    }


def test_bare_verse_lines_with_verse_subtype_stay_one_section():
    # A div explicitly typed as a single verse keeps the existing
    # Lamentations-style behaviour: its lines join into one citation
    # rather than being split one-per-line.
    root = doc('''
<div1 n="5" type="verse">
<l>Mnesthete, Domine, quid nobis acciderit;</l>
<l>respice et vide obprobrium nostrum.</l>
</div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '5': 'Mnesthete, Domine, quid nobis acciderit; respice et vide obprobrium nostrum.',
    }


# --- <ab> is a valid leaf-text container, like <p> ------------------------

def test_ab_elements_are_treated_like_paragraphs():
    root = doc('''
<div1 n="1">
<div2 n="1"><ab>First block of text.</ab><ab>Second block of text.</ab></div2>
</div1>''')
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {
        '1.1.1': 'First block of text.',
        '1.1.2': 'Second block of text.',
    }


# --- files with no default namespace (old Perseus P4 style) --------------

def test_no_namespace_file_still_converts():
    root = doc('''
<div1 n="1"><head>LIBER PRIMUS</head>
<div2 n="1"><p>Text with no TEI namespace at all.</p></div2>
</div1>''', ns=None)
    sections = {s['citation']: s['text'] for s in extract_sections(root)}
    assert sections == {'1.1': 'Text with no TEI namespace at all.'}
