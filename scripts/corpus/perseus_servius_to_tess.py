#!/usr/bin/env python3
"""Convert the Perseus TEI of Servius (Thilo 1881, as adapted by Corpus Corporum)
into .tess files, a whole-work file plus one file per book.

Sources (Corpus Corporum download of Perseus TEI, edition public domain):
  idno 12710  Commentary on the Aeneid   -> serv. a.
  idno 12711  Commentary on the Eclogues -> serv. ecl.
  idno 12712  Commentary on the Georgics -> serv. g.

Reference style follows the held Georgics file: book.N where N is the verse the
note stands at (the TEI div2 n), book.pr for the prologue (div2 n=0), and for the
Eclogues 0.pr for the general prologue. Where the edition repeats a number, the
repeats carry a letter suffix (72, 72a) so references stay unique, and the
duplicates are listed in the report.

Usage: perseus_servius_to_tess.py SRC.xml {aen|ecl|georg} OUTDIR
"""
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

NS = '{http://www.tei-c.org/ns/1.0}'
CFG = {
    'aen': ('servius_honoratus.in_virgilii_aeneidos_libros_commentarius', 'serv. a.'),
    'ecl': ('servius_honoratus.in_virgilii_bucolicon_librum_commentarius', 'serv. ecl.'),
    'georg': ('servius_honoratus.in_virgilii_georgicon_libros_commentarius', 'serv. g.'),
}


def strip_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.startswith(NS):
            el.tag = el.tag[len(NS):]


# The Perseus TEI leaves a few dozen Greek words in Beta Code (KAKA\ for
# κακά, R(E/ONTI for ῥέοντι) and, in a few places, a Greek word whose ending
# is still Beta Code (σκόLOPAS). They are converted here with the standard
# table. Only tokens that carry a Beta Code mark, or an upper-case run touching
# Greek letters, are touched, so Latin capitals stay as they are.
_BETA = dict(zip('ABGDEZHQIKLMNCOPRSTUFXYW', 'αβγδεζηθικλμνξοπρστυφχψω'))
_MARK = {')': '\u0313', '(': '\u0314', '/': '\u0301', '\\': '\u0300', '=': '\u0342', '|': '\u0345', '+': '\u0308'}
_GREEK = '\u0370-\u03ff\u1f00-\u1fff'
_BETA_TOKEN = re.compile(r"[A-Z*]+(?:[()/\\=|+][A-Z]*)+[()/\\=|+]?|[A-Z]+[()/\\=|+]")
_BETA_MIXED = re.compile(r'(?<=[' + _GREEK + r'])[A-Z]{2,}|[A-Z]{2,}(?=[' + _GREEK + r'])')


def _beta_word(tok):
    cap = False
    pending = []
    chars = []
    for c in tok:
        if c == '*':
            cap = True
        elif c in _MARK:
            if chars:
                chars[-1][1].append(_MARK[c])
            else:
                pending.append(_MARK[c])
        elif c in _BETA:
            chars.append([_BETA[c], pending[:] if (not chars and pending) else []])
            pending = []
        else:
            chars.append([c, []])
    res = []
    for k, (ch, marks) in enumerate(chars):
        if ch == 'σ' and k == len(chars) - 1:
            ch = 'ς'
        if k == 0 and cap:
            ch = ch.upper()
        res.append(ch + ''.join(marks))
    return unicodedata.normalize('NFC', ''.join(res))


def fix_betacode(text):
    text = _BETA_TOKEN.sub(lambda m: _beta_word(m.group(0)), text)
    text = _BETA_MIXED.sub(lambda m: _beta_word(m.group(0)), text)
    # an elided particle after a converted Greek word: ὃς ᾔδη τά T' ἐόντα -> τ'
    text = re.sub(r"(?<=[" + _GREEK + r"] )([A-Z])'", lambda m: _beta_word(m.group(1)) + "'", text)
    return text


def text_of(el):
    parts = []

    def walk(e):
        if e.text:
            parts.append(e.text)
        for c in e:
            if c.tag == 'head':
                pass
            elif c.tag in ('pb', 'milestone', 'anchor', 'delSpan'):
                parts.append(' ')
            else:
                walk(c)
            if c.tail:
                parts.append(c.tail)
    walk(el)
    return fix_betacode(re.sub(r'\s+', ' ', ''.join(parts)).strip())


def convert(src, kind):
    root = ET.parse(src).getroot()
    strip_ns(root)
    body = root.find('.//body')
    books = []  # (book label, [(ref, text)])
    dups = []
    for d1 in body.findall('div1'):
        bk = d1.get('n')
        rows = []
        seen = {}
        d2s = d1.findall('div2')
        if not d2s:  # Eclogues general prologue: paragraphs directly in div1
            t = ' '.join(text_of(p) for p in d1.findall('p')).strip()
            if t:
                rows.append((f'{bk}.pr', t))
        for d2 in d2s:
            n = d2.get('n')
            lab = 'pr' if n == '0' else n
            t = ' '.join(text_of(p) for p in d2.findall('p')).strip()
            if not t:
                continue
            k = lab
            if k in seen:
                seen[k] += 1
                lab = f'{k}{chr(96 + seen[k])}'
                dups.append(f'{bk}.{k} repeated, second occurrence written {bk}.{lab}')
            else:
                seen[k] = 1
            rows.append((f'{bk}.{lab}', t))
        books.append((bk, rows))
    return books, dups


def main():
    src, kind, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    stem, tag = CFG[kind]
    books, dups = convert(src, kind)
    whole = []
    for i, (bk, rows) in enumerate(books):
        lines = [f'<{tag} {ref}>\t{t}' for ref, t in rows]
        whole += lines
    (out / f'{stem}.tess').write_text('\n'.join(whole) + '\n', encoding='utf-8')
    # part files: one per book number; the Eclogues prologue (book 0) joins part 1
    pn = {}
    for bk, rows in books:
        key = '1' if bk == '0' else bk
        pn.setdefault(key, []).extend(f'<{tag} {ref}>\t{t}' for ref, t in rows)
    for key, lines in pn.items():
        (out / f'{stem}.part.{key}.tess').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{stem}: {len(whole)} lines, {len(pn)} parts')
    for d in dups:
        print('  DUP', d)


if __name__ == '__main__':
    main()
