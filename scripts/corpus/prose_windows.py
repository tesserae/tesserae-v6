#!/usr/bin/env python3
"""Cut long prose units into finer passage windows (scale "prose").

The fine passage windows are a fixed number of corpus lines. In a prose work
whose line is a whole chapter or section that makes a window of several
thousand characters (the Annals: 7,500 to 31,000), and one description then
covers a dozen scenes. This cuts each unit (line) of a prose work into windows
of about --target-chars characters, made of whole sentences from that one
unit, and writes them for the describer.

    python scripts/corpus/prose_windows.py --work tacitus.annales \
        --work thucydides.peleponnesian_war --target-chars 1200 --out DIR

    python scripts/corpus/prose_windows.py --audit audit.json --top 10 --out DIR

Per window (windows.jsonl): id "<work file>:prose:<n>" (n counts windows in the
file from 0), work, ref_start and ref_end (both the unit's own reference, so
the Reader's lookups by reference keep working), sub (the window's ordinal in
its unit, from 1), char_start and char_end (offsets in the unit text), scale
"prose", language, text.

A sentence ends at . ; ? ! (or the Greek question mark) followed by a space and
a capital letter. Pieces are merged up to the target; a trailing scrap joins
the window before it; a single sentence over 1.5 times the target is cut at a
space, never inside a word. Units under --min-chars characters are skipped.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys
import unicodedata

END_MARKS = '.;?!;'
SENT_END = re.compile(r'[' + re.escape(END_MARKS) + r'](?=\s+\S)')


def tess_units(path):
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


def sentence_spans(text):
    """(start, end) offsets of the sentences of `text`, covering it fully."""
    cuts = [0]
    for m in SENT_END.finditer(text):
        j = m.end()
        while j < len(text) and text[j].isspace():
            j += 1
        if j < len(text) and unicodedata.category(text[j]) == 'Lu':
            cuts.append(j)
    cuts.append(len(text))
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b > a]


def _split_long(text, a, b, target):
    """Cut an over-long span at spaces near the target length."""
    out, start = [], a
    while b - start > 1.5 * target:
        cut = text.rfind(' ', start + int(target * 0.5), start + target + 1)
        if cut <= start:
            cut = text.find(' ', start + target)
            if cut < 0 or cut >= b:
                break
        out.append((start, cut))
        start = cut + 1
    out.append((start, b))
    return out


def cut_unit(text, target=1200):
    """[(char_start, char_end)] for the windows of one unit."""
    pieces = []
    for a, b in sentence_spans(text):
        if b - a > 1.5 * target:
            pieces.extend(_split_long(text, a, b, target))
        else:
            pieces.append((a, b))
    wins = []
    cur = None
    for a, b in pieces:
        if cur is None:
            cur = [a, b]
        elif (b - cur[0] > target) and (cur[1] - cur[0] >= target / 2):
            wins.append(tuple(cur))
            cur = [a, b]
        else:
            cur[1] = b
    if cur:
        wins.append(tuple(cur))
    # a trailing scrap joins the window before it
    if len(wins) > 1 and wins[-1][1] - wins[-1][0] < target / 3 \
            and wins[-1][1] - wins[-2][0] <= 1.5 * target:
        wins[-2:] = [(wins[-2][0], wins[-1][1])]
    # trim whitespace at the ends
    out = []
    for a, b in wins:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if b > a:
            out.append((a, b))
    return out


def work_files(texts_dir, base):
    """(language, work id, path) for a base work: its parts when it has them,
    else the single file."""
    hits = glob.glob(os.path.join(texts_dir, '*', base + '.part.*.tess'))
    hits.sort(key=lambda p: [int(x) if x.isdigit() else x
                             for x in re.split(r'(\d+)', os.path.basename(p))])
    if not hits:
        hits = glob.glob(os.path.join(texts_dir, '*', base + '.tess'))
    return [(os.path.basename(os.path.dirname(p)),
             os.path.basename(p)[:-5], p) for p in hits]


def windows_for_file(language, work, path, target=1200, min_chars=40):
    out, skipped = [], 0
    n = 0
    for ref, text in tess_units(path):
        if len(text) < min_chars:
            skipped += 1
            continue
        for sub, (a, b) in enumerate(cut_unit(text, target), 1):
            out.append({'id': f'{work}:prose:{n}', 'work': work, 'ref_start': ref,
                        'ref_end': ref, 'sub': sub, 'char_start': a, 'char_end': b,
                        'scale': 'prose', 'language': language, 'text': text[a:b]})
            n += 1
    return out, skipped


def summary(lengths):
    if not lengths:
        return {'windows': 0}
    s = sorted(lengths)
    return {'windows': len(s), 'min': s[0], 'median': int(statistics.median(s)),
            'p10': s[int(0.1 * len(s))], 'p90': s[min(len(s) - 1, int(0.9 * len(s)))],
            'max': s[-1], 'mean': int(sum(s) / len(s))}


def upsert_window_texts(db_path, windows_path):
    """Add the windows' texts to window_texts.db (id, language, work, ref_start,
    ref_end, text), so the export and the text lookups find them."""
    import sqlite3
    rows = []
    with open(windows_path, encoding='utf-8') as fh:
        for line in fh:
            w = json.loads(line)
            rows.append((w['id'], w['language'], w['work'], w['ref_start'],
                         w['ref_end'], w['text']))
    con = sqlite3.connect(db_path)
    con.executemany('INSERT OR REPLACE INTO window_texts VALUES (?,?,?,?,?,?)', rows)
    con.commit()
    n = con.execute('SELECT COUNT(*) FROM window_texts').fetchone()[0]
    con.close()
    return len(rows), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', action='append', default=[], help='base work id; repeatable')
    ap.add_argument('--audit', help='audit.json; with --top or --all-long picks the works')
    ap.add_argument('--top', type=int, help='the N prose works with the longest median fine window')
    ap.add_argument('--all-long', action='store_true', help='every prose work over the audit threshold')
    ap.add_argument('--texts', default='/var/www/tesseraev6_flask/texts')
    ap.add_argument('--target-chars', type=int, default=1200)
    ap.add_argument('--min-chars', type=int, default=40)
    ap.add_argument('--upsert-db', help='install step: add the texts of --upsert-from '
                    'to this window_texts.db (back it up first) and stop')
    ap.add_argument('--upsert-from', help='windows.jsonl for --upsert-db')
    ap.add_argument('--dry-run', action='store_true', help='count only, write nothing')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.upsert_db:
        if not a.upsert_from:
            ap.error('--upsert-db needs --upsert-from')
        added, total = upsert_window_texts(a.upsert_db, a.upsert_from)
        print(f'upserted {added} window rows; window_texts now {total:,}')
        return

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    from backend.work_names import base_work
    bases = list(a.work)
    if a.audit:
        res = json.load(open(a.audit))
        longs = [w for w in res['long_works'] if w['prose']]
        seen = []
        for w in longs:  # already sorted by median, longest first
            b = base_work(w['work'])
            if b not in seen:
                seen.append(b)
        bases += seen[:a.top] if a.top else (seen if a.all_long else [])
    bases = list(dict.fromkeys(bases))
    if not bases:
        ap.error('no works chosen')
    os.makedirs(a.out, exist_ok=True)
    per_work, all_len = {}, []
    out = None if a.dry_run else open(os.path.join(a.out, 'windows.jsonl'), 'w', encoding='utf-8')
    for base in bases:
        files = work_files(a.texts, base)
        if not files:
            print(f'no text file for {base}', file=sys.stderr)
            continue
        lens, skipped = [], 0
        for lang, work, path in files:
            wins, sk = windows_for_file(lang, work, path, a.target_chars, a.min_chars)
            skipped += sk
            for w in wins:
                lens.append(len(w['text']))
                if out:
                    out.write(json.dumps(w, ensure_ascii=False) + '\n')
        per_work[base] = dict(summary(lens), files=len(files), skipped_units=skipped)
        all_len += lens
    if out:
        out.close()
    report = {'target_chars': a.target_chars, 'works': per_work, 'total': summary(all_len)}
    if not a.dry_run:
        json.dump(report, open(os.path.join(a.out, 'windows_report.json'), 'w'), indent=1)
    print(json.dumps(report['total']))


if __name__ == '__main__':
    main()
