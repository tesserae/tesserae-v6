"""Build the window-text lookup the passage index has never had.

WHY THIS EXISTS

The passage index stores DESCRIPTIONS and embeddings, not source text. That is
fine for retrieval, which compares descriptions, and it is why Theme Search can
answer at all. But it means a result knows its work and its line range and
cannot show the reader a single word of the actual passage.

For Latin, Greek, English, Coptic and Hebrew you can go back to `texts/` and
slice by reference. For Persian and Urdu you cannot: neither language is in
`texts/` on the dev checkout OR in production. They were indexed from
`scene_windows*.json` in a separate workspace, and those files are not under the
web root. So a third of the index has no served route to its own text.

This makes one uniform source: window id -> text, for every language, read
straight from the same window files the describer used. Uniform matters more
than clever here. Slicing `texts/` by reference for five languages and reading
JSON for two would give the export two code paths with different failure modes,
and the rarer path would be the one that breaks unnoticed.

    python scripts/build_window_texts.py            # build
    python scripts/build_window_texts.py --check    # coverage against ids.json

The table is tiny to query and the file is written once per index build. It is
NOT in git: it is derived data, about 300 MB.
"""
import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.environ.get('TESSERAE_PASSAGE_INDEX',
                       os.path.join(HERE, 'data', 'passage_index'))
DB = os.path.join(INDEX, 'window_texts.db')
WINDOW_FILES = [
    '/home/ncoffee/perseus_trans/scene_windows_newlangs.json',
    '/home/ncoffee/perseus_trans/scene_windows.json',
    '/home/ncoffee/perseus_trans/scene_windows_grc2.json',
    '/home/ncoffee/perseus_trans/scene_windows_la2.json',
    '/home/ncoffee/perseus_trans/scene_windows_cop_en.json',
]


def build():
    tmp = DB + '.building'
    if os.path.exists(tmp):
        os.remove(tmp)
    conn = sqlite3.connect(tmp)
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('CREATE TABLE window_texts ('
                 'id TEXT PRIMARY KEY, language TEXT, work TEXT, '
                 'ref_start TEXT, ref_end TEXT, text TEXT)')
    total = 0
    for path in WINDOW_FILES:
        if not os.path.exists(path):
            print(f'  skip (absent): {path}')
            continue
        with open(path, encoding='utf-8') as fh:
            rows = json.load(fh)
        batch = []
        for w in rows:
            if not w.get('id') or not w.get('text'):
                continue
            batch.append((w['id'], w.get('language'), w.get('work'),
                          w.get('ref_start'), w.get('ref_end'), w['text']))
        # INSERT OR IGNORE: the window files overlap, and the first file listed
        # should win rather than the last one loaded silently overwriting it.
        conn.executemany('INSERT OR IGNORE INTO window_texts VALUES (?,?,?,?,?,?)',
                         batch)
        conn.commit()
        total += len(batch)
        print(f'  {len(batch):>8,} from {os.path.basename(path)}')
    conn.execute('CREATE INDEX idx_work ON window_texts(work)')
    conn.commit()
    n = conn.execute('SELECT COUNT(*) FROM window_texts').fetchone()[0]
    conn.close()
    os.replace(tmp, DB)
    print(f'\n{n:,} distinct windows ({total:,} rows read) -> {DB}')
    print(f'{os.path.getsize(DB) / 1e6:.0f} MB')
    return n


def check():
    """Every id the index can return must resolve, or the export has holes."""
    ids_path = os.path.join(INDEX, 'ids.json')
    if not os.path.exists(ids_path):
        print(f'no ids.json at {ids_path}')
        return 1
    ids = json.load(open(ids_path, encoding='utf-8'))
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    have = {r[0] for r in conn.execute('SELECT id FROM window_texts')}
    missing = [i for i in ids if i not in have]
    print(f'index ids   : {len(ids):,}')
    print(f'texts stored: {len(have):,}')
    print(f'missing     : {len(missing):,}')
    if missing:
        by_lang = {}
        for m in missing[:20000]:
            by_lang[m.split(':')[0].split('.')[0]] = by_lang.get(
                m.split(':')[0].split('.')[0], 0) + 1
        top = sorted(by_lang.items(), key=lambda kv: -kv[1])[:8]
        print('  worst works:', ', '.join(f'{k}={v}' for k, v in top))
        print('  examples   :', ', '.join(missing[:3]))
    conn.close()
    return 0 if not missing else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true',
                    help='report coverage against ids.json instead of building')
    args = ap.parse_args()
    if args.check:
        return check()
    build()
    return check()


if __name__ == '__main__':
    sys.exit(main())
