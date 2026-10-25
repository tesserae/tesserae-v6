#!/usr/bin/env python3
"""Convert Latin Wikisource wikitext of two Neo-Latin works into .tess files.

  valla   Lorenzo Valla, De falso credita et ementita Constantini donatione
          pages P (Proemium) and I to VI. Reference <val. don. B.N>: B the
          book (pr for the Proemium, 1 to 6), N the page number of the print
          edition that the transcription marks in parentheses, for example
          (56). A line is the text of one page. A book's opening "(62) I"
          line is removed.
  milton  John Milton's Epitaphium Damonis and In quintum Novembris (1645
          Poemata text as transcribed on Wikisource). One verse line per
          line, numbered from 1 in the poem (the transcription's own margin
          numbers every fifth line are removed). The prose Argumentum of the
          Epitaphium is <milt. epit. dam. arg>.

Usage: wikisource_neolatin_to_tess.py {valla|milton} SRC_DIR OUT_DIR
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wikisource_prose_to_tess import clean  # noqa: E402

VALLA_PAGES = [('pr', 'P'), ('1', 'I'), ('2', 'II'), ('3', 'III'), ('4', 'IV'), ('5', 'V'), ('6', 'VI')]


def valla(src, out):
    lines = []
    for book, suffix in VALLA_PAGES:
        t = (Path(src) / f'De_falso_credita_et_ementita_Constantini_donatione__{suffix}.wiki').read_text(encoding='utf-8')
        t = re.sub(r'\{\{titulus.*?\n\}\}', '', t, flags=re.S)
        t = clean(t)
        t = re.sub(r'^\s*(\(\d+\))\s*[IVX]*\s*$', r'\1', t, flags=re.M)
        t = re.sub(r'\s+', ' ', t).strip()
        # the transcription keeps the edition's page numbers in parentheses:
        # they are the only locator it carries, so a line is the text of one page
        parts = re.split(r'\((\d{2,3})\)', t)
        segs = []
        first = parts[0].strip()
        if first:
            first_page = int(parts[1]) - 1 if len(parts) > 1 else 0
            segs.append((first_page, first))
        for i in range(1, len(parts), 2):
            txt = parts[i + 1].strip()
            if txt:
                segs.append((int(parts[i]), txt))
        for pg, txt in segs:
            txt = re.sub(r'\s+([,.;:?!)])', r'\1', txt)
            lines.append(f'<val. don. {book}.{pg}>\t{txt}')
    (out / 'valla.de_falso_credita_et_ementita_constantini_donatione.tess').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'valla: {len(lines)} lines')


def poem_lines(text):
    m = re.search(r'<poem>(.*?)</poem>', text, flags=re.S)
    out = []
    for ln in m.group(1).split('\n'):
        ln = re.sub(r'\{\{Versus\|\s*\d+\s*\}\}', '', ln)
        ln = re.sub(r'\s+\d+\s*$', '', ln)
        ln = html_unescape(re.sub(r'<[^>]+>', '', ln))
        ln = re.sub(r'\s+', ' ', ln).strip()
        if ln:
            out.append(ln)
    return out


def html_unescape(s):
    import html
    return html.unescape(s)


def milton(src, out):
    spec = [('Epitaphium_Damonis', 'milton.epitaphium_damonis', 'milt. epit. dam.'),
            ('In_quintus_novembris', 'milton.in_quintum_novembris', 'milt. in quint. nov.')]
    for fname, name, tag in spec:
        t = (Path(src) / f'{fname}.wiki').read_text(encoding='utf-8')
        rows = []
        m = re.search(r'===Argumentum===\s*(.*?)\n\s*===', t, flags=re.S)
        if m:
            arg = re.sub(r'<[^>]+>', '', m.group(1))
            arg = html_unescape(re.sub(r'\s+', ' ', arg)).strip()
            rows.append((f'{tag} arg', arg))
        for n, ln in enumerate(poem_lines(t), 1):
            rows.append((f'{tag} {n}', ln))
        (out / f'{name}.tess').write_text('\n'.join(f'<{r}>\t{x}' for r, x in rows) + '\n', encoding='utf-8')
        print(f'{name}: {len(rows)} lines')


if __name__ == '__main__':
    kind, src, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    {'valla': valla, 'milton': milton}[kind](src, out)
