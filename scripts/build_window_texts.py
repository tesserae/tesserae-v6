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

# WHERE THE VERSE LINES COME FROM.
#
# The window files join a passage's lines with spaces, so the text they carry is
# one long paragraph. That is fine for describing and embedding, which is all it
# was ever used for, and wrong the moment a reader sees it: the first export
# printed the opening of the Aeneid as prose, "Arma virumque cano, Troiae qui
# primus ab oris Italiam, fato profugus...", with line 1 running into line 2.
#
# The .tess files are one line per verse, tagged "<verg. aen. 1.1>\tArma...", so
# the breaks can be restored by slicing each work between the window's own
# ref_start and ref_end. The corpus is spread over three checkouts and no single
# one holds every language: Latin, Greek, English, Coptic and Hebrew here,
# Persian in the Persian workspace, Urdu in the v6 tree.
TEXT_TREES = [
    os.path.join(HERE, 'texts'),
    '/home/ncoffee/tesserae-persian/texts',
    '/home/ncoffee/tesserae-v6-dev/texts',
]
# The vernacular batch of 2026-09 left no window file behind, so its 6,467
# windows had descriptions and embeddings and no text at all: searchable, and
# unreadable. scripts/fill_window_texts_from_index.py rebuilds rows like those
# from the index's own references, which is the route to take when a batch's
# window file is gone.
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
    restore_line_breaks(conn)
    build_lines(conn)
    n = conn.execute('SELECT COUNT(*) FROM window_texts').fetchone()[0]
    conn.close()
    os.replace(tmp, DB)
    print(f'\n{n:,} distinct windows ({total:,} rows read) -> {DB}')
    print(f'{os.path.getsize(DB) / 1e6:.0f} MB')
    return n


def _tess_index():
    """basename without .tess -> path, first tree listed winning."""
    found = {}
    for tree in TEXT_TREES:
        if not os.path.isdir(tree):
            print(f'  skip (absent): {tree}')
            continue
        for root, _dirs, files in os.walk(tree):
            for f in files:
                if f.endswith('.tess'):
                    found.setdefault(f[:-5], os.path.join(root, f))
    return found


def _lines_of(path):
    """[(ref, text)] in file order, from "<ref>\\ttext" lines."""
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.startswith('<'):
                continue
            close = line.find('>')
            if close < 0:
                continue
            ref = line[1:close]
            text = line[close + 1:].lstrip('\t')
            out.append((ref, text))
    return out


def build_lines(conn):
    """Every line of every work, addressable by its own reference.

    Claude desktop, testing the connector: theme_search tells an agent "the gist
    is a machine-written summary, never the passage itself: fetch the lines
    before quoting", and no tool could. The only workaround was an exact-phrase
    search on wording the user already knew by heart, which is exactly the
    reader the feature exists to serve without.

    The windows cannot answer it. They overlap, they start and stop on window
    boundaries rather than on the reference asked for, and their text is a
    single blob. A passage fetch has to return line-by-line references, because
    the presentation contract requires a locus on every quotation.

    This lives in the same file as the window texts, rather than reading
    `texts/` at request time, for the reason that file exists at all: Persian
    and Urdu are not in `texts/` in production, so a route that read from there
    would work for five languages and quietly fail for two.
    """
    files = _tess_index()
    conn.execute('CREATE TABLE IF NOT EXISTS lines ('
                 'work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    works = [r[0] for r in conn.execute(
        'SELECT DISTINCT work FROM window_texts WHERE work IS NOT NULL')]
    total = 0
    for work in works:
        path = files.get(work)
        if not path:
            continue
        rows = [(work, i, ref, text)
                for i, (ref, text) in enumerate(_lines_of(path))]
        if rows:
            conn.executemany('INSERT INTO lines VALUES (?,?,?,?)', rows)
            total += len(rows)
        conn.commit()
    conn.execute('CREATE INDEX IF NOT EXISTS idx_lines_work ON lines(work, ord)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_lines_ref ON lines(work, ref)')
    conn.commit()
    print(f'  addressable lines    : {total:,}')
    return total


def restore_line_breaks(conn):
    """Replace each window's space-joined text with its real verse lines.

    Works work by work so only one .tess is held at a time. A window whose
    references cannot be found keeps the space-joined text it already has, and
    those are COUNTED and reported: a silent fallback here would print poetry as
    prose for one corner of the corpus and nobody would know which.
    """
    files = _tess_index()
    print(f'\n  {len(files):,} .tess files across {len(TEXT_TREES)} trees')
    works = [r[0] for r in conn.execute(
        'SELECT DISTINCT work FROM window_texts WHERE work IS NOT NULL')]
    fixed = kept = no_file = 0
    missing_works = []
    for work in works:
        path = files.get(work)
        if not path:
            no_file += 1
            if len(missing_works) < 8:
                missing_works.append(work)
            continue
        lines = _lines_of(path)
        at = {ref: i for i, (ref, _t) in enumerate(lines)}
        updates = []
        for wid, rs, re_ in conn.execute(
                'SELECT id, ref_start, ref_end FROM window_texts WHERE work = ?',
                (work,)):
            i, j = at.get(rs), at.get(re_)
            if i is None or j is None or j < i:
                kept += 1
                continue
            updates.append(('\n'.join(t for _r, t in lines[i:j + 1]), wid))
        if updates:
            conn.executemany('UPDATE window_texts SET text = ? WHERE id = ?',
                             updates)
            fixed += len(updates)
        conn.commit()
    print(f'  line breaks restored : {fixed:,}')
    print(f'  kept space-joined    : {kept:,} (references not found in the file)')
    if no_file:
        print(f'  works with no .tess  : {no_file:,}'
              f'  e.g. {", ".join(missing_works[:4])}')
    return fixed


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
