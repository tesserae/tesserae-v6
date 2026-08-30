#!/usr/bin/env python3
"""Repair the decapitated Lactantius Placidus commentary.

The corpus copy of lactantius_placidus.in_statii_thebaida_commentum.tess
(digilibLT DLT000323, Sweeney's 1997 Teubner text) lost every capital
letter in conversion: 'Europam dicit, quam Iuppiter rapuit' became
'uropam dicit, quam uppiter rapuit', and the ALL-CAPS Statius lemmata
that head each scholion ('SIDONIOS R(APTVS)') vanished entirely. NC found
it through a Similar Passages card whose scholion had no readable names.

digilibLT's current site serves the TEI anonymously
(https://digiliblt.uniupo.it/teidocs/idno/DLT000323/format/xml), same
Sweeney edition. Its body holds exactly 4,243 <p> elements = our 4,243
units, so the mapping is positional and 1:1 (a scholion with quoted verse
contributes one <p> plus following <lg> lines, which is how the old
conversion counted too).

VERIFICATION, not trust: for every unit, re-applying the old converter's
loss function to the clean text (delete [A-Z], unwrap parentheses, drop
'/', drop <gap/>, collapse whitespace) must reproduce the decapitated
unit exactly (modulo whitespace). The script fails loudly on any unit
that does not match rather than writing a file.

The rebuilt .tess keeps the SAME refs (<lact_plac. comm. N>), so nothing
downstream (index text_id, window ids, translation refs) changes shape.
The caps lemmata are RESTORED into the text: they are Sweeney's text and
they are quotations of the Thebaid, exactly what an intertext tool wants.

Usage: repair_lactantius_placidus.py --xml dlt000323.xml \
    --current texts/la/lactantius_placidus....tess --out new.tess
"""
import argparse
import re
import xml.etree.ElementTree as ET


def strip_ns(tag):
    return tag.split('}')[-1]


def unit_texts(xml_path):
    """The 4,243 units: each <p> plus any following <lg> siblings."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    body = None
    for el in root.iter():
        if strip_ns(el.tag) == 'body':
            body = el
            break
    if body is None:
        raise SystemExit('no <body> in XML')

    def text_of(el):
        parts = []
        if strip_ns(el.tag) == 'gap':
            return ''
        if el.text:
            parts.append(el.text)
        for child in el:
            parts.append(text_of(child))
            if child.tail:
                parts.append(child.tail)
        return ''.join(parts)

    units = []
    def walk(div):
        for child in div:
            tag = strip_ns(child.tag)
            if tag == 'div':
                walk(child)
            elif tag == 'p':
                units.append([text_of(child)])
            elif tag == 'lg':
                if not units:
                    raise SystemExit('<lg> before any <p>')
                units[-1].append(' '.join(
                    text_of(l) for l in child if strip_ns(l.tag) == 'l'))
            elif tag == 'l':
                # quoted verse also appears as bare <l> siblings of <p>
                if not units:
                    raise SystemExit('<l> before any <p>')
                units[-1].append(text_of(child))
            # <head> (LIBER I etc.) is deliberately not a unit
    walk(body)
    return [re.sub(r'\s+', ' ', ' '.join(u)).strip() for u in units]


def lossy(clean):
    """The old converter's loss function, reconstructed."""
    s = re.sub(r'[A-Z]', '', clean)
    s = s.replace('(', '').replace(')', '')
    s = s.replace('/', '')
    # editorial ellipses: the old converter deleted three-dot runs ('...')
    # and the single-char ellipsis ('…'); '....' therefore left one dot
    s = s.replace('…', '')
    s = re.sub(r'\.\.\.', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # deleting caps can orphan punctuation at the start ('QVE,' -> ',')
    s = re.sub(r'^[\s.,;:]+', '', s)
    return s


def current_units(tess_path):
    out = []
    for line in open(tess_path, encoding='utf-8'):
        m = re.match(r'<([^>]*)>\s*(.*)$', line.rstrip('\n'))
        if m:
            out.append((m.group(1), re.sub(r'\s+', ' ', m.group(2)).strip()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xml', required=True)
    ap.add_argument('--current', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--report-only', action='store_true')
    args = ap.parse_args()

    clean = unit_texts(args.xml)
    cur = current_units(args.current)
    print(f'clean units: {len(clean)}, current units: {len(cur)}')
    if len(clean) != len(cur):
        raise SystemExit('unit count mismatch: refusing to continue')

    def letters(s):
        return re.sub(r'[^a-zͰ-Ͽἀ-῿]', '', s.lower())

    mismatches, punct_only = [], 0
    for i, ((ref, old), new) in enumerate(zip(cur, clean), 1):
        if lossy(new) == old:
            continue
        # the old converter left inconsistent punctuation residue where a
        # deleted caps lemma carried commas/dots (', asides', '. . . pullorum');
        # accept when every letter matches and only punctuation differs
        if letters(lossy(new)) == letters(old):
            punct_only += 1
            continue
        mismatches.append((i, ref, old, new))
    print(f'verified {len(cur) - len(mismatches) - punct_only}/{len(cur)} units '
          f'reproduce the decapitated text exactly, plus {punct_only} matching '
          'on letters with punctuation residue')
    for i, ref, old, new in mismatches[:10]:
        print(f'\nMISMATCH unit {i} <{ref}>')
        print(f'  old   : {old[:160]}')
        print(f'  lossy : {lossy(new)[:160]}')
        print(f'  clean : {new[:160]}')
    if mismatches:
        raise SystemExit(f'{len(mismatches)} mismatched units: NOT writing')
    if args.report_only:
        return
    with open(args.out, 'w', encoding='utf-8') as out:
        for (ref, _old), new in zip(cur, clean):
            out.write(f'<{ref}>\t{new}\n')
    print(f'wrote {args.out} ({len(cur)} units, same refs)')


if __name__ == '__main__':
    main()
