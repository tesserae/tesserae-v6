#!/usr/bin/env python3
"""Build the corpus-wide connections map cache.

For every Latin, Greek, English, Coptic and Hebrew window of the passage
index at the fine scale, finds its top 10 nearest windows in OTHER works by
cosine similarity over the index's own description embeddings (the same
vectors Theme Search and Similar Passages already use), excluding the same
work, its part files, and other versions of the same scripture passage
(backend/scripture_id.py). Kept edges are written at the WINDOW level, plus
aggregates by work, author, century and genre, into a SQLite cache keyed by
the passage index's own fingerprint (backend.passage_index.index_fingerprint),
so a rebuilt index invalidates the cache automatically.

This is the production build for the corpus connections map, following the
research prototype at research/connections_map/ (see REPORT_2026-09-18.md).
That prototype computed aggregates only, from Latin/Greek/English, with no
translation marking and no persistent cache. This version:
  * adds Coptic and Hebrew,
  * keeps the window-level edges (not just aggregates), so a work-pair cell
    can be drilled down to actual passage pairs,
  * marks translation pairs two ways -- a curated list
    (data/translation_pairs.json) and a heuristic (see mark_translations()) --
    so the UI can hide them by default without hiding real allusion,
  * writes to a versioned SQLite cache under cache/, atomically.

Run under a memory cap:
    systemd-run --user --scope -p MemoryMax=10G \\
        venv/bin/python3 scripts/build_connections_map.py

Runtime is dominated by one query-chunk x whole-subset matrix multiply per
1,500-row block (BLAS, all cores); expect on the order of 35-45 minutes for
the current index size and a peak a few GB under the cap. Both are logged
to the meta table and to stdout.
"""
import csv
import glob
import json
import math
import os
import resource
import sqlite3
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import scripture_id                        # noqa: E402
from backend.passage_index import index_fingerprint, BASELINE_MARGIN  # noqa: E402
from backend.utils import format_display_name            # noqa: E402

DATA_DIR = os.path.join(ROOT, 'data', 'passage_index')
CACHE_DIR = os.path.join(ROOT, 'cache', 'connections_map')
TRANSLATION_PAIRS_PATH = os.path.join(ROOT, 'data', 'translation_pairs.json')
ALIGNED_CANDIDATES_PATH = os.path.join(CACHE_DIR, 'aligned_candidates.txt')

LANGUAGES = ('la', 'grc', 'en', 'cop', 'he')
SCALE = 'fine'
TOPK = 10
QUERY_CHUNK_ROWS = 1500   # cap on rows scored per BLAS call (memory control)
TIME_BUDGET_SECONDS = int(os.environ.get('CONN_MAP_TIME_BUDGET', 3 * 3600))
ESTIMATE_ONLY = os.environ.get('CONN_MAP_ESTIMATE_ONLY') == '1'

# Heuristic "aligned translation" thresholds (see mark_translations()).
ALIGNED_COVERAGE = 0.40     # fraction of the smaller work's windows that must link
ALIGNED_SPEARMAN = 0.80     # rank correlation of window position through both works
ALIGNED_PREFILTER_RATIO = 0.20  # cheap necessary-not-sufficient filter before the
                                 # expensive exact distinct-window-count query


def log(msg):
    mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f'[{time.strftime("%H:%M:%S")}] (peak {mem_mb:.0f} MB) {msg}', flush=True)


def norm_work(work):
    w = work or ''
    if '/' in w:
        w = w.rsplit('/', 1)[-1]
    if w.endswith('.tess'):
        w = w[:-5]
    return w.split('.part.')[0]


def year_to_century(year):
    if year is None or year == 0:
        return None
    c = math.ceil(abs(year) / 100.0)
    return -c if year < 0 else c


def century_label(c):
    if c is None:
        return 'unknown'
    n = abs(c)
    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n if n < 20 else n % 10, 'th')
    if n % 100 in (11, 12, 13):
        suffix = 'th'
    era = 'BCE' if c < 0 else 'CE'
    return f'{n}{suffix} c. {era}'


def _spearman(a, b):
    """Spearman rank correlation, no scipy dependency."""
    if len(a) < 3:
        return 0.0
    ra = np.argsort(np.argsort(a, kind='stable')).astype(np.float64)
    rb = np.argsort(np.argsort(b, kind='stable')).astype(np.float64)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else 0.0


