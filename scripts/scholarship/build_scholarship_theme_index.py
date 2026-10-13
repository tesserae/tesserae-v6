"""Build a Theme Search style index over secondary scholarship.

Prototype for the question "can Theme Search run over commentaries and
articles". It reads the public-domain commentary notes the Scholarship tab
serves (data/commentaries/*.json) and, optionally, the sentences stored by the
JSTOR Early Journal Content citation index (data/citation_index/citations.db),
cuts them into windows of roughly passage-window size, embeds each window with
the live encoder service (multilingual-e5-large, the "query: " prefix the
passage index was built with), and writes the same files backend/passage_index.py
opens:

    ids.json            window ids, embedding row order
    embeddings.npy      float16 (N, 1024), row i matches ids[i]
    descriptions.jsonl  one record per window; desc.gist holds the note text
    window_texts.db     SQLite sidecar: window_texts(id, language, work, ref_start, ref_end, text)

Production is only read. Output goes to --out, never into data/.

    python scripts/scholarship/build_scholarship_theme_index.py --out DIR [--limit N]
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROD = '/var/www/tesseraev6_flask/data'
E5_PREFIX = 'query: '      # same on both sides, as backend/passage_index.py does
ENDPOINT = os.environ.get('TESSERAE_EMBED_ENDPOINT', 'http://127.0.0.1:8090')

# A passage window is a dozen lines, about 100 words. Notes are shorter (median
# 23 words) so consecutive short notes are joined up to MAX_WORDS; a longer note
# is cut at sentence ends into pieces of about CHUNK_WORDS.
MIN_WORDS = 70
MAX_WORDS = 180
CHUNK_WORDS = 150
EMBED_CHARS = 1900         # the encoder truncates at 2000 characters, prefix included


def words(s):
    return len(s.split())


def split_sentences(text):
    parts = re.split(r'(?<=[.!?;])\s+(?=[A-Z"\'(\[])', text.strip())
    return [p for p in parts if p]


def split_long(text, chunk=CHUNK_WORDS):
    """Cut a long note at sentence ends into pieces of about `chunk` words.
    A single sentence longer than the limit is cut by words."""
    pieces, cur, n = [], [], 0
    for s in split_sentences(text):
        sw = words(s)
        if sw > chunk:
            if cur:
                pieces.append(' '.join(cur)); cur, n = [], 0
            toks = s.split()
            for i in range(0, len(toks), chunk):
                pieces.append(' '.join(toks[i:i + chunk]))
            continue
        if n + sw > chunk and cur:
            pieces.append(' '.join(cur)); cur, n = [], 0
        cur.append(s); n += sw
    if cur:
        pieces.append(' '.join(cur))
    return pieces


def _label(unit):
    lemma = (unit.get('lemma') or '').strip()
    text = (unit.get('text') or '').strip()
    return f'{lemma}: {text}' if lemma else text


def split_notes(units, min_words=MIN_WORDS, max_words=MAX_WORDS):
    """Notes (dicts with ref, lemma, text, optional ref_end) to windows.

    Returns a list of dicts {ref_start, ref_end, text, n_notes}. Order is kept.
    Rules: notes with no text are dropped; a note over max_words is cut at
    sentence ends and each piece is its own window; consecutive notes shorter
    than min_words are joined (in file order) until the window reaches
    min_words, never past max_words.
    """
    out = []
    cur = None

    def flush():
        nonlocal cur
        if cur:
            out.append(cur)
        cur = None

    for u in units:
        body = _label(u)
        if not body:
            continue
        ref = u.get('ref') or ''
        ref_end = u.get('ref_end') or ref
        w = words(body)
        if w > max_words:
            flush()
            for piece in split_long(body):
                out.append({'ref_start': ref, 'ref_end': ref_end, 'text': piece, 'n_notes': 1})
            continue
        if cur and words(cur['text']) + w <= max_words:
            cur['text'] += '\n' + body
            cur['ref_end'] = ref_end
            cur['n_notes'] += 1
        else:
            flush()
            cur = {'ref_start': ref, 'ref_end': ref_end, 'text': body, 'n_notes': 1}
        if words(cur['text']) >= min_words:
            flush()
    flush()
    return out


def embed_text(rec):
    """What is sent to the encoder: a short header naming commentator, work and
    place, then the note. The header lets a query that names an author or work
    ("in Homer") reach notes that never repeat the name."""
    work = rec['work'].replace('.', ' ').replace('_', ' ')
    head = f"{rec['commentator']} on {work} {rec['ref_start']}."
    return (E5_PREFIX + head + ' ' + rec['text'].replace('\n', ' '))[:EMBED_CHARS]


def commentary_windows(commentary_dir, include_hebrew=False, include_bible=False):
    for path in sorted(glob.glob(os.path.join(commentary_dir, '*.json'))):
        with open(path, encoding='utf-8') as fh:
            doc = json.load(fh)
        lang = doc.get('language')
        work = doc.get('work', '')
        if (lang == 'he' and not include_hebrew) or (work.startswith('bible.') and not include_bible):
            continue
        key = os.path.basename(path).split('__', 1)[0]
        for i, w in enumerate(split_notes(doc.get('units', []))):
            yield {
                'id': f"{key}:{os.path.basename(path)[:-5].split('__', 1)[1]}:{i}",
                'language': lang, 'work': work, 'source': 'commentary',
                'commentator': doc.get('commentator') or key,
                'ref_start': w['ref_start'], 'ref_end': w['ref_end'],
                'text': w['text'], 'n_notes': w['n_notes'],
            }


def ejc_windows(db_path):
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    q = ('SELECT c.id, c.work_id, c.locus_start, c.locus_end, c.sentence, a.journal, a.authors, a.year, a.title '
         'FROM citations c JOIN articles a ON a.id = c.article_id ORDER BY c.id')
    for cid, work, ls, le, sent, journal, authors, year, title in con.execute(q):
        text = re.sub(r'\s+', ' ', (sent or '')).strip()
        if words(text) < 8:
            continue
        label = f'{authors or "?"} ({year}), {journal or ""}'.strip()
        for j, piece in enumerate(split_long(text) if words(text) > MAX_WORDS else [text]):
            yield {'id': f'ejc:{cid}:{j}', 'language': 'en', 'work': work or '', 'source': 'ejc',
                   'commentator': label, 'ref_start': ls or '', 'ref_end': le or ls or '',
                   'text': piece, 'n_notes': 1, 'title': title}


def write_sidecar(path, records):
    """window_texts.db, the layout backend/window_texts.py reads."""
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, '
                'ref_start TEXT, ref_end TEXT, text TEXT)')
    con.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    con.execute('CREATE INDEX idx_work ON window_texts(work)')
    con.execute('CREATE INDEX idx_lines_work ON lines(work, ord)')
    con.execute('CREATE INDEX idx_lines_ref ON lines(work, ref)')
    con.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)',
                    [(r['id'], r['language'], r['work'], r['ref_start'], r['ref_end'], r['text']) for r in records])
    con.commit()
    con.close()


def description_record(r):
    """A record backend/passage_index.py can load: the note stands in for the
    description (desc.gist must be non-empty or the window is masked)."""
    return {'id': r['id'], 'language': r['language'], 'work': r['work'], 'scale': 'note',
            'ref_start': r['ref_start'], 'ref_end': r['ref_end'],
            'commentator': r['commentator'], 'source': r['source'],
            'desc': {'mode': 'commentary', 'gist': r['text']},
            'blob': r['text']}


def embed_batch(texts, retries=3):
    payload = json.dumps({'texts': texts, 'normalize': True}).encode('utf-8')
    for k in range(retries):
        try:
            req = urllib.request.Request(f'{ENDPOINT}/embed', data=payload,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=300) as r:
                return np.asarray(json.loads(r.read())['vectors'], dtype=np.float32)
        except Exception as e:      # noqa: BLE001
            if k == retries - 1:
                raise
            print('retry after', e, flush=True)
            time.sleep(5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--commentaries', default=os.path.join(PROD, 'commentaries'))
    ap.add_argument('--citations', default=os.path.join(PROD, 'citation_index', 'citations.db'))
    ap.add_argument('--no-ejc', action='store_true')
    ap.add_argument('--limit', type=int, default=0, help='first N windows only (speed test)')
    ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--reverse', action='store_true', help='embed chunks from the end (a second stream beside a forward one)')
    ap.add_argument('--text-only', action='store_true', help='write the sidecar, skip embedding')
    a = ap.parse_args()
    if os.path.abspath(a.out).startswith(os.path.abspath(PROD)):
        sys.exit('refusing to write inside production data')
    os.makedirs(a.out, exist_ok=True)

    t0 = time.time()
    recs = list(commentary_windows(a.commentaries))
    n_comm = len(recs)
    if not a.no_ejc and os.path.exists(a.citations):
        recs += list(ejc_windows(a.citations))
    if a.limit:
        step = max(1, len(recs) // a.limit)
        recs = recs[::step][:a.limit]
    print(f'{len(recs)} windows ({n_comm} commentary), split in {time.time() - t0:.1f}s', flush=True)
    write_sidecar(os.path.join(a.out, 'window_texts.db'), recs)
    with open(os.path.join(a.out, 'descriptions.jsonl'), 'w', encoding='utf-8') as fh:
        for r in recs:
            fh.write(json.dumps(description_record(r), ensure_ascii=False) + '\n')
    with open(os.path.join(a.out, 'embed_texts.jsonl'), 'w', encoding='utf-8') as fh:
        for r in recs:
            fh.write(json.dumps({'id': r['id'], 't': embed_text(r)}, ensure_ascii=False) + '\n')
    if a.text_only:
        return 0

    part_dir = os.path.join(a.out, 'parts')
    os.makedirs(part_dir, exist_ok=True)
    CH = 2048
    t1 = time.time()
    starts = list(range(0, len(recs), CH))
    for c0 in (reversed(starts) if a.reverse else starts):
        pf = os.path.join(part_dir, f'{c0:08d}.npy')
        if os.path.exists(pf):
            continue
        texts = [embed_text(r) for r in recs[c0:c0 + CH]]
        vecs = np.concatenate([embed_batch(texts[i:i + a.batch]) for i in range(0, len(texts), a.batch)])
        np.save(pf + '.tmp.npy', vecs.astype(np.float16))
        os.replace(pf + '.tmp.npy', pf)
        done = min(len(recs), c0 + CH)
        rate = done / max(1e-9, time.time() - t1)
        print(f'embedded {done}/{len(recs)}  {time.time() - t1:.0f}s  (this run, incl. resumed parts)', flush=True)
    emb = np.concatenate([np.load(os.path.join(part_dir, f'{c0:08d}.npy')) for c0 in starts])
    assert emb.shape[0] == len(recs)
    np.save(os.path.join(a.out, 'embeddings.npy'), emb)
    with open(os.path.join(a.out, 'ids.json'), 'w') as fh:
        json.dump([r['id'] for r in recs], fh)
    print(f'done: {emb.shape} in {time.time() - t0:.0f}s', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
