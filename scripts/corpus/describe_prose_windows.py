#!/usr/bin/env python3
"""Describe staged windows (windows.jsonl) with a BullsAI model.

The staged describer of the Diodorus and Victor installs, taking its windows
from a file instead of window_texts.db, and carrying the prose-window fields
(sub, char_start, char_end) through to the output. Same prompt contract as the
production describer (scripts/corpus/describe_windows.py: SYS, NAMED/UNNAMED
rule, parse); candidate names from build_batch_windows.names_in with the
language's rarity table where one exists (la, grc, en). The gateway key is read
from ~/.config/tesserae/bullsai.env and is never printed.

    python scripts/corpus/describe_prose_windows.py --windows windows.jsonl \
        --model Qwen/Qwen3.8-27B-FP8 --stamp prose-fine-20261011 \
        --out descriptions.jsonl --no-think --concurrency 16 [--limit N]

Resume-safe: ids already in --out are skipped. Records: id, language, work,
scale, ref_start, ref_end, sub, char_start, char_end, desc, described_by,
names_present, ms.
"""
import argparse
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = '/var/www/tesseraev6_flask'
sys.path.insert(0, HERE)
import describe_windows as DW  # noqa: E402
import build_batch_windows as BW  # noqa: E402

GATEWAY = 'https://gateway.bullsai.buffalo.edu/v1/chat/completions'
LEMMA_TABLES = {'la': 'latin_lemmas.json', 'grc': 'greek_lemmas.json', 'en': 'english_lemmas.json'}


def api_key():
    for line in open(os.path.expanduser('~/.config/tesserae/bullsai.env'), encoding='utf-8'):
        if line.startswith('BULLSAI_API_KEY='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('no key')


KEY = api_key()
_rarity = {}
_rarity_lock = threading.Lock()


def rarity_for(lang):
    with _rarity_lock:
        if lang in _rarity:
            return _rarity[lang]
        db = os.path.join(PROD, 'data', 'inverted_index', f'{lang}_index.db')
        table = os.path.join(PROD, 'data', 'lemma_tables', LEMMA_TABLES.get(lang, ''))
        if lang in LEMMA_TABLES and os.path.exists(db) and os.path.exists(table):
            _rarity[lang] = BW.load_rarity(db, table)
        else:
            _rarity[lang] = ({}, {}, 0)
        return _rarity[lang]


WINDOWS_TO_ADD = None  # set from --windows


def load_windows(ids):
    # The text source is the staged windows file, not production's
    # window_texts.db, which does not hold these windows.
    wanted = set(ids)
    out = {}
    with open(WINDOWS_TO_ADD, encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            if r['id'] in wanted:
                out[r['id']] = {'id': r['id'], 'language': r['language'], 'work': r['work'],
                                 'scale': r['scale'], 'ref_start': r['ref_start'],
                                 'ref_end': r['ref_end'], 'text': r.get('text') or '',
                                 **{k: r[k] for k in ('sub', 'char_start', 'char_end') if k in r}}
    return out


EXTRA = {}


def ask(model, rec, temperature, max_tokens, no_think):
    names = rec.get('names_present') or []
    rule = DW.NAMED.format(names=', '.join(names[:12])) if names else DW.UNNAMED
    body = {'model': model, 'temperature': temperature, 'max_tokens': max_tokens,
            'messages': [{'role': 'system', 'content': DW.SYS + ' ' + rule},
                         {'role': 'user', 'content': f"Passage:\n{rec['text'][:1400]}\n\nJSON:"}]}
    if no_think:
        body['chat_template_kwargs'] = {'enable_thinking': False}
    body.update(EXTRA)
    req = urllib.request.Request(GATEWAY, data=json.dumps(body).encode('utf-8'), headers={
        'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:  # nosec B310
        return json.loads(r.read())['choices'][0]['message'].get('content') or ''


MAX_TOKENS = 400


def describe_one(model, rec, stamp, no_think):
    t0 = time.time()
    plans = [(0.0, MAX_TOKENS), (0.0, MAX_TOKENS), (0.4, MAX_TOKENS), (0.0, MAX_TOKENS * 2)]
    for temp, mt in plans:
        try:
            d = DW.parse(ask(model, rec, temp, mt, no_think))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300] if hasattr(e, 'read') else ''
            if e.code == 429 and 'udget' in body:
                # The key's daily budget is spent (found 2026-09-29: 5.0 units a
                # day). Nothing more will succeed until it resets, so stop the
                # whole run instead of writing thousands of error rows.
                sys.stderr.write(f'STOP: {body}\n')
                os._exit(3)
            d = None
        except Exception as e:  # noqa: BLE001
            d = None
        if d:
            return {'id': rec['id'], 'language': rec['language'], 'work': rec['work'],
                    'scale': rec['scale'], 'ref_start': rec['ref_start'], 'ref_end': rec['ref_end'],
                    **{k: rec[k] for k in ('sub', 'char_start', 'char_end') if k in rec},
                    'desc': d, 'described_by': stamp, 'names_present': rec.get('names_present') or [],
                    'ms': int((time.time() - t0) * 1000)}
        time.sleep(1)
    return {'id': rec['id'], 'error': 'no parseable description after 4 tries', 'described_by': stamp}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--windows', required=True, help='windows.jsonl from prose_windows.py')
    ap.add_argument('--model', required=True)
    ap.add_argument('--stamp', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--no-think', action='store_true')
    ap.add_argument('--concurrency', type=int, default=16)
    ap.add_argument('--limit', type=int, default=10**9)
    ap.add_argument('--extra-json', default='{}', help='extra request fields, e.g. {"reasoning_effort":"low"}')
    ap.add_argument('--max-tokens', type=int, default=400, help='raise for models that reason before answering')
    a = ap.parse_args()
    global MAX_TOKENS, WINDOWS_TO_ADD
    WINDOWS_TO_ADD = os.path.abspath(a.windows)
    EXTRA.update(json.loads(a.extra_json))
    MAX_TOKENS = a.max_tokens
    ids = [json.loads(l)['id'] for l in open(WINDOWS_TO_ADD, encoding='utf-8') if l.strip()]
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path, encoding='utf-8'):
            try:
                r = json.loads(line)
                if 'desc' in r:
                    done.add(r['id'])
            except ValueError:
                pass
    todo = [i for i in ids if i not in done][:a.limit]
    print(f'{len(ids)} windows in the slice, {len(done)} done, {len(todo)} to do', flush=True)
    recs = load_windows(todo)
    missing = [i for i in todo if i not in recs]
    if missing:
        print(f'{len(missing)} ids have no stored text and are skipped', flush=True)
    for r in recs.values():
        lemmas, df, n_texts = rarity_for(r['language'])
        r['names_present'] = BW.names_in(r['text'], lemmas, df, n_texts)
    lock = threading.Lock()
    n_ok = n_err = 0
    t_start = time.time()
    with open(out_path, 'a', encoding='utf-8') as fh, ThreadPoolExecutor(a.concurrency) as ex:
        for k, rec in enumerate(ex.map(lambda r: describe_one(a.model, r, a.stamp, a.no_think), recs.values()), 1):
            with lock:
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
                fh.flush()
                if 'desc' in rec:
                    n_ok += 1
                else:
                    n_err += 1
                if k % 200 == 0:
                    rate = k / (time.time() - t_start)
                    print(f'[{k}/{len(recs)}] ok {n_ok} err {n_err} {rate:.1f}/s', flush=True)
    print(f'DONE: {n_ok} described, {n_err} failed, {(time.time()-t_start)/60:.1f} min', flush=True)


if __name__ == '__main__':
    main()
