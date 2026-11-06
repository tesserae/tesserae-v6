"""Time the reader model (services/reader_server.py) on real Theme Search payloads.

The payloads (a query and its 300 passage texts) come from
scripts/profile_theme_search.py --dump-payloads. Each configuration scores all
of them in this process, with no HTTP, and is compared with the first
configuration (the live setting) for the scores and the top ten and top 25.

    python scripts/profile_reader.py --payloads A.json B.json --out OUT.json \
        --configs '[{"name": "live", "threads": 16, "batch": 8, "sort": "chars"}, ...]'

Config keys: name, threads (torch intra-op), batch, sort ("chars" | "tokens" |
"none"), mode ("no_grad" | "inference"), pretok (tokenize all 300 pairs in one
call), dtype ("fp32" | "bf16"), quant (true: int8 dynamic quantization), k (score
only the first k passages), maxlen. Anything but threads/batch/sort/mode/pretok
changes the model's arithmetic and is measured, never merged.
"""
import argparse
import json
import os
import statistics
import sys
import time

MODEL = os.environ.get('READER_MODEL_DIR',
                       '/home/ncoffee/tesserae-models/theme_reader_minilm_2026-09-17')


def load(payload_files):
    out = []
    for f in payload_files:
        out += json.load(open(f))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--payloads', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--configs', required=True)
    ap.add_argument('--interop', type=int, default=0)
    ap.add_argument('--queries', type=int, default=20)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    if args.interop:
        torch.set_num_interop_threads(args.interop)
    tok = AutoTokenizer.from_pretrained(MODEL)
    base_model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
    payloads = load(args.payloads)[:args.queries]
    configs = json.loads(args.configs)

    def make_model(cfg):
        m = base_model
        if cfg.get('quant'):
            m = torch.quantization.quantize_dynamic(base_model, {torch.nn.Linear}, dtype=torch.qint8)
        if cfg.get('dtype') == 'bf16':
            import copy
            m = copy.deepcopy(base_model).to(torch.bfloat16)
        return m

    def score(cfg, model, query, passages, timers):
        maxlen = cfg.get('maxlen', 512)
        k = cfg.get('k')
        if k:
            passages = passages[:k]
        order = list(range(len(passages)))
        sort = cfg.get('sort', 'chars')
        t = time.perf_counter()
        if sort == 'chars':
            order.sort(key=lambda i: len(passages[i].get('text') or ''))
        texts = [passages[i].get('text') or '' for i in order]
        batch = cfg.get('batch', 8)
        encs = None
        if cfg.get('pretok') or sort == 'tokens':
            full = tok([query] * len(texts), texts, truncation=True, max_length=maxlen)
            lens = [len(x) for x in full['input_ids']]
            if sort == 'tokens':
                perm = sorted(range(len(texts)), key=lambda i: lens[i])
                order = [order[i] for i in perm]
                texts = [texts[i] for i in perm]
                full = {kk: [full[kk][i] for i in perm] for kk in full.keys()}
            encs = full
        timers['prep'] += time.perf_counter() - t
        ctx = torch.inference_mode if cfg.get('mode') == 'inference' else torch.no_grad
        scores = {}
        with ctx():
            for i in range(0, len(texts), batch):
                t = time.perf_counter()
                if encs is not None:
                    feats = [{kk: encs[kk][j] for kk in encs.keys()} for j in range(i, min(i + batch, len(texts)))]
                    enc = tok.pad(feats, return_tensors='pt')
                else:
                    enc = tok([query] * len(texts[i:i + batch]), texts[i:i + batch], truncation=True,
                              max_length=maxlen, padding=True, return_tensors='pt')
                timers['tokenize'] += time.perf_counter() - t
                t = time.perf_counter()
                logits = model(**enc).logits.view(-1).float()
                probs = torch.sigmoid(logits).tolist()
                timers['forward'] += time.perf_counter() - t
                for j, s in zip(order[i:i + batch], probs):
                    scores[j] = float(s)
        return [scores[j] for j in range(len(passages))]

    results = []
    ref = None
    for cfg in configs:
        torch.set_num_threads(cfg.get('threads', 16))
        model = make_model(cfg)
        warm = {'prep': 0, 'tokenize': 0, 'forward': 0}
        score(cfg, model, payloads[0]['query'], payloads[0]['passages'][:64], warm)
        times, timers, allscores = [], {'prep': 0.0, 'tokenize': 0.0, 'forward': 0.0}, []
        for p in payloads:
            t = time.perf_counter()
            allscores.append(score(cfg, model, p['query'], p['passages'], timers))
            times.append(time.perf_counter() - t)
        row = {'name': cfg['name'], 'cfg': cfg,
               'median_s': round(statistics.median(times), 3), 'mean_s': round(statistics.mean(times), 3),
               'tokenize_s_per_query': round((timers['prep'] + timers['tokenize']) / len(payloads), 3),
               'forward_s_per_query': round(timers['forward'] / len(payloads), 3)}
        if ref is None:
            ref = allscores
        else:
            maxdiff, o10, o25, same10, same25, same_all = 0.0, [], [], 0, 0, 0
            cfg.get('k')
            for r, s in zip(ref, allscores):
                n = len(s)
                maxdiff = max(maxdiff, max(abs(a - b) for a, b in zip(r[:n], s)))
                rr = sorted(range(len(r)), key=lambda i: (-r[i], i))
                ss = sorted(range(n), key=lambda i: (-s[i], i))
                o10.append(len(set(rr[:10]) & set(ss[:10])))
                o25.append(len(set(rr[:25]) & set(ss[:25])))
                same10 += rr[:10] == ss[:10]
                same25 += rr[:25] == ss[:25]
                same_all += (rr == ss)
            row.update({'max_abs_score_diff': maxdiff,
                        'top10_overlap_mean': round(statistics.mean(o10), 2),
                        'top10_overlap_min': min(o10),
                        'top25_overlap_mean': round(statistics.mean(o25), 2),
                        'top25_overlap_min': min(o25),
                        'queries_top10_same_order': same10, 'queries_top25_same_order': same25,
                        'queries_full_order_same': same_all})
        results.append(row)
        print(json.dumps(row), flush=True)
        json.dump(results, open(args.out, 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
