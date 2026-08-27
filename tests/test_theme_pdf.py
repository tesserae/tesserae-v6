"""The PDF export, checked by reading the PDF back.

Every way this can fail is SILENT. A missing glyph draws an empty box, not an
error. Unshaped Arabic draws disconnected letters that look like text to anyone
who does not read it. Unreordered Hebrew draws the words backwards. A PDF
library reports success in all three cases.

So these tests do not check that a PDF was produced. They extract the text back
out and check the characters are there, in the right form.

They need the built index, so they skip where it is absent, like the other
integration suites.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import passage_index, window_texts, theme_pdf  # noqa: E402

if not (passage_index.is_available() and window_texts.is_available()):
    pytest.skip('passage index or window-text store not present',
                allow_module_level=True)
if not theme_pdf.available():
    pytest.skip('reportlab or the fonts are not installed',
                allow_module_level=True)

pypdf = pytest.importorskip('pypdf')

# Unicode blocks, for asking "is this script actually in the file?"
ARABIC = (0x0600, 0x06FF)
ARABIC_FORMS = (0xFB50, 0xFEFF)      # contextual forms: the shaped output
HEBREW = (0x0590, 0x05FF)
GREEK = (0x0370, 0x03FF)
COPTIC = (0x2C80, 0x2CFF)


@pytest.fixture(scope='module')
def route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/export'))


@pytest.fixture
def client():
    return app.test_client()


def pdf_text(client, route, q='a%20warrior%20arming', limit=3, languages=None):
    url = f'{route}?q={q}&limit={limit}&format=pdf'
    if languages:
        url += f'&languages={languages}'
    r = client.get(url)
    assert r.status_code == 200, r.get_data()[:200]
    body = r.get_data()
    assert body.startswith(b'%PDF-'), 'not a PDF'
    assert body.rstrip().endswith(b'%%EOF'), 'PDF is truncated'
    import io
    reader = pypdf.PdfReader(io.BytesIO(body))
    return body, '\n'.join(p.extract_text() or '' for p in reader.pages)


def count_in(text, block):
    lo, hi = block
    return sum(1 for ch in text if lo <= ord(ch) <= hi)


def test_it_is_a_pdf_with_the_right_headers(client, route):
    r = client.get(f'{route}?q=a%20storm%20at%20sea&limit=2&format=pdf')
    assert r.status_code == 200
    assert r.headers['Content-Type'] == 'application/pdf'
    assert '.pdf"' in r.headers.get('Content-Disposition', '')
    assert r.get_data().startswith(b'%PDF-')


def test_the_text_is_real_text_not_a_picture(client, route):
    """Selectable, searchable, quotable. An image of a page is not an export."""
    _, text = pdf_text(client, route, q='a%20storm%20at%20sea', limit=3)
    assert len(text) > 500, 'almost nothing extractable; the text may be outlined'
    assert 'Tesserae Theme Search' in text
    assert 'a storm at sea' in text


def test_latin_verse_keeps_its_line_breaks(client, route):
    _, text = pdf_text(client, route, q='a%20storm%20at%20sea', limit=3,
                       languages='la')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    assert len(lines) > 10, 'verse appears to have been run together'


def test_greek_glyphs_survive(client, route):
    _, text = pdf_text(client, route, languages='grc')
    assert count_in(text, GREEK) > 100, 'no Greek in the PDF; font may be missing'


def test_hebrew_is_present_and_not_shaped(client, route):
    """Hebrew needs reordering but NOT contextual shaping: it is not cursive.
    Shaped output here would mean the Arabic path was applied to it."""
    _, text = pdf_text(client, route, languages='he')
    assert count_in(text, HEBREW) > 100, 'no Hebrew in the PDF'
    assert count_in(text, ARABIC_FORMS) == 0, 'Hebrew was run through Arabic shaping'


def test_persian_is_shaped_into_contextual_forms(client, route):
    """THE ONE MOST LIKELY TO BE WRONG AND LOOK RIGHT.

    Arabic script is cursive: every letter takes a different form depending on
    its neighbours. Drawn unshaped, a PDF shows a row of disconnected initial
    forms -- still Arabic characters, still 'present', and unreadable. So the
    test demands the PRESENTATION FORMS, not merely Arabic codepoints.
    """
    _, text = pdf_text(client, route, languages='fa')
    shaped = count_in(text, ARABIC_FORMS)
    raw = count_in(text, ARABIC)
    assert shaped > 100, (
        f'Persian is not shaped ({shaped} presentation forms, {raw} raw): the '
        'PDF will show disconnected letters')
    assert shaped > raw, 'most Persian characters were left unshaped'


def test_coptic_glyphs_survive(client, route):
    """Coptic needs its own font; the body font has no glyphs for it, and a
    missing glyph is silent."""
    _, text = pdf_text(client, route, languages='cop')
    assert count_in(text, COPTIC) > 100, (
        'no Coptic in the PDF; NotoSansCoptic is probably not installed')


def test_the_machine_written_summaries_are_declared(client, route):
    """A reader taking a PDF away must not mistake a generated gist for text."""
    _, text = pdf_text(client, route, q='a%20storm%20at%20sea', limit=2)
    assert 'machine-written' in text


def test_an_unavailable_pdf_says_so_rather_than_failing_oddly(monkeypatch,
                                                              client, route):
    monkeypatch.setattr(theme_pdf, 'available', lambda: False)
    r = client.get(f'{route}?q=storm&limit=1&format=pdf')
    assert r.status_code == 200
    import json
    assert 'unavailable' in json.loads(r.get_data())['error']