def load_metadata():
    author_dates = json.load(open(os.path.join(ROOT, 'backend', 'author_dates.json'), encoding='utf-8'))
    genre_by_work, era_by_work = {}, {}
    with open(os.path.join(ROOT, 'data', 'text_genres.csv'), encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            base = norm_work(row.get('filename', ''))
            if row.get('genre'):
                genre_by_work[base] = row['genre']
            if row.get('era'):
                era_by_work.setdefault(base, row['era'])
    return author_dates, genre_by_work, era_by_work


def load_curated_translation_pairs():
    try:
        data = json.load(open(TRANSLATION_PAIRS_PATH, encoding='utf-8'))
    except (OSError, ValueError) as e:
        log(f'WARNING: could not read {TRANSLATION_PAIRS_PATH}: {e} '
            '-- curated translation flag will be empty')
        return set()
    return {tuple(sorted((p['work_a'], p['work_b']))) for p in data.get('pairs', [])}


def build_scripture_exclusions(records, sub_idx):
    """row -> set of OTHER row-local-indices that are another version of the
    same scripture passage, so the neighbour search can mask them out.

    Grouped by (book, starting chapter) to keep the pairwise overlap check
    (scripture_id.overlaps) cheap: candidates are only ever compared within
    their own book+chapter bucket, not against the whole corpus.
    """
    spans = [None] * len(sub_idx)
    buckets = {}
    for local_i, global_i in enumerate(sub_idx):
        r = records[global_i]
        sp = scripture_id.span(r.get('work'), r.get('ref_start'), r.get('ref_end'))
        if sp is None:
            continue
        spans[local_i] = sp
        key = (sp[0], sp[1][0])
        buckets.setdefault(key, []).append(local_i)

    extra_exclude = {}
    for _, members in buckets.items():
        if len(members) < 2:
            continue
        for a in members:
            sp_a = spans[a]
            group = [b for b in members if b != a and scripture_id.overlaps(sp_a, spans[b])]
            if group:
                extra_exclude[a] = np.array(group, dtype=np.int64)
    return extra_exclude


def main():
    t_start = time.time()
    os.makedirs(CACHE_DIR, exist_ok=True)
    fingerprint = index_fingerprint()
    db_path = os.path.join(CACHE_DIR, f'{fingerprint}.db')
    tmp_path = db_path + '.tmp'
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    log(f'index fingerprint {fingerprint}')
    log(f'building {db_path}')

    author_dates, genre_by_work, era_by_work = load_metadata()
    curated_pairs = load_curated_translation_pairs()
    log(f'{len(curated_pairs)} curated translation pairs loaded')

    log('loading ids.json')
    ids = json.load(open(os.path.join(DATA_DIR, 'ids.json'), encoding='utf-8'))

    log('loading descriptions.jsonl (streaming, keeping only the fields this job needs)')
    by_id = {}
    with open(os.path.join(DATA_DIR, 'descriptions.jsonl'), encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            by_id[r['id']] = {
                'id': r['id'], 'language': r.get('language'), 'work': r.get('work'),
                'scale': r.get('scale'), 'ref_start': r.get('ref_start'),
                'ref_end': r.get('ref_end'),
                'gist': (r.get('desc') or {}).get('gist'),
            }
    records = [by_id.get(i, {'id': i}) for i in ids]
    log(f'{len(records)} records total (embedding-row order)')

    emb = np.load(os.path.join(DATA_DIR, 'embeddings.npy'), mmap_mode='r')
    if emb.shape[0] != len(records):
        raise SystemExit(f'index mismatch: {emb.shape[0]} embeddings vs {len(records)} ids')
    log(f'embeddings.npy shape {emb.shape} dtype {emb.dtype}')

    sub_idx = [i for i, r in enumerate(records)
               if r.get('language') in LANGUAGES and r.get('scale') == SCALE]
    log(f'subset ({",".join(LANGUAGES)}, scale={SCALE}): {len(sub_idx)} windows of {len(records)} total')

    sub_idx = np.array(sub_idx, dtype=np.int64)
    base_works = np.array([norm_work(records[i].get('work')) for i in sub_idx])
    languages = np.array([records[i].get('language') for i in sub_idx])
    window_ids = np.array([records[i]['id'] for i in sub_idx])

    order = np.argsort(base_works, kind='stable')
    sub_idx = sub_idx[order]
    base_works = base_works[order]
    languages = languages[order]
    window_ids = window_ids[order]

    N = len(sub_idx)
    log(f'gathering embedding submatrix into memory (float32): {N} x {emb.shape[1]}')
    t0 = time.time()
    sub_emb = np.asarray(emb[sub_idx], dtype=np.float32)
    log(f'submatrix gathered in {time.time() - t0:.1f}s, {sub_emb.nbytes / 1e9:.2f} GB')

    log('building scripture-duplicate exclusion map')
    t0 = time.time()
    extra_exclude = build_scripture_exclusions(records, sub_idx)
    log(f'{len(extra_exclude)} windows carry a same-passage exclusion set '
        f'({time.time() - t0:.1f}s)')

    uniq_works, first_idx, counts = np.unique(base_works, return_index=True, return_counts=True)
    work_bounds = {}
    for w, s, c in zip(uniq_works, first_idx, counts):
        work_bounds[w] = (int(s), int(s + c))
    n_works = len(uniq_works)
    log(f'{n_works} distinct works in subset')

    work_meta = {}
    for w in uniq_works:
        s, e = work_bounds[w]
        lang = languages[s]
        author_raw = w.split('.', 1)[0]
        info = (author_dates.get(lang, {}).get(author_raw) or {})
        year = info.get('year')
        century = year_to_century(year)
        n_win = e - s
        work_meta[w] = {
            'language': lang,
            'author_key': author_raw,
            'author_display': format_display_name(author_raw),
            'year': year,
            'era_label': info.get('era') or era_by_work.get(w),
            'century': century,
            'century_label': century_label(century) if century is not None else None,
            'genre': genre_by_work.get(w),
            'window_count': int(n_win),
        }

    # ---- SQLite: fresh build, single transaction, indexes added at the end -----
    conn = sqlite3.connect(tmp_path)
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA journal_mode=MEMORY')
    conn.executescript('''
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE works (
            work TEXT PRIMARY KEY, language TEXT, author_key TEXT, author_display TEXT,
            year INTEGER, era_label TEXT, century INTEGER, century_label TEXT,
            genre TEXT, window_count INTEGER, total_links INTEGER, links_per_window REAL
        );
        CREATE TABLE windows (
            id TEXT PRIMARY KEY, work TEXT, language TEXT, ref_start TEXT, ref_end TEXT,
            gist TEXT
        );
        CREATE TABLE edges (
            window_a TEXT, window_b TEXT, score REAL,
            work_a TEXT, work_b TEXT, pos_a INTEGER, pos_b INTEGER
        );
        CREATE TABLE work_pairs (
            work_a TEXT, work_b TEXT, lang_a TEXT, lang_b TEXT,
            count INTEGER, count_notrans INTEGER,
            is_translation_curated INTEGER, is_translation_heuristic INTEGER,
            PRIMARY KEY (work_a, work_b)
        );
        CREATE TABLE author_pairs (
            author_a TEXT, author_b TEXT, lang_a TEXT, lang_b TEXT,
            count INTEGER, count_notrans INTEGER,
            PRIMARY KEY (author_a, author_b, lang_a, lang_b)
        );
        CREATE TABLE century_pairs (
            lang_pair TEXT, century_a INTEGER, century_b INTEGER,
            label_a TEXT, label_b TEXT, count INTEGER, count_notrans INTEGER
        );
        CREATE TABLE genre_pairs (
            genre_a TEXT, genre_b TEXT, count INTEGER, count_notrans INTEGER
        );
    ''')

    conn.executemany(
        'INSERT INTO windows (id, work, language, ref_start, ref_end, gist) VALUES (?,?,?,?,?,?)',
        ((records[gi]['id'], base_works[li], languages[li],
          records[gi].get('ref_start'), records[gi].get('ref_end'),
          records[gi].get('gist'))
         for li, gi in enumerate(sub_idx)))
    conn.commit()
    log(f'{N} window rows written')

    # ---- main pass: chunked matrix multiply, edges written incrementally ------
    total_edges_kept = 0
    total_rows_done = 0
    est_seconds = None
    t_compute_start = time.time()
    insert_buf = []

    row = 0
    while row < N:
        block_end = min(N, row + QUERY_CHUNK_ROWS)
        t_chunk0 = time.time()
        block = sub_emb[row:block_end]
        scores = block @ sub_emb.T
        medians = np.median(scores, axis=1)
        floors = medians + BASELINE_MARGIN

        for r_local in range(block_end - row):
            i = row + r_local
            w = base_works[i]
            s, e = work_bounds[w]
            row_scores = scores[r_local].copy()
            row_scores[s:e] = -np.inf   # same work, incl. part files
            extra = extra_exclude.get(i)
            if extra is not None:
                row_scores[extra] = -np.inf   # other versions of the same scripture passage
            top_idx = np.argpartition(-row_scores, TOPK)[:TOPK] if TOPK < N else np.arange(N)
            top_idx = top_idx[np.argsort(-row_scores[top_idx])]
            floor = floors[r_local]
            keep = top_idx[row_scores[top_idx] >= floor]
            if keep.size == 0:
                continue
            pos_a = i - s
            for j in keep:
                wb = base_works[j]
                sb, _eb = work_bounds[wb]
                insert_buf.append((
                    window_ids[i], window_ids[j], float(row_scores[j]),
                    w, wb, int(pos_a), int(j - sb)
                ))
                total_edges_kept += 1

        if len(insert_buf) >= 200_000:
            conn.executemany(
                'INSERT INTO edges (window_a, window_b, score, work_a, work_b, pos_a, pos_b) '
                'VALUES (?,?,?,?,?,?,?)', insert_buf)
            insert_buf.clear()

        total_rows_done += (block_end - row)
        chunk_time = time.time() - t_chunk0
        if est_seconds is None:
            rows_per_sec = (block_end - row) / chunk_time
            est_seconds = N / rows_per_sec
            log(f'first chunk: {block_end - row} rows in {chunk_time:.1f}s '
                f'({rows_per_sec:.1f} rows/s). Estimated full run: '
                f'{est_seconds / 60:.1f} min for {N} rows.')
            if ESTIMATE_ONLY:
                log('CONN_MAP_ESTIMATE_ONLY=1 set -- stopping after first-chunk estimate.')
                conn.close()
                os.remove(tmp_path)
                return
            if est_seconds > TIME_BUDGET_SECONDS:
                log(f'ESTIMATED RUN TIME {est_seconds/3600:.2f}h EXCEEDS BUDGET. Stopping.')
                conn.close()
                os.remove(tmp_path)
                return
        if total_rows_done % (QUERY_CHUNK_ROWS * 20) < QUERY_CHUNK_ROWS:
            elapsed = time.time() - t_compute_start
            frac = total_rows_done / N
            eta = elapsed / frac - elapsed if frac > 0 else 0
            log(f'progress {total_rows_done}/{N} ({100*frac:.1f}%), '
                f'elapsed {elapsed/60:.1f} min, eta {eta/60:.1f} min, '
                f'edges kept so far {total_edges_kept}')
        row = block_end

    if insert_buf:
        conn.executemany(
            'INSERT INTO edges (window_a, window_b, score, work_a, work_b, pos_a, pos_b) '
            'VALUES (?,?,?,?,?,?,?)', insert_buf)
        insert_buf.clear()
    conn.commit()
    total_compute_time = time.time() - t_compute_start
    log(f'neighbour computation done: {total_edges_kept} kept edges, {total_compute_time/60:.1f} min')

    log('indexing edges')
    conn.executescript('''
        CREATE INDEX idx_edges_work_pair ON edges(work_a, work_b);
        CREATE INDEX idx_edges_window_a ON edges(window_a);
        CREATE INDEX idx_edges_window_b ON edges(window_b);
    ''')
    conn.commit()

    # ---- work_pairs: canonicalized from edges -----------------------------
    log('aggregating work_pairs')
    cur = conn.execute('''
        SELECT CASE WHEN work_a<=work_b THEN work_a ELSE work_b END AS wa,
               CASE WHEN work_a<=work_b THEN work_b ELSE work_a END AS wb,
               COUNT(*) AS c
        FROM edges GROUP BY wa, wb
    ''')
    work_pair_rows = cur.fetchall()
    work_degree = {w: 0 for w in uniq_works}
    for wa, wb, c in work_pair_rows:
        work_degree[wa] = work_degree.get(wa, 0) + c
        work_degree[wb] = work_degree.get(wb, 0) + c

    heuristic_hits = []
    wp_insert = []
    for wa, wb, c in work_pair_rows:
        curated = tuple(sorted((wa, wb))) in curated_pairs
        heuristic = False
        if not curated:
            meta_a, meta_b = work_meta[wa], work_meta[wb]
            if meta_a['language'] != meta_b['language']:
                smaller, larger = (wa, wb) if meta_a['window_count'] <= meta_b['window_count'] else (wb, wa)
                smaller_n = work_meta[smaller]['window_count']
                if smaller_n and c >= ALIGNED_PREFILTER_RATIO * smaller_n:
                    dcur = conn.execute('''
                        SELECT COUNT(DISTINCT w) FROM (
                            SELECT window_a AS w FROM edges WHERE work_a=? AND work_b=?
                            UNION
                            SELECT window_b AS w FROM edges WHERE work_b=? AND work_a=?
                        )
                    ''', (smaller, larger, smaller, larger))
                    distinct_linked = dcur.fetchone()[0]
                    coverage = distinct_linked / smaller_n
                    if coverage >= ALIGNED_COVERAGE:
                        pcur = conn.execute('''
                            SELECT pos_a, pos_b FROM edges WHERE work_a=? AND work_b=?
                            UNION ALL
                            SELECT pos_b, pos_a FROM edges WHERE work_a=? AND work_b=?
                        ''', (smaller, larger, larger, smaller))
                        pos_rows = pcur.fetchall()
                        if len(pos_rows) >= 3:
                            pa = np.array([p[0] for p in pos_rows], dtype=np.float64)
                            pb = np.array([p[1] for p in pos_rows], dtype=np.float64)
                            rho = _spearman(pa, pb)
                            if rho >= ALIGNED_SPEARMAN:
                                heuristic = True
                                heuristic_hits.append((smaller, larger, coverage, rho, c))
        is_trans = curated or heuristic
        wp_insert.append((wa, wb, work_meta[wa]['language'], work_meta[wb]['language'],
                          c, 0 if is_trans else c, int(curated), int(heuristic)))

    conn.executemany('''
        INSERT INTO work_pairs (work_a, work_b, lang_a, lang_b, count, count_notrans,
                                is_translation_curated, is_translation_heuristic)
        VALUES (?,?,?,?,?,?,?,?)
    ''', wp_insert)
    conn.commit()
    log(f'{len(wp_insert)} work pairs, {sum(r[6] for r in wp_insert)} curated translation pairs, '
        f'{sum(r[7] for r in wp_insert)} heuristic-aligned pairs')

    with open(ALIGNED_CANDIDATES_PATH, 'w', encoding='utf-8') as fh:
        fh.write('# Heuristic-aligned work pairs (coverage >= {:.0%}, Spearman >= {:.2f}), '
                  'not already in data/translation_pairs.json.\n'
                 '# smaller_work  larger_work  coverage  spearman  edge_count\n'.format(
                     ALIGNED_COVERAGE, ALIGNED_SPEARMAN))
        for smaller, larger, coverage, rho, c in sorted(heuristic_hits, key=lambda r: -r[2]):
            fh.write(f'{smaller}\t{larger}\t{coverage:.3f}\t{rho:.3f}\t{c}\n')
    log(f'{len(heuristic_hits)} heuristic candidates written to {ALIGNED_CANDIDATES_PATH}')

    # ---- works table --------------------------------------------------------
    works_insert = []
    for w in uniq_works:
        m = work_meta[w]
        deg = work_degree.get(w, 0)
        works_insert.append((w, m['language'], m['author_key'], m['author_display'],
                            m['year'], m['era_label'], m['century'], m['century_label'],
                            m['genre'], m['window_count'], deg,
                            round(deg / m['window_count'], 4) if m['window_count'] else 0))
    conn.executemany('''
        INSERT INTO works (work, language, author_key, author_display, year, era_label,
                           century, century_label, genre, window_count, total_links, links_per_window)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ''', works_insert)
    conn.commit()

    # ---- author_pairs / century_pairs / genre_pairs, derived from work_pairs -
    log('aggregating author/century/genre pairs from work_pairs')
    author_acc = {}
    century_acc = {}
    genre_acc = {}
    for wa, wb, la, lb, c, c_nt, _cur, _heur in wp_insert:
        ma, mb = work_meta[wa], work_meta[wb]
        aa = f"{ma['author_display']} ({la})"
        ab = f"{mb['author_display']} ({lb})"
        a_key = tuple(sorted((aa, ab)))
        akey = (a_key[0], a_key[1], la if a_key[0] == aa else lb, lb if a_key[0] == aa else la)
        prev = author_acc.get(akey, (0, 0))
        author_acc[akey] = (prev[0] + c, prev[1] + c_nt)

        if ma['century'] is not None and mb['century'] is not None:
            lang_key = f'{la}-{lb}' if la <= lb else f'{lb}-{la}'
            pair = tuple(sorted((ma['century'], mb['century'])))
            key = (lang_key, pair[0], pair[1])
            prev = century_acc.get(key, (0, 0))
            century_acc[key] = (prev[0] + c, prev[1] + c_nt)

        if ma['genre'] and mb['genre']:
            gpair = tuple(sorted((ma['genre'], mb['genre'])))
            prev = genre_acc.get(gpair, (0, 0))
            genre_acc[gpair] = (prev[0] + c, prev[1] + c_nt)

    conn.executemany(
        'INSERT INTO author_pairs (author_a, author_b, lang_a, lang_b, count, count_notrans) '
        'VALUES (?,?,?,?,?,?)',
        [(k[0], k[1], k[2], k[3], v[0], v[1]) for k, v in author_acc.items()])
    conn.executemany(
        'INSERT INTO century_pairs (lang_pair, century_a, century_b, label_a, label_b, count, count_notrans) '
        'VALUES (?,?,?,?,?,?,?)',
        [(k[0], k[1], k[2], century_label(k[1]), century_label(k[2]), v[0], v[1])
         for k, v in century_acc.items()])
    conn.executemany(
        'INSERT INTO genre_pairs (genre_a, genre_b, count, count_notrans) VALUES (?,?,?,?)',
        [(k[0], k[1], v[0], v[1]) for k, v in genre_acc.items()])
    conn.commit()
    log(f'{len(author_acc)} author pairs, {len(century_acc)} century pairs, {len(genre_acc)} genre pairs')

    total_runtime = time.time() - t_start
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    meta = {
        'built_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'index_fingerprint': fingerprint,
        'languages': list(LANGUAGES),
        'scale': SCALE,
        'topk': TOPK,
        'baseline_margin': BASELINE_MARGIN,
        'subset_windows': int(N),
        'distinct_works': n_works,
        'edges_kept': total_edges_kept,
        'work_pairs': len(wp_insert),
        'curated_translation_pairs': sum(r[6] for r in wp_insert),
        'heuristic_translation_pairs': sum(r[7] for r in wp_insert),
        'author_pairs': len(author_acc),
        'century_pairs': len(century_acc),
        'genre_pairs': len(genre_acc),
        'compute_seconds': round(total_compute_time, 1),
        'total_runtime_seconds': round(total_runtime, 1),
        'peak_memory_mb': round(peak_mb, 1),
    }
    conn.executemany('INSERT INTO meta (key, value) VALUES (?, ?)',
                     [(k, json.dumps(v)) for k, v in meta.items()])
    conn.commit()
    conn.close()

    os.replace(tmp_path, db_path)   # atomic: a reader never sees a half-built cache
    log(f'wrote {db_path} ({os.path.getsize(db_path)/1e6:.1f} MB)')
    prune_old_caches(db_path)
    log(f'total wall time {total_runtime/60:.1f} min, peak memory {peak_mb/1024:.2f} GB')


def _cache_built_at(path):
    try:
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='built_at'").fetchone()
        finally:
            conn.close()
        return json.loads(row[0]) if row else ''
    except sqlite3.Error:
        return ''


def prune_old_caches(db_path):
    """Keep the cache just built plus exactly one older one, delete the
    rest (NC, 2026-09-19).

    backend.connections_map falls back to the most recently built cache
    present when a corpus edit changes index_fingerprint() before the next
    ~40-minute rebuild catches up (see its _resolve()), so one previous
    generation is worth keeping as that fallback; anything older than that
    is dead weight at tens to hundreds of MB each.
    """
    others = [p for p in glob.glob(os.path.join(CACHE_DIR, '*.db')) if p != db_path]
    if len(others) <= 1:
        return
    others.sort(key=_cache_built_at, reverse=True)   # newest first
    for stale_path in others[1:]:
        try:
            os.remove(stale_path)
            log(f'removed old cache {stale_path}')
        except OSError as e:
            log(f'WARNING: could not remove old cache {stale_path}: {e}')


if __name__ == '__main__':
    main()
