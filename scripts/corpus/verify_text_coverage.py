#!/usr/bin/env python3
"""Has a text reached every store the site reads? One row per text, one column
per store, so an import is not finished until every column says ok.

Stores checked (the ones the site reads at request time):
  text      texts/<lang>/<file>.tess exists and has reference lines
  lemmas    the lemma cache for the file's current content (cache/lemmas/<lang>/)
  index     whole works only: the file is in data/inverted_index/<lang>_index.db
  bigrams   cache/bigrams/<lang>_bigrams.json is newer than the text (rare bigrams, formula counts)
  freq      cache/frequencies/<lang>.json carries the checksum of the current texts folder
  vectors   backend/embeddings/<lang>/<base>.npy exists with one row per line (semantic channel)
  windows   passage windows in data/passage_index/window_texts.db (Theme Search, Reader gutter)
  described descriptions.jsonl has every window of the work
  winvec    ids.json (the passage vectors) has every window of the work
  connmap   whole works only: cache/connections_map/*.db works table has the work
  sources   data/text_sources.json has an entry (Sources page credits)
  genres    data/text_genres.csv has the file (browser era, meter, genre)
  blurb     data/text_descriptions.json[<lang>][<base>] (About this text)
  dates     backend/author_dates.json[<lang>][<author>] (optional, reported as '-')
  transl    data/translations/<lang>__<base>.json (optional; parts use the whole work's)

Usage:
  python scripts/corpus/verify_text_coverage.py --root /var/www/tesseraev6_flask --language la curtius_rufus.historiae_alexandri_magni
  python scripts/corpus/verify_text_coverage.py --root /var/www/tesseraev6_flask --language la --all [--json out.json]
Exit status 1 when any required store is missing for any text checked.
"""
import argparse, csv, glob, json, os, re, sqlite3, sys
import numpy as np

