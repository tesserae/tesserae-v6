"""People & Places for a text printed in lower case, and without names found only in editors' notes (2026-10-22).

1. Our edition of Pliny's Natural History prints every name in lower case ("etruria", "luna", "rusellana"),
   and the People & Places scan finds names by their capital initial, so the store held 424 mention rows
   for the Natural History against 51,326 for Livy, and Rusellae lacked NH 3.26 (Loeb 3.51), the colony
   "rusellana". This scan reads every passage window of a lower-case work and matches each word against the
   spellings the scan already linked elsewhere in Latin with a capital, keeping a spelling only when it never
   occurs as an ordinary lower-case word in the other Latin texts (so "rusellana" counts and "luna", moon or
   the town of Luna, does not) and has at least four letters. Each match becomes a mention row for the entity
   that spelling is most often linked to, with matcher 'lowercase'.
2. The Epigraphic Database Roma writes editors' notes into the text between 〈: and 〉 ("Rusellis adtributa,
   sed est Cosana"). A document-mention row whose spelling occurs only in such a note, and not in the text
   of the stone, is removed (1,363 rows on 2026-10-22, among them two of Rusellae's six documents).

Then the stored catalog and the spelling table are rebuilt. Run on a copy:

    scan_lowercase_work.py STORE_COPY WINDOW_TEXTS_DB TEXTS_LA_DIR LEIDEN_DB --work pliny_the_elder.naturalis_historia
"""
import argparse
import collections
import glob
import os
import re
import sqlite3
import sys

from backend import entity_extras as extras
from backend import entity_index as ei

TOKEN = re.compile(r'[^\W\d_]+')
MIN_LEN = 4


def fold(t):
    return ei.fold(t)


ENDINGS = sorted(['orum', 'arum', 'ibus', 'um', 'us', 'ae', 'am', 'as', 'os', 'is', 'es', 'em', 'a', 'i', 'o', 'e'],
                 key=len, reverse=True)


def latin_stem(fk):
    for e in ENDINGS:
        if fk.endswith(e) and len(fk) - len(e) >= 5:
            return fk[:-len(e)]
    return None


def linked_spellings(db):
    """{folded spelling: eid} for spellings the scan linked in Latin with a capital, at least twice."""
    best = {}
    for fk, eid, n in db.execute("select m.form_key, m.eid, count(*) from mention_rows m join windows w on w.wid = m.wid "
                                 "where w.language = 'la' and m.cap = 1 and m.form_key is not null "
                                 "group by m.form_key, m.eid"):
        if n >= 2 and (fk not in best or n > best[fk][1]):
            best[fk] = (eid, n)
    return {fk: eid for fk, (eid, _n) in best.items()}


