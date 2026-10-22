#!/usr/bin/env python3
"""Each inscription and papyrus as its editor prints it, with the Leiden signs (2026-10-22).

The documents index holds the restored, expanded reading with every editorial sign removed, which is what
the search needs. Shown on a card, that reading hides what the stone has lost and what the editor added:
EDR107014 (the Perusine war in the consular fasti of Cupra Maritima) read "... bello Perusino / uf IIviri
duoviri", where the edition has "[---]uf [---][IIvir(i)] (duoviri)": a word broken off before "uf", a
restored title, and the editor's spelled-out gloss of it. This script renders the EpiDoc edition of every
EDH, EDR, I.Sicily and papyri.info document with the usual signs and stores it for display only:

    [abc]     letters lost and restored by the editor        [---]  text lost, not restored
    a(bc)     an abbreviation and the editor's expansion     (abc)  the editor's expansion alone
    ạ         an uncertain letter (dot below)                 <abc>  letters the editor adds
    {abc}     letters the editor deletes                     [[abc]] letters erased in antiquity
    /         a new line on the stone

A rendering is kept only when its letters agree with the indexed reading of the same document (their
letters, signs and spaces removed, match at least 75 percent), so a card never shows a different text.

    build_leiden_display.py METADATA_DB DOCUMENTS_INDEX_DIR RAW_DIR OUT_SQLITE [--workers 8]
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor

from lxml import etree

TEI = '{http://www.tei-c.org/ns/1.0}'
DOT = '̣'


def _local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else ''


def render(div):
    """The Leiden text of an EpiDoc edition <div>."""
    out = []
    state = {'first_lb': True}

    def emit(s):
        if s:
            out.append(s)

    def walk(el):
        tag = _local(el)
        if tag in ('note', 'head', 'bibl', 'desc', 'certainty', 'figure'):
            emit_tail(el)
            return
        if tag == 'lb':
            if state['first_lb']:
                state['first_lb'] = False
            elif el.get('break') == 'no':
                emit('')
            else:
                emit(' / ')
            emit_tail(el)
            return
        if tag == 'gap':
            reason = el.get('reason') or ''
            emit('[---]' if reason in ('lost', '') else ('+++' if reason == 'illegible' else '[---]'))
            emit_tail(el)
            return
        if tag == 'space':
            emit(' vac. ')
            emit_tail(el)
            return
        if tag == 'unclear':
            text = ''.join(el.itertext())
            emit(''.join(ch + DOT if ch.strip() else ch for ch in text))
            emit_tail(el)
            return
        if tag == 'ex':
            emit('(')
            inner(el)
            emit(')')
            emit_tail(el)
            return
        if tag == 'am':
            emit_tail(el)
            return
        if tag == 'choice':
            pick = None
            for want in ('corr', 'reg'):
                pick = next((c for c in el if _local(c) == want), None)
                if pick is not None:
                    break
            if pick is None and len(el):
                pick = el[0]
            if pick is not None:
                walk_children_only(pick)
            emit_tail(el)
            return
        wrap = {('supplied', 'lost'): ('[', ']'), ('supplied', 'omitted'): ('<', '>'),
                ('supplied', 'subaudible'): ('(', ')'), ('del', None): ('[[', ']]'),
                ('surplus', None): ('{', '}'), ('add', None): ('`', '`')}
        key = (tag, el.get('reason')) if tag == 'supplied' else (tag, None)
        left, right = wrap.get(key, ('', ''))
        if tag == 'supplied' and key not in wrap:
            left, right = '[', ']'
        emit(left)
        inner(el)
        emit(right)
        emit_tail(el)

    def inner(el):
        if el.text:
            emit(el.text)
        for child in el:
            walk(child)

    def walk_children_only(el):
        inner(el)

    def emit_tail(el):
        if el.tail:
            emit(el.tail)

    inner(div)
    s = ''.join(out)
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('][', '').replace(']]]', ']] ]')
    s = re.sub(r'\[\s*\]', '', s)
    s = re.sub(r'\s*/\s*', ' / ', s).strip(' /')
    return s.strip()


def edition_div(path):
    try:
        root = etree.parse(path, etree.XMLParser(recover=True, huge_tree=True)).getroot()
    except (etree.XMLSyntaxError, OSError):
        return None
    for div in root.iter(TEI + 'div'):
        if div.get('type') == 'edition':
            return div
    return None


def fold(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.replace('v', 'u').replace('j', 'i')


def words(s):
    return re.findall(r'[^\W\d_]+', fold(s))


def letters(s):
    return ''.join(words(s))


def agrees(leiden, indexed):
    """The Leiden text, signs removed, says the same as the indexed reading: their letters, spaces and
    signs ignored, match at least 75 percent (difflib ratio). Comparing words failed honest cases where the
    index splits a word at a line end ("be / ne merenti") or runs two together."""
    from difflib import SequenceMatcher
    plain = re.sub(r'\[---\]|\+\+\+|vac\.', ' ', leiden)
    plain = re.sub(r'[\[\]()<>{}`]', '', plain)
    a, b = letters(plain), letters(indexed)
    if not a or not b:
        return False
    m = SequenceMatcher(None, a, b, autojunk=False)
    return m.real_quick_ratio() >= 0.75 and m.quick_ratio() >= 0.75 and m.ratio() >= 0.75


def job(args):
    doc_id, path, indexed = args
    div = edition_div(path)
    if div is None:
        return doc_id, None, 'no edition'
    text = render(div)
    if not text:
        return doc_id, None, 'empty'
    if not agrees(text, indexed):
        return doc_id, None, 'disagrees'
    return doc_id, text, 'ok'


def file_index(raw):
    idx = {}
    for p in glob.glob(os.path.join(raw, 'edh', '**', '*.xml'), recursive=True):
        idx[('edh', os.path.basename(p)[:-4])] = p
    for p in glob.glob(os.path.join(raw, 'edr', '**', '*.xml'), recursive=True):
        idx[('edr', os.path.basename(p)[:-4].lstrip('a'))] = p
    for p in glob.glob(os.path.join(raw, 'isicily', '**', '*.xml'), recursive=True):
        idx[('isicily', os.path.basename(p)[:-4])] = p
    for p in glob.glob(os.path.join(raw, 'papyri', 'DDbDP', '**', '*.xml'), recursive=True):
        idx.setdefault(('papyri', os.path.basename(p)[:-4]), p)
    return idx


def raw_path(idx, row):
    doc_id, edh_id, edr_id, hgv_id = row
    src, local = doc_id.split(':', 1)
    if src == 'edh':
        return idx.get(('edh', local))
    if src == 'edr':
        return idx.get(('edr', local.lstrip('a').replace('EDR', 'EDR')))
    if src == 'merged':
        return idx.get(('edh', edh_id or '')) or idx.get(('edr', edr_id or ''))
    if src == 'isicily':
        return idx.get(('isicily', local))
    if src == 'papyri':
        return idx.get(('papyri', local))
    return None


def indexed_text(index_dir):
    out = {}
    for lang in ('la', 'grc'):
        p = os.path.join(index_dir, f'{lang}_documents_index.db')
        if not os.path.exists(p):
            continue
        c = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
        for ref, content in c.execute('select ref, content from lines'):
            out[ref] = content or ''
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('metadata')
    ap.add_argument('index_dir')
    ap.add_argument('raw')
    ap.add_argument('out')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--only', default=None, help='comma-separated document ids (a test)')
    a = ap.parse_args()
    meta = sqlite3.connect(f'file:{a.metadata}?mode=ro', uri=True)
    rows = meta.execute("select id, edh_id, edr_id, hgv_id from documents where source != 'aio'").fetchall()
    if a.only:
        want = set(a.only.split(','))
        rows = [r for r in rows if r[0] in want]
    idx = file_index(a.raw)
    texts = indexed_text(a.index_dir)
    tasks = []
    missing = 0
    for r in rows:
        p = raw_path(idx, r)
        if p and r[0] in texts:
            tasks.append((r[0], p, texts[r[0]]))
        else:
            missing += 1
    counts = {'ok': 0, 'disagrees': 0, 'no edition': 0, 'empty': 0}
    out = sqlite3.connect(a.out)
    out.executescript('DROP TABLE IF EXISTS leiden; CREATE TABLE leiden (id TEXT PRIMARY KEY, text TEXT);')
    with ProcessPoolExecutor(a.workers) as ex:
        for doc_id, text, status in ex.map(job, tasks, chunksize=200):
            counts[status] += 1
            if text:
                out.execute('insert into leiden values (?, ?)', (doc_id, text))
    out.commit()
    out.close()
    print(json.dumps({'documents': len(rows), 'no raw file or not indexed': missing, **counts}))


if __name__ == '__main__':
    sys.exit(main())
