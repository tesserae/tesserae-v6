"""Formula detection: how many works in the corpus repeat a result's words.

Biblical Hebrew, Latin epic, and other formulaic corpora reuse set phrases
("and she conceived and bore a son and called his name", "if your servant
has found favour in your eyes"). In a two-text comparison these recur as
parallels; one reader calls them clutter, another calls them the object of
study. `formula_count` answers "how many works share this result's shared
wording", read from the same per-language bigram and lemma document-frequency
tables the rare-bigram and rare-word searches already build, so a result can
be hidden or isolated on that count without a new corpus pass per search.

Scope: a row's matched_words all belong to one language (this is the
same-language fusion/lemma/exact/etc. search), so annotation is skipped for
cross-lingual rows (the two sides' lemma forms belong to different bigram
tables, which this does not attempt to reconcile).
"""
import os
import sqlite3

from backend.bigram_frequency import get_bigram_cache, make_bigram_key
from backend.logging_config import get_logger

logger = get_logger('formula_filter')

_INDEX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'inverted_index')

# lemma -> number of works containing it, loaded whole the first time a row
# in that language needs it (one SELECT over the index's own lemma_doc_freq
# table, the same precomputed table the rare-word channel reads — tens of
# thousands of rows, a few MB). False means "no index/table for this
# language", cached so a language without an index isn't retried every row.
_lemma_doc_freq_cache = {}


def _load_lemma_doc_freq(language):
    """Return {lemma: work_count} for `language`, or None if unavailable.

    Cached in memory for the life of the process (mirrors how
    backend.bigram_frequency caches its per-language table).
    """
    if language in _lemma_doc_freq_cache:
        return _lemma_doc_freq_cache[language]
    table = None
    db_path = os.path.join(_INDEX_DIR, f'{language}_index.db')
    if os.path.exists(db_path):
        conn = None
        try:
            conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
            rows = conn.execute('SELECT lemma, df FROM lemma_doc_freq').fetchall()
            table = {lemma: df for lemma, df in rows}
        except sqlite3.OperationalError:
            # Index predates the lemma_doc_freq table (not every language's
            # index has been rebuilt since it was added); word-basis formula
            # counts are simply unavailable for it.
            table = None
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"Failed to load lemma_doc_freq for {language}: {e}")
            table = None
        finally:
            if conn is not None:
                conn.close()
    _lemma_doc_freq_cache[language] = table
    return table


def formula_count_for_row(matched_words, language, bigram_table=None, lemma_table=None):
    """How many works in the corpus carry this result's shared words together.

    Picks the two matched lemmas with the lowest corpus frequency (the
    scorer's own `frequency` field on each matched-word entry — the two most
    informative shared words, not just any two) and looks up their bigram's
    per-work count in the cached bigram table. With only one real matched
    lemma, falls back to that lemma's own work count.

    bigram_table/lemma_table let a caller (tests) inject a fake table
    directly; a normal call leaves them None and this loads the real
    per-language tables (`cache/bigrams/<language>_bigrams.json`'s
    `doc_frequencies`, and the index's `lemma_doc_freq` table), each read
    from an in-memory cache loaded once per language.

    Returns (formula_count, formula_basis):
      - formula_basis is "bigram" (2+ shared lemmas) or "word" (exactly 1).
      - formula_count is None when the relevant table has no entry for the
        pair/lemma, or no table exists for the language — never a guess.
      - (None, None) when there are no real matched lemmas at all (nothing
        to look up).
    """
    if not matched_words:
        return None, None

    lemmas = []
    for mw in matched_words:
        lemma = mw.get('lemma') if isinstance(mw, dict) else None
        if not lemma:
            continue
        freq = mw.get('frequency')
        if freq is None:
            freq = 1
        lemmas.append((lemma, freq))

    if not lemmas:
        return None, None

    # The two most informative (rarest) shared lemmas by corpus token
    # frequency; a tie keeps matched_words' original order (stable sort).
    lemmas.sort(key=lambda lf: lf[1])

    if len(lemmas) >= 2:
        lemma_a, lemma_b = lemmas[0][0], lemmas[1][0]
        if bigram_table is None:
            cache = get_bigram_cache(language)
            bigram_table = cache.get('doc_frequencies') if cache else None
        if bigram_table is None:
            return None, 'bigram'
        key = make_bigram_key(lemma_a, lemma_b)
        return bigram_table.get(key), 'bigram'

    # Single shared lemma: the lemma's own work count.
    if lemma_table is None:
        lemma_table = _load_lemma_doc_freq(language)
    if lemma_table is None:
        return None, 'word'
    return lemma_table.get(lemmas[0][0]), 'word'


def annotate_formula_counts(results, language):
    """Attach formula_count/formula_basis to each result row, in place.

    No-op (rows left untouched) when language is falsy: cross-lingual rows
    mix two languages' lemma forms, and the per-language tables this reads
    do not apply across them.
    """
    if not language:
        return results
    for row in results:
        count, basis = formula_count_for_row(row.get('matched_words'), language)
        row['formula_count'] = count
        row['formula_basis'] = basis
    return results


def apply_formula_filter(results, formula_max=None, formula_only=False):
    """Hide or isolate rows by formula_count, per the request's settings.

    formula_max: hide rows whose formula_count is ABOVE this number. None
    (the default — no value sent) disables filtering entirely and returns
    `results` unchanged. A row with no formula_count (the tables had nothing
    for its pair/lemma) is never hidden by this mode: there is nothing to
    judge it a formula on.

    formula_only: keep only rows whose formula_count is AT OR ABOVE
    formula_max (requires formula_max; ignored otherwise). A row with no
    formula_count is excluded here, since "formula" cannot be affirmed
    without a count.

    Returns (kept_results, hidden_count).
    """
    if formula_max is None:
        return results, 0
    try:
        formula_max = int(formula_max)
    except (TypeError, ValueError):
        return results, 0

    kept = []
    hidden = 0
    for row in results:
        count = row.get('formula_count')
        if formula_only:
            keep = count is not None and count >= formula_max
        else:
            keep = count is None or count <= formula_max
        if keep:
            kept.append(row)
        else:
            hidden += 1
    return kept, hidden
