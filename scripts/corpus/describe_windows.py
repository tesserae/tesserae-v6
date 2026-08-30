#!/usr/bin/env python3
"""Describe passage windows against a vLLM OpenAI endpoint (RunPod or local).

Latin corpus batch 2 (2026-08-30); same prompt contract as the original
corpus describer (gpu_describe_v3.py) and batch 1: schema fields
mode/setting/participants/action_steps/props/themes/imagery_tone/gist,
names_present offered as candidate names (NAMED rule) or an explicit
UNNAMED rule, temperature 0, max_tokens 380. Records are appended to a
sidecar JSONL as they finish, so a dead pod loses minutes, not the run.

Usage:
  python describe_windows.py --windows wins.json --sidecar out.jsonl \
      --endpoint https://<pod>-8000.proxy.runpod.net/v1/chat/completions \
      --model Qwen/Qwen2.5-32B-Instruct-AWQ --stamp <described_by> \
      [--concurrency 32] [--temperature 0.0] [--max-tokens 380] [--only-ids f]

Retries per record: 2 at the given temperature, then one at 0.4 and one
with max_tokens 700 (the batch-1 straggler recipe).
"""
import argparse
import json
import re
import threading
import time
import urllib.request

MODES = ('narrative', 'speech', 'lyric', 'argument', 'description', 'catalog',
         'prayer', 'prophecy', 'dialogue')
SYS = ("You are a scholar of ancient and early literature. You read a passage in Latin, "
       "Ancient Greek, Hebrew, or English and characterize WHAT KIND OF CONTENT it contains, "
       "abstractly, in English. Focus on the recurring pattern and substance, not the specific "
       "words. Reply with ONLY a JSON object with keys: "
       "mode (one of: narrative, speech, lyric, argument, description, catalog, prayer, prophecy, dialogue), "
       "setting (string, empty if none), participants (string, empty if none), "
       "action_steps (list of short strings, empty list if no action), "
       "props (list of short strings), themes (list of 2-5 abstract topic words, e.g. mortality, exile, "
       "hospitality, divine anger, love, war), imagery_tone (short string: dominant imagery and emotional tone), "
       "gist (one sentence). No prose outside the JSON.")
NAMED = ("The following proper names occur in this passage: {names}. "
         "Name ONLY people or places from that list. Some entries may not be "
         "names at all, so ignore any that are not. Do not introduce any other "
         "name, however well it seems to fit the scene.")
UNNAMED = ("This passage names NOBODY. Leave participants unnamed and describe "
           "them by role only, for example 'a speaker and a listener'. Do not "
           "supply names that would fit the scene.")


def ask(endpoint, model, rec, temperature, max_tokens, timeout=300):
    names = [n for n in (rec.get('names_present') or []) if n]
    rule = NAMED.format(names=', '.join(names[:12])) if names else UNNAMED
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'system', 'content': SYS + ' ' + rule},
                     {'role': 'user',
                      'content': f"Passage:\n{rec['text'][:1400]}\n\nJSON:"}],
        'temperature': temperature, 'max_tokens': max_tokens,
    }).encode('utf-8')
    req = urllib.request.Request(endpoint, data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())['choices'][0]['message']['content'] or ''


def parse(raw):
    m = re.search(r'\{.*\}', raw or '', re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if not str(d.get('gist') or '').strip():
        return None
    if str(d.get('mode') or '').lower() not in MODES:
        d['mode'] = 'narrative'
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--windows', required=True)
    ap.add_argument('--sidecar', required=True)
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--stamp', required=True)
    ap.add_argument('--concurrency', type=int, default=32)
    ap.add_argument('--temperature', type=float, default=0.0)
    ap.add_argument('--max-tokens', type=int, default=380)
    ap.add_argument('--only-ids', help='file of ids, one per line: restrict run')
    args = ap.parse_args()

    recs = json.load(open(args.windows, encoding='utf-8'))
    if args.only_ids:
        keep = {l.strip() for l in open(args.only_ids) if l.strip()}
        recs = [r for r in recs if r['id'] in keep]
    done = set()
    try:
        for line in open(args.sidecar, encoding='utf-8'):
            try:
                done.add(json.loads(line)['id'])
            except (ValueError, KeyError):
                pass
    except FileNotFoundError:
        pass
    todo = [r for r in recs if r['id'] not in done]
    print(f'{len(recs)} windows, {len(done)} already described, {len(todo)} to go',
          flush=True)
    if not todo:
        return

    lock = threading.Lock()
    out = open(args.sidecar, 'a', encoding='utf-8')
    stats = {'ok': 0, 'fail': 0, 't0': time.time()}

    def work(rec):
        plans = [(args.temperature, args.max_tokens),
                 (args.temperature, args.max_tokens),
                 (0.4, args.max_tokens), (args.temperature, 700)]
        d = None
        for temp, mt in plans:
            try:
                d = parse(ask(args.endpoint, args.model, rec, temp, mt))
            except Exception as e:
                with lock:
                    print(f"  {rec['id']}: {e}", flush=True)
                time.sleep(2)
            if d:
                break
        with lock:
            if d:
                d['names_in_text'] = None
                out.write(json.dumps({
                    'id': rec['id'], 'language': rec['language'],
                    'work': rec['work'], 'scale': rec.get('scale', ''),
                    'ref_start': rec.get('ref_start', ''),
                    'ref_end': rec.get('ref_end', ''), 'desc': d,
                    'described_by': args.stamp, 'described_from': 'original',
                }, ensure_ascii=False) + '\n')
                out.flush()
                stats['ok'] += 1
            else:
                print(f"  {rec['id']}: FAILED after retries", flush=True)
                stats['fail'] += 1
            n = stats['ok'] + stats['fail']
            if n % 100 == 0:
                el = time.time() - stats['t0']
                print(f'  {n}/{len(todo)}  {el/max(n,1):.2f}s/rec  '
                      f'{stats["fail"]} failed  {el/60:.0f}m', flush=True)

    threads = []
    sem = threading.Semaphore(args.concurrency)

    def runner(rec):
        with sem:
            work(rec)

    for rec in todo:
        t = threading.Thread(target=runner, args=(rec,))
        t.start()
        threads.append(t)
        while sum(1 for x in threads if x.is_alive()) > args.concurrency * 2:
            time.sleep(0.2)
    for t in threads:
        t.join()
    out.close()
    el = time.time() - stats['t0']
    print(f'DONE: {stats["ok"]} described, {stats["fail"]} failed, '
          f'{el/60:.1f} min', flush=True)


if __name__ == '__main__':
    main()
