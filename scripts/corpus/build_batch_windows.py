#!/usr/bin/env python3
"""Build passage windows (+ names_present) for newly imported .tess files.

Latin corpus batch 2 (2026-08-30). Reproduces the standard geometry of the
original corpus build (perseus_trans/build_scene_windows.py): fine = 12
lines step 6, coarse = 30 lines step 15, windows shorter than 4 lines
dropped, describe-prompt text capped at 1400 chars. Window id is
"<work>:<scale>:<start_line_index>", which is what ids.json and
window_texts.db already use.

names_present per window follows build_redescribe_windows.py: capitalised
non-initial words, generic-role stoplist, then a corpus-rarity filter --
resolve the surface form through the lemma table (v/u normalised) and drop
anything whose lemma sits in more than 5% of the corpus. Unresolvable words
are KEPT: treebank lemmatisers do not know proper names, so failure to
resolve is weak evidence FOR a name.

Output: one windows JSON (records ready for the describer, with
names_present), plus optional --upsert-db to write the rows into
window_texts.db (text stored newline-joined and uncapped, matching
build_window_texts.restore_line_breaks; the per-line `lines` table rows are
refreshed for each work as well). Always back up window_texts.db first.
"""
import argparse
import json
import os
import re
import sqlite3
import unicodedata

GENERIC = {
    'lord', 'god', 'gods', 'goddess', 'great', 'people', 'king', 'queen',
    'soldiers', 'citizens', 'narrator', 'speaker', 'author', 'men', 'women',
    'father', 'mother', 'son', 'daughter', 'romans', 'greeks', 'trojans',
    'israelites', 'rome', 'jews', 'disciples', 'crowd', 'army', 'priest',
    'prophet', 'angel', 'servant', 'brother', 'sister', 'husband', 'wife',
}
MAX_NAME_DF_SHARE = 0.05
NAME_RE = re.compile(r'(?<![.;:!?]\s)(?<!^)\b([A-Z][a-z]{3,})\b')


def tess_lines(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
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


def load_rarity(index_db, lemma_table_path):
    lemmas = {}
    if lemma_table_path and os.path.exists(lemma_table_path):
        lemmas = json.load(open(lemma_table_path, encoding='utf-8'))
    df, n = {}, 0
    if index_db and os.path.exists(index_db):
        con = sqlite3.connect(index_db)
        df = {r[0]: r[1] for r in
              con.execute('SELECT lemma, df FROM lemma_doc_freq')}
        n = con.execute('SELECT COUNT(*) FROM texts').fetchone()[0]
        con.close()
    return lemmas, df, n


def names_in(text, lemmas, df, n_texts):
    out, seen = [], set()
    for m in NAME_RE.finditer(text or ''):
        w = m.group(1)
        k = unicodedata.normalize('NFKD', w.lower())
        if k in GENERIC or k in seen:
            continue
        seen.add(k)
        if df and n_texts:
            # v/u-normalised lookup: corpus texts print 'Vergilius' but the
            # lemma table is u-normalised ('uergilius').
            kv = k.replace('v', 'u')
            head = lemmas.get(k) or lemmas.get(kv) or k
            d = df.get(head) or df.get(head.replace('v', 'u'))
            if d is not None and d > MAX_NAME_DF_SHARE * n_texts:
                continue
        out.append(w)
    return out[:12]


def windows_for(path, language, lemmas, df, n_texts):
    work = os.path.basename(path)[:-5]
    lines = tess_lines(path)
    if len(lines) < 4:
        return []
    wins = []
    for scale, size, step in (('fine', 12, 6), ('coarse', 30, 15)):
        if len(lines) < size and scale == 'coarse':
            continue
        for start in range(0, max(1, len(lines) - 3), step):
            chunk = lines[start:start + size]
            if len(chunk) < 4:
                continue
            joined = '\n'.join(t for _r, t in chunk)
            wins.append({
                'id': f'{work}:{scale}:{start}',
                'language': language, 'work': work, 'scale': scale,
                'ref_start': chunk[0][0], 'ref_end': chunk[-1][0],
                'text': joined,
                'names_present': names_in(' '.join(t for _r, t in chunk),
                                          lemmas, df, n_texts),
            })
            if start + size >= len(lines):
                break
    return wins


def upsert(db_path, wins, files):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows = [(w['id'], w['language'], w['work'], w['ref_start'], w['ref_end'],
             w['text']) for w in wins]
    cur.executemany('INSERT OR REPLACE INTO window_texts VALUES (?,?,?,?,?,?)',
                    rows)
    for path in files:
        work = os.path.basename(path)[:-5]
        cur.execute('DELETE FROM lines WHERE work = ?', (work,))
        cur.executemany('INSERT INTO lines VALUES (?,?,?,?)',
                        [(work, i, ref, text)
                         for i, (ref, text) in enumerate(tess_lines(path))])
    conn.commit()
    n = cur.execute('SELECT COUNT(*) FROM window_texts').fetchone()[0]
    conn.close()
    print(f'upserted {len(rows)} window rows; window_texts now {n:,}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--language', default='la')
    ap.add_argument('--index-db', required=True, help='for lemma_doc_freq rarity')
    ap.add_argument('--lemma-table', required=True)
    ap.add_argument('--out', required=True, help='windows JSON for the describer')
    ap.add_argument('--upsert-db', help='window_texts.db to update (back it up first)')
    ap.add_argument('files', nargs='+')
    args = ap.parse_args()

    lemmas, df, n_texts = load_rarity(args.index_db, args.lemma_table)
    print(f'rarity: {len(df):,} lemma dfs over {n_texts} texts; '
          f'table {len(lemmas):,}')
    wins = []
    for path in args.files:
        w = windows_for(path, args.language, lemmas, df, n_texts)
        named = sum(1 for x in w if x['names_present'])
        print(f'  {os.path.basename(path)}: {len(w)} windows ({named} with names)')
        wins.extend(w)
    json.dump(wins, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{len(wins)} windows -> {args.out}')
    if args.upsert_db:
        upsert(args.upsert_db, wins, args.files)


if __name__ == '__main__':
    main()