def lowercase_counts(texts_dir, skip):
    counts = collections.Counter()
    for path in glob.glob(os.path.join(texts_dir, '*.tess')):
        if os.path.basename(path).startswith(skip):
            continue
        with open(path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                body = re.sub(r'^<[^>]*>\s*', '', line)
                for tok in TOKEN.findall(body):
                    if tok[:1].islower():
                        counts[fold(tok)] += 1
    return counts


def scan(db, windows_db, texts_dir, work):
    spell = linked_spellings(db)
    lower = lowercase_counts(texts_dir, work)
    usable = {fk: eid for fk, eid in spell.items() if len(fk) >= MIN_LEN and lower.get(fk, 0) == 0}
    # Another case form of a linked spelling counts too: the same stem of at least five letters with a
    # Latin ending ("rusellana" beside "rusellanum"), when the word never occurs lower case elsewhere.
    stems = {}
    for fk, eid in usable.items():
        st = latin_stem(fk)
        if st and len(st) >= 5:
            stems.setdefault(st, set()).add(eid)
    stems = {st: next(iter(e)) for st, e in stems.items() if len(e) == 1}
    w = sqlite3.connect(f'file:{windows_db}?mode=ro', uri=True)
    wins = w.execute("select id, work, ref_start, ref_end, language, text from window_texts "
                     "where work like ? and (id like '%:prosem:%' or id like '%:fine:%')", (work + '.part.%',)).fetchall()
    # The section that holds each word: a window can span several sections of the work.
    line_rows = collections.defaultdict(list)
    for lwork, ordn, ref, ltext in w.execute('select work, ord, ref, text from lines where work like ?', (work + '.part.%',)):
        line_rows[lwork].append((ordn, ref, {fold(t) for t in TOKEN.findall(ltext or '')}))
    ord_of = {}
    for lwork, lst in line_rows.items():
        lst.sort()
        for ordn, ref, _toks in lst:
            ord_of.setdefault((lwork, ref), ordn)

    def section_of(wwork, rs, re_, fk):
        lo, hi = ord_of.get((wwork, rs)), ord_of.get((wwork, re_))
        if lo is None or hi is None:
            return rs
        for ordn, ref, toks in line_rows[wwork]:
            if lo <= ordn <= hi and fk in toks:
                return ref
        return rs

    have = dict(db.execute('select window_id, wid from windows'))
    next_wid = (db.execute('select max(wid) from windows').fetchone()[0] or 0) + 1
    existing = {(eid, wid, fk) for eid, wid, fk in db.execute(
        'select m.eid, m.wid, m.form_key from mention_rows m join windows w on w.wid = m.wid where w.work like ?', (work + '%',))}
    rows, new_windows, per_eid = [], [], collections.Counter()
    for wid_txt, wwork, rs, re_, lang, text in wins:
        found = {}
        for tok in TOKEN.findall(text or ''):
            fk = fold(tok)
            if fk in found:
                continue
            if fk in usable:
                found[fk] = (tok, usable[fk])
            elif len(fk) >= 6 and lower.get(fk, 0) == 0 and latin_stem(fk) in stems:
                found[fk] = (tok, stems[latin_stem(fk)])
        if not found:
            continue
        wid = have.get(wid_txt)
        if wid is None:
            wid = next_wid
            next_wid += 1
            have[wid_txt] = wid
            new_windows.append((wid, wid_txt, wwork, rs, re_, lang or 'la'))
        for fk, (tok, eid) in found.items():
            if (eid, wid, fk) in existing:
                continue
            rows.append((eid, wid, tok, 0, 0, 0, 'lemma', 'lowercase', 0, section_of(wwork, rs, re_, fk), fk))
            per_eid[eid] += 1
    db.executemany('insert into windows values (?,?,?,?,?,?)', new_windows)
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?,?,?,?,?)', rows)
    for eid in per_eid:
        n = db.execute('select count(distinct wid) from mention_rows where eid = ?', (eid,)).fetchone()[0]
        db.execute('update entities set n_windows = ? where eid = ?', (n, eid))
    return {'spellings_linked_with_capital': len(spell), 'usable_spellings': len(usable), 'windows_scanned': len(wins),
            'windows_added': len(new_windows), 'rows_added': len(rows), 'entities_touched': len(per_eid)}


def drop_note_only_documents(db, leiden_db):
    ldb = sqlite3.connect(f'file:{leiden_db}?mode=ro', uri=True)
    texts = dict(ldb.execute("select id, text from leiden where text like '%〈:%'"))
    gone = []
    for rowid, doc, form in db.execute('select rowid, doc_id, form from document_mentions').fetchall():
        t = texts.get(doc)
        if not t or not form:
            continue
        notes = ' '.join(re.findall(r'〈:([^〉]*)〉', t))
        body = re.sub(r'[\[\]()<>{}`]', '', re.sub(r'〈:[^〉]*〉', ' ', t))
        f = fold(form)
        if f in {fold(x) for x in TOKEN.findall(notes)} and f not in {fold(x) for x in TOKEN.findall(body)}:
            gone.append((rowid,))
    db.executemany('delete from document_mentions where rowid = ?', gone)
    return len(gone)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    ap.add_argument('window_texts')
    ap.add_argument('texts_la')
    ap.add_argument('leiden')
    ap.add_argument('--work', default='pliny_the_elder.naturalis_historia')
    a = ap.parse_args()
    db = sqlite3.connect(a.store)
    out = scan(db, a.window_texts, a.texts_la, a.work)
    out['document_rows_removed_note_only'] = drop_note_only_documents(db, a.leiden)
    db.commit()
    db.close()
    extras.write_catalog(a.store)
    extras.write_form_index(a.store)
    print(out)


if __name__ == '__main__':
    sys.exit(main())
