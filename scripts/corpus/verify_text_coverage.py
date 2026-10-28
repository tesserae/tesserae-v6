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
  sources   backend/text_sources.json has an entry (Sources page credits)
  genres    data/text_genres.csv has the file (browser era, meter, genre)
  blurb     data/text_descriptions.json[<lang>][<base>] (About this text)
  dates     backend/author_dates.json[<lang>][<author>] (optional, reported as '-')
  transl    data/translations/<lang>__<base>.json (optional; parts use the whole work's)
  syntax    la, grc, cop: data/inverted_index/syntax_<language>.db table texts has the exact file name
            (the syntax channel looks it up by that name); '-' for other languages
  names     data/entity_index/entities.sqlite table windows has the work (People & Places);
            exempt when the work has no passage windows or is too short for one
  wnames    data/passage_index/window_names.db window_names has rows for the work's windows
            (Similar Passages names); same exemption
  descfts   data/passage_index/desc_fts.sqlite has a row for every window of the work
            (Theme Search word index); same exemption
  reuse     la, grc, en, fa, ur: cache/reuse_pairs/<language>.db table line_counts has the work
            (a part is covered by its whole work, the way backend/reuse_table.py resolves it)
  meter     OPTIONAL, Latin verse only (text_genres.csv meter not prose/unknown): a line of the
            file scans, from the MQDQ table or the automatic scanner; reported, never fails the run
  label     OPTIONAL: the author the site shows is the credit row's author, and the displayed
            title is not a bare fragment of a longer file name; 'check: ...' says what to read

The procedure these columns serve: docs/DATA_OPERATIONS.md, "Adding a text: the standard procedure".

Usage:
  python scripts/corpus/verify_text_coverage.py --root /var/www/tesseraev6_flask --language la curtius_rufus.historiae_alexandri_magni
  python scripts/corpus/verify_text_coverage.py --root /var/www/tesseraev6_flask --language la --all [--json out.json]
Exit status 1 when any required store is missing for any text checked.
"""
import argparse, csv, glob, json, os, re, sqlite3, sys
import numpy as np

MIN_WINDOW_LINES = 10
SYNTAX_DB = {'la': 'syntax_latin.db', 'grc': 'syntax_greek.db', 'cop': 'syntax_coptic.db'}
REUSE_LANGS = ('la', 'grc', 'en', 'fa', 'ur')
VERSE_METERS = ('hexameter', 'elegiac', 'lyric', 'dramatic', 'mixed')
REQUIRED = ['text', 'lemmas', 'index', 'bigrams', 'vectors', 'windows', 'described', 'winvec', 'connmap', 'sources', 'browser', 'genres', 'blurb',
            'syntax', 'names', 'wnames', 'descfts', 'reuse']
# freq: the app recomputes a stale frequency table on the first search that needs it,
# so a stale table is reported but is not a gap.
OPTIONAL = ['freq', 'dates', 'transl', 'meter', 'label']


def count_lines(path):
    pat = re.compile(r'<([^>]+)>')
    return sum(1 for l in open(path, encoding='utf-8', errors='replace') if l.startswith('<') and pat.match(l))


def window_flags(base, whole, is_part, n_lines, part_lines, win_counts, desc_counts, vec_counts):
    """The windows, described and winvec columns for one file.

    part_lines maps each part's base name to its line count (empty for a part or a work without parts).
    A file under MIN_WINDOW_LINES makes no window at all and is exempt. A whole work with parts is
    covered when every part that is long enough has windows; a short part is exempt the same way a
    short whole file is (hermas.pastor parts 6 and 20 have 2 and 3 lines).
    """
    r = {}
    if n_lines < MIN_WINDOW_LINES:
        # too short to make a passage window at all (a one-line epigram, a hypothesis)
        r['windows'] = r['described'] = r['winvec'] = True
    elif part_lines and win_counts.get(base, 0) > 0:
        # the whole work carries windows; very short parts cannot have their own
        r['windows'] = r['described'] = r['winvec'] = True
    elif part_lines:
        parts = [p for p, n in part_lines.items() if n >= MIN_WINDOW_LINES]
        r['windows'] = all(win_counts.get(p, 0) > 0 for p in parts)
        r['described'] = r['windows'] and all(desc_counts.get(p, 0) >= win_counts.get(p, 0) for p in parts)
        r['winvec'] = r['windows'] and all(vec_counts.get(p, 0) >= win_counts.get(p, 0) for p in parts)
    else:
        nw = win_counts.get(base, 0)
        r['windows'] = nw > 0 or (is_part and win_counts.get(whole, 0) > 0)
        r['described'] = (desc_counts.get(base, 0) >= nw) if nw else r['windows']
        r['winvec'] = (vec_counts.get(base, 0) >= nw) if nw else r['windows']
    return r


def _ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def syntax_files(root, lang):
    """File names in the grammar-parse database for the language, or None when the language has none."""
    name = SYNTAX_DB.get(lang)
    if not name:
        return None
    path = os.path.join(root, 'data', 'inverted_index', name)
    if not os.path.exists(path):
        return set()
    c = _ro(path)
    try:
        return {r[0] for r in c.execute('select filename from texts')}
    finally:
        c.close()


def entity_work_counts(root):
    """work -> number of windows in the People & Places store."""
    path = os.path.join(root, 'data', 'entity_index', 'entities.sqlite')
    if not os.path.exists(path):
        return {}
    c = _ro(path)
    try:
        return dict(c.execute('select work, count(*) from windows group by work'))
    finally:
        c.close()


def window_name_works(root):
    """Works with rows in window_names.db (Similar Passages names); ids look like <work>:<kind>:<n>."""
    path = os.path.join(root, 'data', 'passage_index', 'window_names.db')
    if not os.path.exists(path):
        return {}
    c = _ro(path)
    try:
        out = {}
        for (wid,) in c.execute('select distinct id from window_names'):
            w = wid.split(':', 1)[0]
            out[w] = out.get(w, 0) + 1
        return out
    finally:
        c.close()


def desc_fts_counts(root):
    """work -> rows in the Theme Search word index (desc_fts.sqlite); ids look like <work>:<kind>:<n>."""
    path = os.path.join(root, 'data', 'passage_index', 'desc_fts.sqlite')
    if not os.path.exists(path):
        return {}
    c = _ro(path)
    try:
        out = {}
        for (wid,) in c.execute('select c0 from desc_content'):
            w = wid.split(':', 1)[0]
            out[w] = out.get(w, 0) + 1
        return out
    finally:
        c.close()


def reuse_works(root, lang):
    """Works in the reuse table for the language, or None when the language has no table."""
    if lang not in REUSE_LANGS:
        return None
    path = os.path.join(root, 'cache', 'reuse_pairs', f'{lang}.db')
    if not os.path.exists(path):
        return set()
    c = _ro(path)
    try:
        return {r[0] for r in c.execute('select distinct work from line_counts')}
    finally:
        c.close()


def store_flag(base, whole, is_part, n_lines, part_lines, win_counts, have, full=False):
    """Whether a per-window store covers the work. Not applicable (True) when the work has no
    passage windows or is too short for one; the windows column reports a missing window set.
    have maps work -> rows. With full, the rows must reach the window count (descfts)."""
    def ok(w):
        n = have.get(w, 0)
        return n >= win_counts.get(w, 0) if full else n > 0
    if n_lines < MIN_WINDOW_LINES:
        return True
    if part_lines and win_counts.get(base, 0) > 0:
        return ok(base)
    if part_lines:
        parts = [p for p, n in part_lines.items() if n >= MIN_WINDOW_LINES and win_counts.get(p, 0) > 0]
        return all(ok(p) for p in parts)
    if win_counts.get(base, 0) > 0:
        return ok(base)
    if is_part and win_counts.get(whole, 0) > 0:
        return ok(whole)
    return True


def work_level_flag(whole, win_counts, have):
    """For stores that list only windows WITH names (People & Places, window names):
    a poem or chapter that names nobody is absent and that is not a gap. The build
    reached the work when any window of the work, whole file or any part, is listed.
    A work with windows and no listed window at all is reported missing (a real gap,
    or a rare work that names nobody, which a person confirms)."""
    prefix = whole + '.part.'
    def total(counts):
        return counts.get(whole, 0) + sum(n for w, n in counts.items() if w.startswith(prefix))
    if total(win_counts) == 0:
        return True
    return total(have) > 0


def reuse_flag(base, whole, is_part, reuse):
    """The table keys a part on its whole work when a whole file exists (backend/reuse_table.py)."""
    if reuse is None:
        return '-'
    return base in reuse or whole in reuse


def first_lines(path, n=5):
    """Up to n (tag, text) pairs from a .tess file."""
    out = []
    for l in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'<([^>]+)>\s*(.*)', l)
        if m and m.group(2).strip():
            out.append((m.group(1).strip(), m.group(2).strip()))
            if len(out) >= n:
                break
    return out


def meter_flag(path, genre_row):
    """Latin verse only: True when a line scans, 'no scansion' when none of the first lines does,
    '-' for prose or an unknown meter."""
    meter = (genre_row or {}).get('meter', '')
    if meter not in VERSE_METERS:
        return '-'
    try:
        from backend.metrical_scanner import lookup_mqdq_scansion, scan_latin_verse, detect_meter_type
    except Exception as e:
        return f'scanner unavailable: {e}'[:40]
    for tag, text in first_lines(path, 8):
        if lookup_mqdq_scansion(tag):
            return True
        res = scan_latin_verse(text, detect_meter_type(os.path.basename(path)))
        if res and res.get('pattern'):
            return True
    return 'no scansion'


def label_flag(fn, meta, src_rows):
    """Compare what the site shows with the credit rows and the file name. True or 'check: ...'.
    meta is the site's entry for the file (may be empty); src_rows is a list of (author, work)."""
    if not meta:
        return 'no-api'
    ma = (meta.get('author') or '').strip().casefold()
    mw = (meta.get('work') or meta.get('title') or '').strip()
    notes = []
    base = fn[:-5] if fn.endswith('.tess') else fn
    segs = base.split('.part.')[0].split('.')
    words = [w for w in re.split(r'[_.]', '.'.join(segs[1:])) if w]
    shown = mw.split(',')[0].strip().casefold()
    shown_words = [w for w in re.split(r'[\s_]+', shown) if w]
    # a credit row for the same work under a different author
    same_work = [sa for sa, sw in src_rows if shown and (sw == shown or sw.startswith(shown) or shown.startswith(sw)) and sw]
    if same_work and ma and ma not in same_work and not any(sa == ma for sa, _ in src_rows):
        notes.append(f'author shown {ma!r}, credit row {same_work[0]!r}')
    # a bare fragment of the file name
    if len(words) >= 2 and shown_words and len(shown_words) < len(words) and len(shown_words) == 1 \
            and shown_words[0] in [w.casefold() for w in words]:
        notes.append(f'title {mw!r} is one word of {"_".join(words)!r}')
    return True if not notes else 'check: ' + '; '.join(notes)


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
    sources = json.load(open('backend/text_sources.json')) if os.path.exists('backend/text_sources.json') else []
    sources = sources if isinstance(sources, list) else sources.get('entries', [])
    src_keys = {(e.get('author', '').strip().casefold(), e.get('work', '').strip().casefold()) for e in sources}
    blurbs = (json.load(open('data/text_descriptions.json')).get(lang) or {}) if os.path.exists('data/text_descriptions.json') else {}
    dates = (json.load(open('backend/author_dates.json')).get(lang) or {}) if os.path.exists('backend/author_dates.json') else {}

    syn_files = syntax_files(root, lang)
    ent_counts = entity_work_counts(root)
    wn_counts = window_name_works(root)
    fts_counts = desc_fts_counts(root)
    reuse = reuse_works(root, lang)
    src_rows = [(sa, sw) for sa, sw in src_keys]

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
        part_lines = {pf[:-5]: count_lines(f'texts/{lang}/{pf}') for pf in parts_of_whole}
        r.update(window_flags(base, whole, is_part, n_lines, part_lines, win_counts, desc_counts, vec_counts))
        # a text too short for passage windows cannot appear in the connection map
        r['connmap'] = True if (is_part or n_lines < MIN_WINDOW_LINES) else (whole in conn_works)
        g = genres.get(fn) or genres.get(whole + '.tess')
        r['genres'] = (g is not None) if lang == 'la' else True     # genre table is Latin-only
        m = api_meta.get(fn) or api_meta.get(whole + '.tess') or {}
        # no metadata from the site: report the column as unknown, never as ok
        r['browser'] = (bool(m) and bool(m.get('era')) and m.get('era') != 'Unknown' and bool(m.get('text_type'))) if api_meta else 'no-api'
        ma, mw = (m.get('author') or '').strip().casefold(), (m.get('work') or m.get('title') or '').strip().casefold()
        r['sources'] = (ma, mw) in src_keys or any(sa == ma and (sw.startswith(mw) or mw.startswith(sw)) for sa, sw in src_keys if ma and mw and sw)
        # a part file whose name has no work segment gets the work 'Unknown'; the author's one row covers it
        if not r['sources'] and ma and mw == 'unknown':
            r['sources'] = sum(1 for sa, _ in src_keys if sa == ma) == 1
        r['blurb'] = (base in blurbs) or (whole in blurbs)
        r['dates'] = whole.split('.')[0] in dates
        r['transl'] = os.path.exists(f'data/translations/{lang}__{base}.json') or os.path.exists(f'data/translations/{lang}__{whole}.json')
        r['syntax'] = '-' if syn_files is None else (fn in syn_files)
        sf = lambda have, full=False: store_flag(base, whole, is_part, n_lines, part_lines, win_counts, have, full)
        r['names'] = work_level_flag(whole, win_counts, ent_counts)
        r['wnames'] = work_level_flag(whole, win_counts, wn_counts)
        r['descfts'] = sf(fts_counts, True)
        r['reuse'] = reuse_flag(base, whole, is_part, reuse)
        r['meter'] = meter_flag(path, g) if lang == 'la' else '-'
        r['label'] = label_flag(fn, m, src_rows)
        r['text'] = r.pop('text_ok'); r['file'] = fn
        missing = [k for k in REQUIRED if r.get(k) is not True and r.get(k) != '-']
        r['missing'] = missing; any_missing |= bool(missing)
        rows.append(r)

    cols = REQUIRED + OPTIONAL
    w = max(len(r['file']) for r in rows)
    print(f"{'text':<{w}}  lines  " + ' '.join(f'{c[:7]:<7}' for c in cols))
    for r in rows:
        def mark(k):
            v = r.get(k)
            if k in ('meter', 'label'):
                return 'ok' if v is True else ('-' if v == '-' else ('CHECK' if isinstance(v, str) else '-'))
            if k in OPTIONAL: return 'ok' if v is True else '-'
            return 'ok' if v is True else ('MISSING' if v is False else str(v)[:7])
        print(f"{r['file']:<{w}}  {r['lines']:>5}  " + ' '.join(f'{mark(c):<7}' for c in cols))
    tot = len(rows); miss = sum(1 for r in rows if r['missing'])
    per = {c: sum(1 for r in rows if r.get(c) is not True and r.get(c) != '-') for c in REQUIRED}
    opt = {c: sum(1 for r in rows if isinstance(r.get(c), str) and r.get(c) not in ('-', 'no-api')) for c in ('meter', 'label')}
    print(f"\n{tot} texts checked; {miss} with something missing; missing per store: " + ', '.join(f'{c} {n}' for c, n in per.items() if n))
    print('optional columns to read (not failures): ' + ', '.join(f'{c} {n}' for c, n in opt.items() if n))
    for r in rows:
        if isinstance(r.get('label'), str) and r['label'].startswith('check'):
            print(f"  label {r['file']}: {r['label']}")
    if a.json:
        json.dump(rows, open(a.json, 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if any_missing else 0)


if __name__ == '__main__':
    main()
