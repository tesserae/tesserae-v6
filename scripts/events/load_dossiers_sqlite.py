#!/usr/bin/env python3
"""Load event dossier JSON files (build_event_dossier.py output) into the SQLite
file the Events page reads (backend/blueprints/events.py).

  load_dossiers_sqlite.py --dossiers DIR --out events.sqlite [--llm-judgements llm_judgements.sqlite]

DIR holds one <name>.json per event; files ending .ranked.json are skipped.
Tables: events, passages, documents, scholarship, judgements. Beyond the agreed
columns, passages carries language and window_id, and documents carries
language, lat and lon, so the page can build Reader links and a map; the route
works without them (it falls back to the passage index and omits findspots).
"""
import argparse
import glob
import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE events (id TEXT PRIMARY KEY, label TEXT, type TEXT, date_start INTEGER, date_end INTEGER,
  place TEXT, lat REAL, lon REAL, pleiades_id TEXT, participants TEXT, wikipedia_title TEXT, description TEXT);
CREATE TABLE passages (event_id TEXT, rank INTEGER, work TEXT, ref_start TEXT, ref_end TEXT, score REAL,
  llm_label TEXT, names_matched TEXT, snippet TEXT, language TEXT, window_id TEXT);
CREATE TABLE documents (event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT,
  distance_km REAL, text_snippet TEXT, language TEXT, lat REAL, lon REAL);
CREATE TABLE scholarship (event_id TEXT, kind TEXT, title TEXT, page_ref TEXT, url TEXT);
CREATE TABLE judgements (event_id TEXT, window_id TEXT, label TEXT);
CREATE INDEX passages_event ON passages(event_id);
CREATE INDEX documents_event ON documents(event_id);
CREATE INDEX scholarship_event ON scholarship(event_id);
"""


def clip(text, n):
    text = ' '.join((text or '').split())
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'


def load_one(c, d):
    ev = d['event']
    eid = ev['qid']
    loc = next((m for m in d.get('map', []) if m.get('kind') == 'event location'), None)
    span = ev.get('span') or [None, None]
    c.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
        eid, ev['label'], (ev.get('types') or [None])[0], span[0], span[-1],
        loc['label'] if loc else None, loc['lat'] if loc else None, loc['lon'] if loc else None,
        ev.get('pleiades_id'), json.dumps([p['label'] for p in ev.get('participants', [])], ensure_ascii=False),
        ev.get('wikipedia_title'), ev.get('description')))
    for p in d.get('literary', {}).get('passages', []):
        hits = p.get('hit_lines') or []
        snippet = hits[0].get('snippet') if hits else clip(p.get('text'), 300)
        c.execute('INSERT INTO passages VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
            eid, p['rank'], p['work'], p['ref_start'], p['ref_end'], p.get('score'), p.get('llm_label'),
            json.dumps(p.get('matched', []), ensure_ascii=False), clip(snippet, 400),
            p.get('language'), p.get('window_id')))
        if p.get('llm_label'):
            c.execute('INSERT INTO judgements VALUES (?,?,?)', (eid, p.get('window_id'), p['llm_label']))
    for it in d.get('documents', {}).get('items', []):
        c.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', (
            eid, it['id'], it.get('not_before'), it.get('not_after'), it.get('place'), it.get('distance_km'),
            clip(it.get('edition') or it.get('text'), 300), it.get('language'), it.get('lat'), it.get('lon')))
    for r in d.get('scholarship', {}).get('results', []):
        for a in r.get('citations', []):
            title = a['title'] + (f" ({a['authors']}, {a['year']})" if a.get('authors') else '')
            c.execute('INSERT INTO scholarship VALUES (?,?,?,?,?)', (
                eid, 'article', title, a.get('cites') or (f"p. {a['page']}" if a.get('page') else None), a.get('url')))
        for m in r.get('commentary', []):
            c.execute('INSERT INTO scholarship VALUES (?,?,?,?,?)', (
                eid, 'commentary', f"{m.get('commentator', '')}: {clip(m.get('text'), 160)}", m.get('ref'), None))
    # document findspot coordinates (the items carry them, keep them with the rows)
    return eid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dossiers', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        os.remove(a.out)
    c = sqlite3.connect(a.out)
    c.executescript(SCHEMA)
    n = 0
    for f in sorted(glob.glob(os.path.join(a.dossiers, '*.json'))):
        if f.endswith('.ranked.json'):
            continue
        d = json.load(open(f, encoding='utf-8'))
        if 'event' in d:
            load_one(c, d)
            n += 1
    c.commit()
    c.close()
    print(f'{n} events written to {a.out}')


if __name__ == '__main__':
    main()
