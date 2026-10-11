#!/usr/bin/env python3
"""Audit the length of the fine passage windows, work by work.

A fine window is a fixed number of corpus lines. For a prose work whose line
is a whole chapter, one window can run to tens of thousands of characters, and
one description then covers a dozen scenes. This script cuts each fine
window's text from the corpus file (by the line index in its id, checked
against ref_start, falling back to a search for the references) and reports,
per work, the number of fine windows, the median and 90th percentile length in
characters, and whether the work is prose.

    python scripts/corpus/prose_window_audit.py --index data/passage_index \
        --texts /var/www/tesseraev6_flask/texts --out DIR [--threshold 3000]

Writes DIR/audit.json and DIR/audit.md. Read-only on the index and the texts.
"""
import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..'))


def tess_lines(path):
    """[(ref, text)] for the lines of a .tess file."""
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.startswith('<'):
                continue
            close = line.find('>')
            if close < 0:
                continue
            ref, text = line[1:close].strip(), line[close + 1:].strip()
            if text:
                out.append((ref, text))
    return out


def window_length(lines, wid, ref_start, ref_end):
    """Characters in the lines a window covers, or None when not found."""
    try:
        start = int(wid.rsplit(':', 1)[1])
    except (ValueError, IndexError):
        start = -1
    if not (0 <= start < len(lines) and lines[start][0] == ref_start):
        starts = [i for i, (r, _t) in enumerate(lines) if r == ref_start]
        if not starts:
            return None
        start = starts[0]
    end = next((i for i in range(start, len(lines)) if lines[i][0] == ref_end), None)
    if end is None:
        return None
    return sum(len(t) for _r, t in lines[start:end + 1]) + (end - start)


def percentile(values, q):
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def audit(index_dir, texts_dir, threshold, is_prose):
    per_work = {}
    cache = {}
    missing = {}
    with open(os.path.join(index_dir, 'descriptions.jsonl'), encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('scale') != 'fine':
                continue
            work, lang = r.get('work') or '', r.get('language') or ''
            key = (lang, work)
            if key not in cache:
                path = os.path.join(texts_dir, lang, work + '.tess')
                cache[key] = tess_lines(path) if os.path.exists(path) else None
            lines = cache[key]
            slot = per_work.setdefault(key, [])
            if lines is None:
                missing[key] = missing.get(key, 0) + 1
                continue
            n = window_length(lines, r['id'], r.get('ref_start'), r.get('ref_end'))
            if n is None:
                missing[key] = missing.get(key, 0) + 1
            else:
                slot.append(n)
            # keep memory flat: a cached file is only needed while its work streams
            if len(cache) > 50:
                for k in list(cache)[:25]:
                    del cache[k]
    works = []
    for (lang, work), lens in sorted(per_work.items()):
        if not lens:
            continue
        works.append({
            'work': work, 'language': lang, 'fine_windows': len(lens),
            'unmeasured': missing.get((lang, work), 0),
            'median_chars': int(statistics.median(lens)),
            'p90_chars': percentile(lens, 0.9), 'max_chars': max(lens),
            'prose': bool(is_prose(work, lang)),
        })
    long_works = [w for w in works if w['median_chars'] > threshold]
    long_prose = [w for w in long_works if w['prose']]
    return {
        'threshold_chars': threshold,
        'works_measured': len(works),
        'works_over_threshold': len(long_works),
        'windows_in_works_over_threshold': sum(w['fine_windows'] for w in long_works),
        'prose_works_over_threshold': len(long_prose),
        'windows_in_prose_works_over_threshold': sum(w['fine_windows'] for w in long_prose),
        'unmeasured_windows': sum(missing.values()),
        'long_works': sorted(long_works, key=lambda w: -w['median_chars']),
        'works': works,
    }


def write_md(res, path):
    L = ['# Fine passage window lengths, by work', '',
         f"Works measured: {res['works_measured']}. Threshold: median fine window "
         f"over {res['threshold_chars']} characters.", '',
         f"- Works over the threshold: {res['works_over_threshold']} "
         f"({res['windows_in_works_over_threshold']:,} fine windows), of which prose: "
         f"{res['prose_works_over_threshold']} ({res['windows_in_prose_works_over_threshold']:,} windows).",
         f"- Fine windows whose text could not be located: {res['unmeasured_windows']:,}.", '',
         '## Works over the threshold', '',
         '| work | lang | prose | fine windows | median | p90 | max |', '|---|---|---|---|---|---|---|']
    for w in res['long_works']:
        L.append(f"| {w['work']} | {w['language']} | {'yes' if w['prose'] else 'no'} | "
                 f"{w['fine_windows']} | {w['median_chars']:,} | {w['p90_chars']:,} | {w['max_chars']:,} |")
    L += ['', '## All works', '',
          '| work | lang | prose | fine windows | median | p90 |', '|---|---|---|---|---|---|']
    for w in res['works']:
        L.append(f"| {w['work']} | {w['language']} | {'yes' if w['prose'] else 'no'} | "
                 f"{w['fine_windows']} | {w['median_chars']:,} | {w['p90_chars']:,} |")
    open(path, 'w', encoding='utf-8').write('\n'.join(L) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', required=True)
    ap.add_argument('--texts', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--threshold', type=int, default=3000)
    a = ap.parse_args()
    from backend.distance_filter import is_prose_text
    res = audit(a.index, a.texts, a.threshold, is_prose_text)
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, 'audit.json'), 'w'), indent=1)
    write_md(res, os.path.join(a.out, 'audit.md'))
    print({k: v for k, v in res.items() if k not in ('works', 'long_works')})


if __name__ == '__main__':
    main()