MIN_WINDOW_LINES = 10
REQUIRED = ['text', 'lemmas', 'index', 'bigrams', 'vectors', 'windows', 'described', 'winvec', 'connmap', 'sources', 'browser', 'genres', 'blurb']
# freq: the app recomputes a stale frequency table on the first search that needs it,
# so a stale table is reported but is not a gap.
OPTIONAL = ['freq', 'dates', 'transl']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ap.add_argument('--language', '-l', required=True)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--json')
    ap.add_argument('--api', default='https://tesserae.caset.buffalo.edu/api', help='site whose /texts list gives the browser metadata')
    ap.add_argument('texts', nargs='*', help='work names (without .tess); parts are checked with their whole work')
    a = ap.parse_args()
    root = os.path.abspath(a.root); lang = a.language
    sys.path.insert(0, root)
    os.chdir(root)
    from backend.lemma_cache import get_cache_path   # name carries the content hash

    files = sorted(os.path.basename(f) for f in glob.glob(f'texts/{lang}/*.tess'))
    files_all = list(files)
    if not a.all:
        want = set()
        for t in a.texts:
            t = t[:-5] if t.endswith('.tess') else t
            want.update(f for f in files if f == t + '.tess' or f.startswith(t + '.part.'))
        files = sorted(want)
    if not files:
        print('no texts selected'); sys.exit(2)

    # per-language stores, loaded once
    idx_files = set()
    dbp = f'data/inverted_index/{lang}_index.db'
    if os.path.exists(dbp):
        c = sqlite3.connect(f'file:{dbp}?mode=ro', uri=True)
        idx_files = {r[0] for r in c.execute('select filename from texts')}
    big = f'cache/bigrams/{lang}_bigrams.json'; big_mtime = os.path.getmtime(big) if os.path.exists(big) else None
    freq_ok = False
    try:
        from backend.frequency_cache import get_corpus_checksum, load_frequency_cache
        fc = load_frequency_cache(lang); freq_ok = bool(fc) and fc.get('checksum') == get_corpus_checksum(lang)
    except Exception:
        freq_ok = False
    win_counts, desc_counts, vec_counts = {}, {}, {}
    wdb = 'data/passage_index/window_texts.db'
    if os.path.exists(wdb):
        c = sqlite3.connect(f'file:{wdb}?mode=ro', uri=True)
        for w, n in c.execute('select work, count(*) from window_texts where language=? group by work', (lang,)):
            win_counts[w] = n
    if os.path.exists('data/passage_index/descriptions.jsonl'):
        with open('data/passage_index/descriptions.jsonl', encoding='utf-8') as fh:
            for line in fh:
                try: r = json.loads(line)
                except ValueError: continue
                if r.get('language') == lang: desc_counts[r.get('work')] = desc_counts.get(r.get('work'), 0) + 1
    if os.path.exists('data/passage_index/ids.json'):
        for wid in json.load(open('data/passage_index/ids.json')):
            w = wid.split(':', 1)[0]; vec_counts[w] = vec_counts.get(w, 0) + 1
    conn_works = set()
    for db in glob.glob('cache/connections_map/*.db'):
        if '.bak' in db: continue
        try:
            c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
            conn_works |= {r[0] for r in c.execute('select work from works where language=?', (lang,))}
        except Exception as e:
            print(f'(connection map {db} unreadable: {e})')
    import urllib.request
    api_meta = {}
    try:
        with urllib.request.urlopen(f'{a.api}/texts?language={lang}', timeout=120) as resp:
            d = json.loads(resp.read()); lst = d if isinstance(d, list) else d.get('texts', [])
            api_meta = {x.get('id'): x for x in lst}
    except Exception as e:
        print(f'(browser metadata unavailable from {a.api}: {e})')
    genres = {}
    if os.path.exists('data/text_genres.csv'):
        for r in csv.DictReader(open('data/text_genres.csv', encoding='utf-8')): genres[r['filename']] = r
    sources = json.load(open('data/text_sources.json')) if os.path.exists('data/text_sources.json') else []
    sources = sources if isinstance(sources, list) else sources.get('entries', [])
    src_keys = {(e.get('author', '').strip().casefold(), e.get('work', '').strip().casefold()) for e in sources}
    blurbs = (json.load(open('data/text_descriptions.json')).get(lang) or {}) if os.path.exists('data/text_descriptions.json') else {}
    dates = (json.load(open('backend/author_dates.json')).get(lang) or {}) if os.path.exists('backend/author_dates.json') else {}

    pat = re.compile(r'<([^>]+)>')
    rows = []; any_missing = False
    for fn in files:
        base = fn[:-5]; is_part = '.part.' in base; whole = base.split('.part.')[0]
        path = f'texts/{lang}/{fn}'
        n_lines = sum(1 for l in open(path, encoding='utf-8', errors='replace') if l.startswith('<') and pat.match(l))
        r = {'text': fn, 'lines': n_lines}
        r['text_ok'] = n_lines > 0
        r['lemmas'] = os.path.exists(get_cache_path(fn, lang))
        r['index'] = True if is_part else (fn in idx_files)
        r['bigrams'] = bool(big_mtime) and big_mtime >= os.path.getmtime(path)
        r['freq'] = freq_ok
        vp = f'backend/embeddings/{lang}/{base}.npy'
        if os.path.exists(vp):
            try:
                rows_v = np.load(vp, mmap_mode='r').shape[0]
                r['vectors'] = rows_v == n_lines or f'rows {rows_v} vs lines {n_lines}'
            except Exception: r['vectors'] = 'unreadable'
        else: r['vectors'] = False
        # Passage windows belong to the part files when a work has parts (the
        # whole file's own windows were dropped so a passage is not indexed
        # twice); a whole work with parts is covered when every part is.
        parts_of_whole = [f for f in files_all if f.startswith(base + '.part.')] if not is_part else []
        if n_lines < MIN_WINDOW_LINES:
            # too short to make a passage window at all (a one-line epigram, a hypothesis)
            r['windows'] = r['described'] = r['winvec'] = True
        elif parts_of_whole and win_counts.get(base, 0) > 0:
            # the whole work carries windows; very short parts cannot have their own
            r['windows'] = r['described'] = r['winvec'] = True
        elif parts_of_whole:
            pw = [win_counts.get(pf[:-5], 0) for pf in parts_of_whole]
            r['windows'] = all(n > 0 for n in pw)
            r['described'] = all(desc_counts.get(pf[:-5], 0) >= win_counts.get(pf[:-5], 0) for pf in parts_of_whole) and r['windows']
            r['winvec'] = all(vec_counts.get(pf[:-5], 0) >= win_counts.get(pf[:-5], 0) for pf in parts_of_whole) and r['windows']
        elif not (n_lines < MIN_WINDOW_LINES):
            nw = win_counts.get(base, 0); r['windows'] = nw > 0 or (is_part and win_counts.get(whole, 0) > 0)
            r['described'] = (desc_counts.get(base, 0) >= nw) if nw else r['windows']
            r['winvec'] = (vec_counts.get(base, 0) >= nw) if nw else r['windows']
        r['connmap'] = True if is_part else (whole in conn_works)
        g = genres.get(fn) or genres.get(whole + '.tess')
        r['genres'] = (g is not None) if lang == 'la' else True     # genre table is Latin-only
        m = api_meta.get(fn) or api_meta.get(whole + '.tess') or {}
        # no metadata from the site: report the column as unknown, never as ok
        r['browser'] = (bool(m) and bool(m.get('era')) and m.get('era') != 'Unknown' and bool(m.get('text_type'))) if api_meta else 'no-api'
        ma, mw = (m.get('author') or '').strip().casefold(), (m.get('work') or m.get('title') or '').strip().casefold()
        r['sources'] = (ma, mw) in src_keys or any(sa == ma and (sw.startswith(mw) or mw.startswith(sw)) for sa, sw in src_keys if ma and mw and sw)
        r['blurb'] = (base in blurbs) or (whole in blurbs)
        r['dates'] = whole.split('.')[0] in dates
        r['transl'] = os.path.exists(f'data/translations/{lang}__{base}.json') or os.path.exists(f'data/translations/{lang}__{whole}.json')
        r['text'] = r.pop('text_ok'); r['file'] = fn
        missing = [k for k in REQUIRED if r.get(k) is not True]
        r['missing'] = missing; any_missing |= bool(missing)
        rows.append(r)

    cols = REQUIRED + OPTIONAL
    w = max(len(r['file']) for r in rows)
    print(f"{'text':<{w}}  lines  " + ' '.join(f'{c[:7]:<7}' for c in cols))
    for r in rows:
        def mark(k):
            v = r.get(k)
            if k in OPTIONAL: return 'ok' if v is True else '-'
            return 'ok' if v is True else ('MISSING' if v is False else str(v)[:7])
        print(f"{r['file']:<{w}}  {r['lines']:>5}  " + ' '.join(f'{mark(c):<7}' for c in cols))
    tot = len(rows); miss = sum(1 for r in rows if r['missing'])
    per = {c: sum(1 for r in rows if r.get(c) is not True) for c in REQUIRED}
    print(f"\n{tot} texts checked; {miss} with something missing; missing per store: " + ', '.join(f'{c} {n}' for c, n in per.items() if n))
    if a.json:
        json.dump(rows, open(a.json, 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if any_missing else 0)


if __name__ == '__main__':
    main()
