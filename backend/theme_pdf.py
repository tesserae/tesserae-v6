"""A real PDF of Theme Search results, with the passages in their own scripts.

WHY THIS IS HARDER THAN A PDF USUALLY IS

The export has to print seven languages in five scripts, and three of the
awkward cases are all present at once:

  * Greek, Hebrew, Coptic and Latin need a font that actually has the glyphs.
    Most PDF defaults have Latin and nothing else, and a missing glyph in a PDF
    is silent: you get a blank box or nothing, not an error.
  * Persian and Urdu are written in Arabic script, which is CURSIVE. Each letter
    takes a different form depending on its neighbours. Handed to a PDF library
    unprocessed, the text comes out as a row of disconnected initial forms --
    legible to nobody, and wrong in a way an English-speaking reader cannot see.
  * Hebrew, Persian and Urdu run right to left. A PDF has no concept of text
    direction: it draws glyphs where you put them. So the runs have to be
    reordered before drawing, or the words appear backwards.

The earlier export sidestepped all of this by handing the job to the browser,
which solves it properly and for free. That remains the better-rendered route.
This exists because NC asked for a real downloadable file, and a printable page
is not one.

WHAT MAKES IT CORRECT

  fonts    DejaVuSans covers Latin, Greek, Hebrew and Arabic script;
           NotoSansCoptic covers Coptic. Both are already on this machine, so
           nothing is downloaded and nothing needs installing as root. The font
           is chosen PER PASSAGE from its language.
  shaping  arabic_reshaper converts Arabic-script text to its contextual forms.
  order    python-bidi reorders right-to-left runs for drawing.

Every one of those is invisible when it goes wrong, which is why
tests/test_theme_pdf.py checks the bytes rather than trusting the pipeline.
"""
import io
import os

from backend.logging_config import get_logger

logger = get_logger('theme_pdf')

# Scripts written right to left. Hebrew needs reordering but not shaping, since
# it is not cursive; the Arabic-script languages need both.
_RTL = {'he', 'fa', 'ur', 'ar'}
_ARABIC_SCRIPT = {'fa', 'ur', 'ar'}

_FONT_CANDIDATES = {
    'body': ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'],
    'bold': ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'],
    # Bundled first. Read from a home directory this worked in development and
    # would have failed silently in production, where the web user cannot
    # traverse /home/ncoffee. See backend/fonts/README.md.
    'coptic': [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'fonts', 'NotoSansCoptic-Regular.ttf'),
               '/usr/share/fonts/truetype/noto/NotoSansCoptic-Regular.ttf',
               os.path.expanduser('~/.local/share/fonts/NotoSansCoptic-Regular.ttf')],
}

_LANG_NAME = {'la': 'Latin', 'grc': 'Greek', 'en': 'English', 'he': 'Hebrew',
              'cop': 'Coptic', 'fa': 'Persian', 'ur': 'Urdu', 'ar': 'Arabic'}

_registered = False


def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def available():
    """True when a PDF can actually be produced. Checked before offering it."""
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return bool(_first_existing(_FONT_CANDIDATES['body']))


def _register_fonts():
    global _registered
    if _registered:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for name, key in (('Tess', 'body'), ('Tess-Bold', 'bold'), ('TessCoptic', 'coptic')):
        path = _first_existing(_FONT_CANDIDATES[key])
        if path:
            pdfmetrics.registerFont(TTFont(name, path))
        elif key != 'coptic':
            raise RuntimeError(f'no font found for {key}')
        else:
            # Coptic falls back to the body font, which lacks the glyphs. Said
            # out loud, because the failure is otherwise invisible: the PDF
            # renders empty boxes and nobody can tell why.
            logger.warning('[THEMEPDF] no Coptic font; Coptic passages will not render')
    _registered = True


def _font_for(language):
    return 'TessCoptic' if language == 'cop' else 'Tess'


