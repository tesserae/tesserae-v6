#!/usr/bin/env python3
"""Precompute the Reader gutter's passage (content) density cache, per work.

backend.passage_index.connection_density() answers /api/passages/density, the
violet mark in the Reader's gutter that shows where a work's content is echoed
elsewhere in the corpus. The first time a worker sees a given work it pays for
loading the passage index (mmap'd embeddings, ~1.2 GB of ids/descriptions) AND
a matrix multiply of that work's windows against the whole corpus -- for a
large work this was about 100 seconds and, before the score block was
chunked (backend/passage_index.py _row_scores, 2026-09-19), a single
allocation of 2.5 MB per window: 5 GB for the Punica, 11.6 GB for the
Vulgate, on a production Apache worker that also has to keep answering
other requests. The
answer is cached to disk (cache/passage_density/) precisely so this only has
to happen once per work per index build, but nothing has ever pre-warmed that
cache: it fills lazily, one unlucky reader at a time.

This script walks every work in the passage index and calls the exact same
compute-and-cache path the live endpoint uses, so a first Reader visit to any
work always finds the cache already warm. It also optionally does the same for
backend.lexical_density.line_density(), the red gutter mark, with --lexical.

It deliberately does NOT reimplement any part of the density computation, the
cache file naming, or the cache JSON shape: it imports and calls
backend.passage_index.connection_density() and
backend.lexical_density.line_density() directly, which are the identical
functions backend/blueprints/passages.py calls for
/api/passages/density and /api/lexical-density. Whatever those functions
write to cache/passage_density/ and cache/lexical_density/ is exactly what
this script produces -- same file names (via
passage_index._density_cache_path() / lexical_density._cache_path()), same
JSON.

The work list comes from the loaded passage index itself (the raw `work`
field of every window record, not the language's `works_for_language()`
group), because a multi-part text like vergil.aeneid.part.6 is what the
Reader actually requests, and works_for_language() collapses parts into a
single base id.

Usage:
    # See what would run, no computation, no index load beyond enumeration:
    venv/bin/python scripts/precompute_passage_density.py --dry-run --language la

    # Real run, one language, bounded memory: the index is about 2.5 GB
    # resident and the chunked score block under 0.7 GB, so 8G is ample:
    systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 \\
        venv/bin/python scripts/precompute_passage_density.py --language la

    # Also warm the lexical (red-mark) cache for the same works:
    systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 \\
        venv/bin/python scripts/precompute_passage_density.py --language la --lexical

Run ONE language at a time, one job at a time, per the standing memory rules
in CLAUDE.md -- never all five languages in one uncapped process.
"""
import argparse
import logging
import os
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import lexical_density  # noqa: E402
from backend import passage_index  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('precompute_passage_density')

# The five languages the Reader currently opens with a connection gutter.
# Persian/Urdu/Hebrew's other scripture forms are not wired to the gutter yet,
# so they are left out here rather than guessed at; add them to this tuple
# when they are.
ALL_LANGUAGES = ('la', 'grc', 'en', 'cop', 'he')

DENSITY_SCALE = 'fine'  # matches the endpoint's default when no ?scale= is given


def discover_works(languages=None):
    """{language: [work, ...]} for every raw `work` id in the loaded passage
    index, restricted to `languages` if given.

    Uses passage_index._ensure_loaded() and the loaded _records directly --
    the same load the endpoint does lazily on its first request -- rather than
    passage_index.works_for_language(), which collapses a multi-part work
    (vergil.aeneid.part.1 .. .12) down to one base id. The Reader requests
    density by the exact per-part filename, so that is the granularity this
    script has to precompute at.

    A record with no `work` or no `language` is skipped: that is what "skip
    works with no windows in the passage index" means here in practice --
    there is no such thing as a work in this list that has no windows, since
    the list itself IS drawn from the windows.
    """
    passage_index._ensure_loaded()
    if not passage_index._state.get('ok'):
        raise RuntimeError(passage_index._state.get('error')
                           or 'passage index unavailable')
    wanted = set(languages) if languages else None
    by_lang = {}
    for r in passage_index._records or []:
        lang = r.get('language')
        work = r.get('work')
        if not lang or not work:
            continue
        if wanted is not None and lang not in wanted:
            continue
        by_lang.setdefault(lang, set()).add(work)
    return {lang: sorted(works) for lang, works in by_lang.items()}


def density_is_cached(work, scale=DENSITY_SCALE):
    return os.path.exists(passage_index._density_cache_path(work, scale))


def lexical_is_cached(work, language):
    return os.path.exists(lexical_density._cache_path(work, language))


