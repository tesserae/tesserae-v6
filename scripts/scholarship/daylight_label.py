#!/usr/bin/env python3
"""Label articles for the Daylight prototype through the campus gateway.

  sample   pass 1: free labels on a 600-article sample spread over journals and
           decades -> OUT/free_labels.jsonl
  label    pass 2: every article against the written vocabulary
           (daylight_vocabulary.json) -> OUT/labels.jsonl

Both are resumable (ids already in the JSONL are skipped) and stop themselves
before --budget seconds so a run fits one foreground call. The model is reached
through backend.assistant.model.complete, as the assistant does. Article text
is sent to the gateway; none of it is stored here, only labels.

  python daylight_label.py sample|label [--workers 8] [--budget 540] [--limit N]
"""
import argparse
import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from daylight_common import (OUT, articles, article_text, citing_sentences,
                             connect, load_gateway_env)

MODEL_TAG = 'campus-gateway'
FREE_SYS = (
    "You are a classical scholar indexing journal articles from 1827 to 1922 (in English, "
    "German, French, Latin or Italian). Reply with ONLY a JSON object with keys: "
    "approaches (list of 1 to 3 short English noun phrases saying HOW the article works, "
    "for example metrical analysis, textual criticism, source criticism, rhetoric and style), "
    "themes (list of 1 to 5 short English noun phrases saying WHAT it is about as a topic, "
    "for example the place of women, kingship, exile, grief and lament, the gods). "
    "Use general scholarly terms, never proper names of people or places. "
    "If the article is not about classical antiquity, use approaches [\"other\"] and themes [\"other\"].")
LAB_SYS = (
    "You are a classical scholar indexing journal articles from 1827 to 1922 (in English, "
    "German, French, Latin or Italian). Choose labels ONLY from the two lists given. "
    "Reply with ONLY a JSON object with keys: approaches (1 to 3 items from the approaches list), "
    "themes (1 to 5 items from the themes list; use [] only if no theme fits). "
    "Copy each label exactly as written in the list. Do not invent labels.")


def build_user(con, a):
    txt = article_text(a['ia_id'])
    cs = citing_sentences(con, a['id'])
    parts = ['Title: %s' % (a['title'] or '')]
    if txt:
        parts.append('Opening of the article: %s' % txt)
    if cs:
        parts.append('Sentences citing ancient works: ' + ' | '.join(cs))
    return '\n\n'.join(parts)


def parse(raw):
    m = re.search(r'\{.*\}', raw or '', re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    ap, th = d.get('approaches'), d.get('themes')
    if not isinstance(ap, list) or not isinstance(th, list):
        return None
    return {'approaches': [str(x).strip().lower() for x in ap if str(x).strip()],
            'themes': [str(x).strip().lower() for x in th if str(x).strip()]}


def sample_ids(arts, n=600, seed=13):
    """Spread over journals and decades: round-robin over (journal, decade) cells."""
    rnd = random.Random(seed)
    cells = {}
    for a in arts:
        cells.setdefault((a['journal'], (a['year'] or 0) // 10), []).append(a)
    for v in cells.values():
        rnd.shuffle(v)
    keys = sorted(cells)
    rnd.shuffle(keys)
    pick = []
    while len(pick) < n and any(cells.values()):
        for k in keys:
            if cells[k] and len(pick) < n:
                pick.append(cells[k].pop())
    return pick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['sample', 'label'])
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--budget', type=int, default=540)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    load_gateway_env()
    from backend.assistant import model
    os.makedirs(OUT, exist_ok=True)
    con = connect()
    arts = articles(con)
    if args.mode == 'sample':
        todo_all, path, system = sample_ids(arts), os.path.join(OUT, 'free_labels.jsonl'), FREE_SYS
    else:
        vocab = json.load(open(os.path.join(OUT, 'daylight_vocabulary.json'), encoding='utf-8'))
        okA, okT = set(vocab['approaches']), set(vocab['themes'])
        system = (LAB_SYS + '\n\nAPPROACHES: ' + '; '.join(vocab['approaches']) +
                  '\n\nTHEMES: ' + '; '.join(vocab['themes']))
        todo_all, path = arts, os.path.join(OUT, 'labels.jsonl')
    done = set()
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            try:
                done.add(json.loads(line)['id'])
            except (ValueError, KeyError):
                pass
    todo = [a for a in todo_all if a['id'] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print('%d to do, %d done' % (len(todo), len(done)), flush=True)
    lock = threading.Lock()
    out = open(path, 'a', encoding='utf-8')
    t0 = time.time()
    st = {'ok': 0, 'fail': 0, 'calls': 0}
    tl = threading.local()

    def work(a):
        if time.time() - t0 > args.budget:
            return
        c = getattr(tl, 'con', None) or connect()
        tl.con = c
        user = build_user(c, a)
        d = None
        for temp in (0.0, 0.0, 0.3):
            raw = model.complete(system, user, max_tokens=300, temperature=temp)
            with lock:
                st['calls'] += 1
            d = parse(raw)
            if d:
                break
            time.sleep(1)
        with lock:
            if not d:
                st['fail'] += 1
                return
            if args.mode == 'label':
                d['approaches'] = [x for x in d['approaches'] if x in okA][:3]
                d['themes'] = [x for x in d['themes'] if x in okT][:5]
            rec = {'id': a['id'], 'journal': a['journal'], 'year': a['year'], **d,
                   'model': MODEL_TAG, 'time': time.strftime('%Y-%m-%dT%H:%M:%S')}
            out.write(json.dumps(rec, ensure_ascii=False) + '\n')
            out.flush()
            st['ok'] += 1
            if st['ok'] % 100 == 0:
                el = time.time() - t0
                print('  %d ok, %d fail, %.1f articles/min' % (st['ok'], st['fail'], st['ok'] / el * 60),
                      flush=True)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, todo))
    el = time.time() - t0
    print('finished: %d ok, %d fail in %.0fs = %.1f articles/min with %d workers'
          % (st['ok'], st['fail'], el, st['ok'] / max(el, 1) * 60, args.workers), flush=True)


if __name__ == '__main__':
    main()
