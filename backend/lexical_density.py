"""Per-line lexical connection density, for the Reader's red gutter marks.

The scene index answers "what else is ABOUT this?"; this answers the older
question, "what else USES these words?". For each line of a work it counts how
many other works in the corpus share one of its distinctive lemmata, which is
the same signal the rare-word channel scores, reduced to one number per line.

Speed comes from the precomputed `lemma_doc_freq` table already in each index
(the table that took rare-word search from 34s to 0.02s). A line's density is
read straight off it: no corpus scan, no per-line queries against postings.
Results are cached per work, since a work's lines do not change between builds.
"""
import json
import math
import os
import sqlite3
import threading

from backend.logging_config import get_logger

logger = get_logger('lexical_density')

_INDEX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'inverted_index')
_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'cache', 'lexical_density')

# A lemma in more than this share of the corpus says nothing about a line: it is
# vocabulary, not a connection. Matches the spirit of the rare-word channel,
# which scores rarity rather than mere co-occurrence.
COMMON_LEMMA_SHARE = 0.10
# Lemmata rarer than this carry the signal a reader cares about.
_lock = threading.Lock()


def _index_path(language):
    return os.path.join(_INDEX_DIR, f'{language}_index.db')


def _cache_path(work, language):
    safe = work.replace('/', '_')
    return os.path.join(_CACHE_DIR, f'{language}__{safe}.json')


def line_density(work, language='la', use_cache=True):
    """Per-line counts of how distinctive a line's vocabulary is corpus-wide.

    Returns {'work', 'language', 'peak', 'lines': [{ref, connections, density}]}.
    `connections` is the number of OTHER works sharing this line's rarest lemma,
    and `density` normalises that against the work's own busiest line, so the
    gutter reads as "busy for this text" rather than against an absolute scale.
    """
    cached = _read_cache(work, language) if use_cache else None
    if cached:
        return cached

    db = _index_path(language)
    if not os.path.exists(db):
        return {'error': f'no index for language {language}', 'lines': []}

    try:
        conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        cur = conn.cursor()
        row = cur.execute(
            'SELECT text_id FROM texts WHERE filename = ? OR filename = ?',
            (work, f'{work}.tess')).fetchone()
        if not row:
            return {'error': f'work {work} not in the {language} index', 'lines': []}
        text_id = row[0]
        total_texts = cur.execute('SELECT COUNT(*) FROM texts').fetchone()[0] or 1
        common_cut = max(2, int(total_texts * COMMON_LEMMA_SHARE))

        # One pass over this work's lines, one lookup per distinct lemma.
        lines = cur.execute(
            'SELECT ref, lemmas FROM lines WHERE text_id = ? ORDER BY rowid',
            (text_id,)).fetchall()
        freq = {}

        def doc_freq(lemma):
            if lemma not in freq:
                r = cur.execute(
                    'SELECT df FROM lemma_doc_freq WHERE lemma = ?',
                    (lemma,)).fetchone()
                freq[lemma] = r[0] if r else 0
            return freq[lemma]

        out = []
        for ref, lemmas_json in lines:
            try:
                lemmas = json.loads(lemmas_json) if lemmas_json else []
            except ValueError:
                lemmas = []
            # Score the WHOLE line, not just its rarest word. Taking the single
            # rarest lemma made the measure a ceiling: every line holding any
            # reasonably rare word tied at the maximum while ordinary lines read
            # as empty. Instead each distinctive lemma contributes its own
            # rarity (rarer counts for more), so a line dense with uncommon
            # vocabulary outranks one that happens to contain a single odd word.
            score = 0.0
            connections = 0
            for lem in set(lemmas):
                if not lem:
                    continue
                df = doc_freq(lem)
                if df <= 1 or df > common_cut:
                    continue
                score += math.log(common_cut / df)
                connections = max(connections, df - 1)
            out.append({'ref': ref, 'score': round(score, 3),
                        'connections': connections})
        conn.close()
    except sqlite3.Error as e:
        logger.error('[LEXDENSITY] %s', e)
        return {'error': str(e), 'lines': []}

    # Normalise against a high percentile rather than the single busiest line,
    # so one outlier cannot flatten the rest of the gutter to nothing.
    scores = sorted(l['score'] for l in out)
    if scores:
        idx = int(len(scores) * 0.95)
        peak = scores[min(idx, len(scores) - 1)] or 1.0
    else:
        peak = 1.0
    for l in out:
        l['density'] = round(min(1.0, l['score'] / peak), 3)
    result = {'work': work, 'language': language, 'peak': peak, 'lines': out}
    _write_cache(work, language, result)
    return result


def _read_cache(work, language):
    p = _cache_path(work, language)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_cache(work, language, data):
    try:
        with _lock:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            with open(_cache_path(work, language), 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
    except OSError as e:
        logger.warning('[LEXDENSITY] could not cache %s: %s', work, e)
