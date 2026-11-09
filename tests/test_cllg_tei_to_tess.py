"""Tests for scripts/corpus/cllg_tei_to_tess.py on small inline TEI fixtures (no corpus data)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.corpus.cllg_tei_to_tess import convert  # noqa: E402

HEAD = """<?xml version='1.0' encoding='utf-8'?>
<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt></fileDesc>
<encodingDesc><refsDecl>{refs}</refsDecl></encodingDesc></teiHeader>
<text><body>{body}</body></text></TEI>"""


def run(tmp_path, refs, body, name='x.xml'):
    p = tmp_path / name
    p.write_text(HEAD.format(refs=refs, body=body), encoding='utf-8')
    mode, rows, lines, src = convert(str(p), 't')
    return mode, rows, lines, src


def cites(lines):
    return [r.split(' ', 1)[1] for r, _ in lines]


def test_numbered_leaves_with_preface_and_verse(tmp_path):
    refs = ("<citeStructure match=\"/TEI/text/body/div[@type='chapter']\" use=\"@n\" unit=\"chapter\">"
            "<citeStructure match=\"./div[@type='section']\" use=\"@n\" unit=\"section\"/></citeStructure>")
    body = ("<div type='chapter' n='1'>Πρῶτον προοίμιον τοῦ λόγου. "
            "<div type='section' n='1'><p>Ἀρχὴ τοῦ βιβλίου ἐστὶν αὕτη.</p><note>Latin note here</note></div>"
            "<div type='section' n='2'><head>Κεφάλαιον</head><p>Δεύτερον μέρος τοῦ βιβλίου.</p></div></div>"
            "<div type='chapter' n='2'><div type='section' n='pr'><p>Προοίμιον δευτέρου.</p></div></div>")
    mode, rows, lines, src = run(tmp_path, refs, body)
    assert mode == 'leaves'
    assert cites(lines) == ['1.0', '1.1', '1.2', '2.0']
    assert lines[1][1] == 'Ἀρχὴ τοῦ βιβλίου ἐστὶν αὕτη.'
    assert lines[2][1] == 'Δεύτερον μέρος τοῦ βιβλίου.'          # the heading is dropped
    assert src == sum(1 for c in ''.join(t for _, t in lines) if c.isalpha() and 'Ͱ' <= c <= '῿')


def test_verse_lines_under_fragments_and_latin_run(tmp_path):
    refs = ("<citeStructure match=\"/TEI/text/body/div[@type='fragment']\" use=\"@n\" unit=\"fragment\">"
            "<citeStructure match=\"l\" use=\"@n\" unit=\"l\"/></citeStructure>")
    body = ("<div type='fragment' n='3'><l n='1'>[Ath. 5 e] ἄνδρα μοι ἔννεπε μοῦσα</l>"
            "<l n='2'>πολύτροπον ὃς μάλα πολλὰ ...... ]πλάγχθη</l></div>"
            "<div type='fragment' n='4'><p>Vgl. Zonar. XIII 9, 10 καὶ τὸ ὅτι ἦν ἀρχή, <note>x</note>ἐστὶ τὸ πᾶν.</p></div>")
    mode, rows, lines, src = run(tmp_path, refs, body)
    assert cites(lines) == ['3.1', '3.2', '4']
    assert lines[0][1] == 'ἄνδρα μοι ἔννεπε μοῦσα'                  # the Latin bracket is apparatus
    assert lines[1][1] == 'πολύτροπον ὃς μάλα πολλὰ πλάγχθη'        # the lacuna dots and the bracket go
    assert lines[2][1] == 'καὶ τὸ ὅτι ἦν ἀρχή, ἐστὶ τὸ πᾶν.'        # the Latin run goes


def test_page_cited_prose_lines_hyphen_and_volumes(tmp_path):
    refs = "<citeStructure match=\"/TEI/text/body//pb[@ed='Bk']\" use=\"@n\" unit=\"page\"/>"
    body = ("<milestone ed='Bk' unit='volume' n='1'/><pb ed='Bk' n='7'/><head>ΤΙΤΛΟΣ\nΔΕΥΤΕΡΟΣ</head>"
            "<p>Πρώτη γραμμὴ τοῦ λόγου\nδευτέρα γραμμὴ κατα-\nπαύσωμεν τοῦτον <pb ed='Bk' n='8'/>τρίτη γραμμή\n"
            "ἐν-<pb ed='Bk' n='9'/>θάδε τὸ τέλος.\n</p>"
            "<milestone ed='Bk' unit='volume' n='2'/><pb ed='Bk' n='1'/><p>Νέος τόμος ἄρχεται.</p>")
    mode, rows, lines, src = run(tmp_path, refs, body)
    assert mode == 'pages'
    # the heading's two printed lines are counted but not written; a volume prefix appears because there are two
    assert cites(lines) == ['1.7.3', '1.7.4', '1.7.5', '1.8.1', '1.8.2', '1.9.1', '2.1.1']
    texts = [t for _, t in lines]
    assert texts == ['Πρώτη γραμμὴ τοῦ λόγου', 'δευτέρα γραμμὴ καταπαύσωμεν', 'τοῦτον', 'τρίτη γραμμή',
                     'ἐνθάδε', 'τὸ τέλος.', 'Νέος τόμος ἄρχεται.']      # a hyphenated word stays on its first line, across a page too


def test_pages_with_divisions_and_preface(tmp_path):
    refs = ("<citeStructure match=\"/TEI/text/body/div[@type='book']\" use=\"@n\" unit=\"book\"/>"
            "<citeStructure match=\"/TEI/text/body//pb[@ed='H']\" use=\"@n\" unit=\"page\"/>")
    body = ("<pb ed='H' n='1'/><p>Εἰσαγωγή τις πρὸ τοῦ βιβλίου.</p>"
            "<div type='book' n='1'><p>Πρώτου βιβλίου ἀρχή.\nδευτέρα γραμμή.</p><pb ed='H' n='2'/><p>Τρίτη σελίς.</p></div>")
    mode, rows, lines, src = run(tmp_path, refs, body)
    assert cites(lines) == ['0.1.1', '1.1.2', '1.1.3', '1.2.1']
    other_ed = HEAD.format(refs=refs, body="<pb ed='Z' n='99'/><pb ed='H' n='5'/><p>Μόνη γραμμή ἐστίν.</p>")
    p = tmp_path / 'y.xml'
    p.write_text(other_ed, encoding='utf-8')
    assert cites(convert(str(p), 't')[2]) == ['5.1']                # a pb of another edition is not a page


def test_empty_structure_gives_one_line_per_paragraph_in_order(tmp_path):
    body = ("<head>ΤΙΤΛΟΣ</head><p>Πρώτη παράγραφος τοῦ κειμένου.</p><p>Δευτέρα παράγραφος ἐστίν.</p>"
            "<list><item>Τρίτον ὄνομα</item></list>")
    mode, rows, lines, src = run(tmp_path, '', body)
    assert mode == 'paragraphs'
    assert cites(lines) == ['1', '2', '3']


def test_lb_numbered_fragments_do_not_double_count_newlines(tmp_path):
    refs = ("<citeStructure match=\"/TEI/text/body/div[@type='fragment']\" use=\"@n\" unit=\"fragment\">"
            "<citeStructure match=\".//lb\" use=\"@n\" unit=\"l\"/></citeStructure>")
    body = ("<div type='fragment' n='1a'><p><lb n='1'/>πρώτη γραμμή\nτοῦ ἔπους <lb n='2'/>δευτέρα γραμμή</p></div>")
    mode, rows, lines, src = run(tmp_path, refs, body)
    assert mode == 'lb'
    assert cites(lines) == ['1a.1', '1a.2']
    assert lines[0][1] == 'πρώτη γραμμή τοῦ ἔπους'


def test_marginalia_and_editorial_text(tmp_path):
    refs = "<citeStructure match=\"/TEI/text/body/div[@type='section']\" use=\"@n\" unit=\"section\"/>"
    body = ("<div type='section' n='1'><p>λόγος <seg rend='Marginalia'>ΠΕΡΙΘΩΡΙΟΝ</seg><supplied>ἔστι</supplied> "
            "<unclear>τι</unclear><gap/> <add>καὶ</add> <del>οὐ</del> ἄλλο.</p></div>")
    mode, rows, lines, src = run(tmp_path, refs, body)
    assert lines[0][1] == 'λόγος ἔστι τι καὶ οὐ ἄλλο.'
