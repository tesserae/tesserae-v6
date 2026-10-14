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
    python scripts/build_window_texts.py --work ID --db COPY.db            # plan
    python scripts/build_window_texts.py --work ID --db COPY.db --apply    # rebuild one work

--work rebuilds only that work's rows (its windows and its addressable lines)
in the window_texts.db named by --db and touches no other row. Run it on a COPY
and swap the copy into place; the database is rewritten inside one transaction.

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


def build_lines(conn, only=None):
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
    works = only if only is not None else [r[0] for r in conn.execute(
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


def restore_line_breaks(conn, only=None):
    """Replace each window's space-joined text with its real verse lines.

    Works work by work so only one .tess is held at a time. A window whose
    references cannot be found keeps the space-joined text it already has, and
    those are COUNTED and reported: a silent fallback here would print poetry as
    prose for one corner of the corpus and nobody would know which.
    """
    files = _tess_index()
    print(f'\n  {len(files):,} .tess files across {len(TEXT_TREES)} trees')
    works = only if only is not None else [r[0] for r in conn.execute(
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


def _numkey(ref, prefix):
    """Trailing dotted numbers of a reference as a tuple, or None."""
    tail = ref[len(prefix):].lstrip('.') if ref.startswith(prefix) else ref.split()[-1]
    try:
        return tuple(int(x) for x in tail.split('.'))
    except ValueError:
        return None


def clamp_empty_windows(conn, work):
    """Give a window whose own references are not in the file the lines it can have.

    A window cut when a laisse had a line that the file no longer has (the
    Chanson de Roland: laisse 25 ends at 25.6, a window starts at 25.7) names a
    reference that is absent. Its start is moved up to the first line at or
    after it and its end down to the last line at or before it, in numeric
    order; a window that then holds no line stays empty. Each is reported.
    """
    path = _tess_index().get(work)
    if not path:
        return
    lines = _lines_of(path)
    prefix = work
    keyed = [(_numkey(r, prefix), t) for r, t in lines]
    rows = conn.execute("SELECT id, ref_start, ref_end FROM window_texts "
                        "WHERE work = ? AND (text IS NULL OR text = '')", (work,)).fetchall()
    for wid, rs, re_ in rows:
        a, b = _numkey(rs, prefix), _numkey(re_, prefix)
        if a is None or b is None:
            continue
        got = [t for k, t in keyed if k is not None and a <= k <= b]
        if got:
            conn.execute('UPDATE window_texts SET text = ? WHERE id = ?', ('\n'.join(got), wid))
            print(f'  {wid}: references {rs}..{re_} not all in the file; '
                  f'stored the {len(got)} lines that are')


def rebuild_work(db, work, descriptions, apply=False):
    """Rebuild one work's window_texts rows and lines rows in `db`, nothing else.

    Windows come from the window files first (first file wins, as in build())
    and then from the index's own descriptions.jsonl for any id of this work
    that no window file carries (the case of the vernacular batch, whose window
    files are gone). A window gets its text by slicing the work's .tess file
    between its ref_start and ref_end, exactly as restore_line_breaks() does;
    one whose references are not in the file is counted and left out rather
    than stored empty. All inside one transaction: nothing is written without
    --apply, and a failure rolls back.
    """
    conn = sqlite3.connect(db)
    old = {r[0]: r[1:] for r in conn.execute(
        'SELECT id, language, ref_start, ref_end, text FROM window_texts WHERE work = ?',
        (work,))}
    old_lines = conn.execute('SELECT COUNT(*) FROM lines WHERE work = ?', (work,)).fetchone()[0]
    wins = {}
    for path in WINDOW_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as fh:
            for w in json.load(fh):
                if w.get('work') == work and w.get('id') and w.get('text'):
                    wins.setdefault(w['id'], (w.get('language'), w.get('ref_start'),
                                              w.get('ref_end'), w['text']))
    from_files = len(wins)
    if not descriptions or not os.path.exists(descriptions):
        raise SystemExit(f'descriptions.jsonl not found at {descriptions!r}: pass '
                         '--descriptions (a window with no file text is found there)')
    if True:
        needle = '"work": ' + json.dumps(work)
        with open(descriptions, encoding='utf-8') as fh:
            for line in fh:
                if needle not in line:
                    continue
                r = json.loads(line)
                if r.get('work') == work and r['id'] not in wins:
                    wins[r['id']] = (r.get('language'), r.get('ref_start'),
                                     r.get('ref_end'), '')
    print(f'{work}: {len(old)} window rows and {old_lines} line rows now; '
          f'{len(wins)} windows to store ({from_files} from window files, '
          f'{len(wins) - from_files} from descriptions)')
    if not apply:
        print('(dry run; pass --apply to write)')
        conn.close()
        return 0
    conn.execute('BEGIN')
    conn.execute('DELETE FROM window_texts WHERE work = ?', (work,))
    conn.execute('DELETE FROM lines WHERE work = ?', (work,))
    conn.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)',
                     [(i, v[0], work, v[1], v[2], v[3]) for i, v in wins.items()])
    restore_line_breaks(conn, only=[work])
    build_lines(conn, only=[work])
    clamp_empty_windows(conn, work)
    empty = [r[0] for r in conn.execute(
        "SELECT id FROM window_texts WHERE work = ? AND (text IS NULL OR text = '')", (work,))]
    if empty:
        conn.execute("DELETE FROM window_texts WHERE work = ? AND (text IS NULL OR text = '')",
                     (work,))
        print(f'  {len(empty)} windows have no stored text and were left out, '
              f'e.g. {empty[:3]}')
    conn.commit()
    n = conn.execute('SELECT COUNT(*) FROM window_texts WHERE work = ?', (work,)).fetchone()[0]
    changed = sum(1 for i, v in old.items()
                  if conn.execute('SELECT text FROM window_texts WHERE id = ?', (i,)).fetchone()
                  not in (None, (v[3],)))
    print(f'  now {n} window rows; {changed} rows that existed before changed their text')
    conn.close()
    return 0 if not empty else 1


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
    ap.add_argument('--work', help='rebuild only this work id in the database '
                    'given by --db (a copy; see the module docstring)')
    ap.add_argument('--db', default=DB, help='window_texts.db to change with --work')
    ap.add_argument('--descriptions', default=os.path.join(INDEX, 'descriptions.jsonl'),
                    help='descriptions.jsonl naming the work\'s window ids')
    ap.add_argument('--apply', action='store_true', help='write (with --work)')
    args = ap.parse_args()
    if args.work:
        return rebuild_work(args.db, args.work, args.descriptions, args.apply)
    if args.check:
        return check()
    build()
    return check()


if __name__ == '__main__':
    sys.exit(main())