def process_density(work, force, scale=DENSITY_SCALE):
    """Warm cache/passage_density/ for one work, via passage_index.connection_density.

    Returns 'skipped_cached', 'computed', or 'failed'. Never raises: a
    per-work failure is logged and the caller moves on to the next work.
    """
    cache_path = passage_index._density_cache_path(work, scale)
    cached = os.path.exists(cache_path)
    if cached and not force:
        return 'skipped_cached'
    if cached and force:
        # connection_density() has no force parameter of its own: it always
        # serves a cache hit. Removing the stale file first is what makes
        # --force actually recompute, through the identical write path
        # connection_density() already uses.
        try:
            os.remove(cache_path)
        except OSError as e:
            logger.warning('could not remove stale density cache for %s: %s',
                           work, e)
    try:
        passage_index.connection_density(work, scale=scale)
        return 'computed'
    except Exception:                                            # noqa: BLE001
        logger.exception('density computation failed for work=%s scale=%s',
                         work, scale)
        return 'failed'


def process_lexical(work, language, force):
    """Warm cache/lexical_density/ for one work, via lexical_density.line_density.

    Returns 'skipped_cached', 'computed', or 'failed'.
    """
    cached = lexical_is_cached(work, language)
    if cached and not force:
        return 'skipped_cached'
    try:
        # use_cache=False on a forced run skips the (stale-but-still-hit) read
        # and always recomputes; line_density() unconditionally rewrites its
        # cache file with the fresh result either way.
        lexical_density.line_density(work, language=language, use_cache=not force)
        return 'computed'
    except Exception:                                            # noqa: BLE001
        logger.exception('lexical density computation failed for work=%s language=%s',
                         work, language)
        return 'failed'


def _peak_rss_mb():
    # ru_maxrss is KB on Linux, a monotonic high-water mark for the whole
    # process -- exactly "peak RSS so far".
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def build_parser():
    parser = argparse.ArgumentParser(
        description='Precompute the Reader gutter\'s passage density cache '
                    '(and optionally lexical density) for every work in the '
                    'passage index.')
    parser.add_argument('--language', choices=list(ALL_LANGUAGES) + ['all'],
                        default='all',
                        help='Language to precompute (default: all).')
    parser.add_argument('--only-missing', action='store_true', default=True,
                        help='Skip a work whose cache file already exists '
                             '(default behavior; pass --force to override).')
    parser.add_argument('--force', action='store_true', default=False,
                        help='Recompute and overwrite even if already cached.')
    parser.add_argument('--limit', type=int, default=None,
                        help='Process at most N works, for testing.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        help='List what would be computed; compute nothing.')
    parser.add_argument('--lexical', action='store_true', default=False,
                        help='Also precompute lexical (red-mark) density for '
                             'the same works.')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    force = args.force
    languages = list(ALL_LANGUAGES) if args.language == 'all' else [args.language]

    logger.info('Discovering works for language(s): %s', ', '.join(languages))
    t0 = time.time()
    by_lang = discover_works(languages)
    targets = [(lang, work) for lang in languages for work in by_lang.get(lang, [])]
    if args.limit is not None:
        targets = targets[:args.limit]
    logger.info('Discovered %d work(s) to consider in %.1fs (peak RSS %.1f MB)',
               len(targets), time.time() - t0, _peak_rss_mb())

    if args.dry_run:
        for lang, work in targets:
            cached = density_is_cached(work)
            print(f'{lang}\t{work}\t{"cached" if cached else "missing"}')
        print(f'{len(targets)} work(s) would be processed '
              f'(dry run, no computation performed)')
        return 0

    done = skipped = failed = 0
    lex_done = lex_skipped = lex_failed = 0
    for i, (lang, work) in enumerate(targets, 1):
        t_start = time.time()
        status = process_density(work, force)
        logger.info('[%d/%d] density %s (%s): %s (%.2fs, peak RSS %.1f MB)',
                   i, len(targets), work, lang, status,
                   time.time() - t_start, _peak_rss_mb())
        if status == 'skipped_cached':
            skipped += 1
        elif status == 'failed':
            failed += 1
        else:
            done += 1

        if args.lexical:
            t_start = time.time()
            lstatus = process_lexical(work, lang, force)
            logger.info('[%d/%d] lexical %s (%s): %s (%.2fs, peak RSS %.1f MB)',
                       i, len(targets), work, lang, lstatus,
                       time.time() - t_start, _peak_rss_mb())
            if lstatus == 'skipped_cached':
                lex_skipped += 1
            elif lstatus == 'failed':
                lex_failed += 1
            else:
                lex_done += 1

    logger.info('Density summary: %d computed, %d skipped (cached), %d failed, '
               '%d total', done, skipped, failed, len(targets))
    if args.lexical:
        logger.info('Lexical summary: %d computed, %d skipped (cached), %d failed, '
                   '%d total', lex_done, lex_skipped, lex_failed, len(targets))
    return 1 if (failed or (args.lexical and lex_failed)) else 0


if __name__ == '__main__':
    sys.exit(main())
