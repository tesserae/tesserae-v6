#!/usr/bin/env python3
"""Extraction pass that also reads the old TEI P4 files.

extract5 addresses every element by the TEI P5 namespace. Nineteen of the Perseus
translations are still in the older P4 form, whose elements sit in no namespace at
all, so every lookup missed and the extractor reported them as having no text
rather than as having failed. They were then simply absent from the results, and
nothing said so. Among them are the whole of Tacitus in Church and Brodribb's
translation and all fourteen works of Claudian, which the gap survey had listed
as needing expensive page scans.

Putting the P4 tree into the P5 namespace is enough: div1/div2/div3, the type
attribute and the milestone units are already handled.
"""
import glob
import json
import os

from lxml import etree

import tei_extract_base as E

ROOT = E.ROOT
NS = 'http://www.tei-c.org/ns/1.0'


def _is_p4(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return '<TEI.2' in fh.read(4000)


def _to_p5(path):
    """Parse a P4 file and return a tree whose elements carry the P5 namespace."""
    root = etree.parse(path, E.PARSER).getroot()
    for el in root.iter():
        if isinstance(el.tag, str) and not el.tag.startswith('{'):
            el.tag = f'{{{NS}}}{el.tag}'
    etree.cleanup_namespaces(root)
    return root


def extract(path):
    if not _is_p4(path):
        return E.extract(path)

    # Same walk as extract5, entered from a re-namespaced root. extract5.extract
    # takes a path, so hand it the normalised tree through a temporary file
    # rather than duplicating two hundred lines of traversal.
    root = _to_p5(path)
    tmp = os.path.join('/tmp', 'p4_' + os.path.basename(path))
    etree.ElementTree(root).write(tmp, encoding='utf-8', xml_declaration=True)
    try:
        meta, chunks = E.extract(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    # Restore the identity fields, which extract5 derives from the file name.
    base = os.path.basename(path)[:-4]
    meta['cts_urn'] = 'urn:cts:%sLit:%s' % ('greek' if 'greekLit' in path else 'latin', base)
    meta['source_file'] = os.path.relpath(path, ROOT)
    return meta, chunks


def main():
    files = sorted(glob.glob(f'{ROOT}/canonical-greekLit/data/*/*/*eng*.xml')) + \
            sorted(glob.glob(f'{ROOT}/canonical-latinLit/data/*/*/*eng*.xml'))
    out, recovered = [], []
    for p in files:
        if p.endswith('.tracking.json'):
            continue
        try:
            meta, chunks = extract(p)
        except Exception as exc:              # a malformed file must not stop the pass
            print('FAILED', os.path.basename(p), exc)
            continue
        out.append({'meta': meta, 'chunks': chunks})
        if chunks and _is_p4(p):
            recovered.append((os.path.basename(p), len(chunks), meta.get('year')))

    with open(f'{ROOT}/extracted6.json', 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False)

    zero = sum(1 for r in out if not r['chunks'])
    print(f'files extracted: {len(out)}   with zero chunks: {zero}')
    print(f'P4 files now yielding text: {len(recovered)}')
    for name, n, year in recovered:
        print(f'   {name:44s} {n:6d} chunks   {year}')


if __name__ == '__main__':
    main()