def _shape(text, language):
    """Contextual forms and reading order, for the scripts that need them."""
    if language not in _RTL:
        return text
    out = text
    if language in _ARABIC_SCRIPT:
        try:
            import arabic_reshaper
            out = arabic_reshaper.reshape(out)
        except Exception as e:                                   # noqa: BLE001
            logger.warning('[THEMEPDF] no Arabic shaping: %s', e)
    try:
        from bidi.algorithm import get_display
        out = get_display(out)
    except Exception as e:                                       # noqa: BLE001
        logger.warning('[THEMEPDF] no bidi reordering: %s', e)
    return out


def _esc(s):
    return (str(s or '').replace('&', '&amp;')
            .replace('<', '&lt;').replace('>', '&gt;'))


def build(payload):
    """Bytes of a PDF for one export payload. Raises if reportlab is absent."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    KeepTogether)
    _register_fonts()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Tesserae theme search: {payload.get('query', '')}",
        author='Tesserae V6')

    title = ParagraphStyle('t', fontName='Tess-Bold', fontSize=14, leading=18,
                           spaceAfter=2)
    query = ParagraphStyle('q', fontName='Tess', fontSize=12, leading=16,
                           spaceAfter=4)
    sub = ParagraphStyle('s', fontName='Tess', fontSize=8, leading=11,
                         textColor='#555555', spaceAfter=10)
    head = ParagraphStyle('h', fontName='Tess-Bold', fontSize=10, leading=13,
                          spaceBefore=8, spaceAfter=1)
    meta = ParagraphStyle('m', fontName='Tess', fontSize=7.5, leading=10,
                          textColor='#555555', spaceAfter=3)
    gist = ParagraphStyle('g', fontName='Tess', fontSize=8.5, leading=11,
                          textColor='#444444', spaceAfter=4)
    foot = ParagraphStyle('f', fontName='Tess', fontSize=7.5, leading=10,
                          textColor='#666666', spaceBefore=12)

    flow = [Paragraph('Tesserae Theme Search', title),
            Paragraph(f"&ldquo;{_esc(payload.get('query'))}&rdquo;", query)]
    conf = (payload.get('confidence') or {}).get('level')
    bits = [f"{payload.get('count', 0)} passages", 'oldest first']
    if conf:
        bits.append(f'confidence: {conf}')
    if payload.get('missing_text'):
        bits.append(f"{payload['missing_text']} without source text")
    flow.append(Paragraph(' &middot; '.join(_esc(b) for b in bits), sub))

    for r in payload.get('results') or []:
        lang = r.get('language') or ''
        # The API's own language NAMES come through the JSON export, so accept
        # either the code or the name.
        code = lang if lang in _LANG_NAME else next(
            (k for k, v in _LANG_NAME.items() if v == lang), lang)
        block = []
        who = ', '.join(x for x in (r.get('author'), r.get('work')) if x)
        block.append(Paragraph(f"{r.get('n', '')}. {_esc(who)}", head))
        line = ' &middot; '.join(_esc(x) for x in
                                 (r.get('locus'), r.get('date'), r.get('era'),
                                  _LANG_NAME.get(code, lang)) if x)
        if str(r.get('strong')).lower() in ('no', 'false'):
            line += ' &middot; weak match'
        block.append(Paragraph(line, meta))
        if r.get('gist'):
            block.append(Paragraph(_esc(r['gist']), gist))

        rtl = code in _RTL
        body = ParagraphStyle(
            f'p{code}', fontName=_font_for(code),
            fontSize=11 if rtl else 9.5, leading=17 if rtl else 12.5,
            alignment=TA_RIGHT if rtl else 0,
            leftIndent=6, rightIndent=6, spaceAfter=2)
        for para in str(r.get('text') or '').split('\n'):
            if para.strip():
                block.append(Paragraph(_esc(_shape(para, code)), body))
        flow.append(KeepTogether(block))
        flow.append(Spacer(1, 3 * mm))

    flow.append(Paragraph(
        'Tesserae V6, tesserae.caset.buffalo.edu. Passages are matched by '
        'content rather than wording, so results in different languages need '
        'share no words with the query. The one-line summaries are '
        'machine-written and are not part of the source text.', foot))
    doc.build(flow)
    return buf.getvalue()
