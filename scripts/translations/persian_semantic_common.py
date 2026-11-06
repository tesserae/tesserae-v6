#!/usr/bin/env python3
"""Cross-language matching of Persian poems to English translations, for sources whose
scan lost the Persian script (Clarke's Hafiz 1891, Whinfield's Khayyam 1882).

When the printed Persian is not in the OCR, nothing can be matched by first line. The
poems are matched by meaning instead, with the same multilingual model that serves Theme
Search (intfloat/multilingual-e5-large, reached through the loopback service of
services/embed_server.py, 32 texts a call). Meaning alone is a weak basis for a published
alignment, so the rules are strict:

  * a pair is kept only if each side is the other's best match AND the best beats the
    runner-up on both sides by a margin (precision before recall);
  * the pairing is then judged on evidence the matcher never saw: the length of the Persian
    against the length of the English (a poem twice as long should have English twice as
    long) and, where both books keep the alphabetical order of the rhyme letter, the rank
    correlation of the matched positions. A control (the same English shifted along by
    seven) is measured with the same tests.
"""
import hashlib
import json
import math
import os
import time
import urllib.request

URL = os.environ.get('TESSERAE_EMBED_URL', 'http://127.0.0.1:8090/embed')
UA = 'Tesserae-project-delegate (alignment build; local)'


def embed(texts, cache_path, batch=32, pause=0.1):
    """Vectors for the texts, cached on disk by text hash so a rerun costs nothing."""
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path))
    keys = [hashlib.sha1(t.encode('utf-8')).hexdigest() for t in texts]
    todo = [(k, t) for k, t in zip(keys, texts) if k not in cache]
    seen = set()
    todo = [(k, t) for k, t in todo if not (k in seen or seen.add(k))]
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        body = json.dumps({'texts': ['passage: ' + t[:1800] for _, t in chunk]}).encode('utf-8')
        req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json',
                                                              'User-Agent': UA})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    vecs = json.loads(r.read())['vectors']
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5)
        for (k, _), v in zip(chunk, vecs):
            cache[k] = [round(x, 5) for x in v]
        time.sleep(pause)
    if cache_path:
        json.dump(cache, open(cache_path, 'w'))
    return [cache[k] for k in keys]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def similarity_matrix(A, B):
    return [[dot(a, b) for b in B] for a in A]


def mutual_best(S, margin=0.02):
    """Pairs (i, j) where j is i's best, i is j's best, and both lead the runner-up by margin."""
    n, m = len(S), len(S[0])
    best_j = [max(range(m), key=lambda j: S[i][j]) for i in range(n)]
    cols = list(zip(*S))
    best_i = [max(range(n), key=lambda i: cols[j][i]) for j in range(m)]
    out = []
    for i in range(n):
        j = best_j[i]
        if best_i[j] != i:
            continue
        row = sorted(S[i], reverse=True)
        col = sorted(cols[j], reverse=True)
        if row[0] - row[1] >= margin and col[0] - col[1] >= margin:
            out.append((i, j, S[i][j], min(row[0] - row[1], col[0] - col[1])))
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else None


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0] * len(v)
    for k, i in enumerate(order):
        r[i] = k
    return r


def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys))


def csls(S, k=10):
    """Cross-domain similarity local scaling (Conneau et al. 2018): cosines between two
    languages are compressed, and a few 'hub' poems are everyone's nearest neighbor. Each
    cosine is corrected by the mean of its row's and its column's k best, which removes the
    hubs. Returns the corrected matrix."""
    n, m = len(S), len(S[0])
    rk = [sum(sorted(row, reverse=True)[:k]) / k for row in S]
    cols = list(zip(*S))
    ck = [sum(sorted(c, reverse=True)[:k]) / k for c in cols]
    return [[2 * S[i][j] - rk[i] - ck[j] for j in range(m)] for i in range(n)]
