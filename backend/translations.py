"""Aligned public-domain English translations, for the Reader's Translation tab.

Each work has a file mapping our exact .tess reference tags to translation
units, built offline from the Perseus canonical TEI (see the acquisition report
in research/motif_feature/DEVELOPMENT_LOG_2026-08.md). Alignment is not always
one line to one sentence: verse is often rendered as prose in blocks, so several
source lines can share a translation unit. Each file records how coarse it is
and how confidently it was aligned, and both travel with the response so the
Reader can be honest about what it is showing.

Coverage is partial by nature. About 30 percent of Greek and 18 percent of Latin
have an aligned public-domain translation, so "no translation for this passage"
is a normal answer rather than an error.
"""
import json
import os
import threading

from backend.logging_config import get_logger

logger = get_logger('translations')

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'translations')

_lock = threading.Lock()
_cache = {}          # work key -> parsed file (or None when absent)
_index = None        # tess work name -> filename


def _build_index():
    """Map our work names to translation files, once."""
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        idx = {}
        if os.path.isdir(_DIR):
            for fn in os.listdir(_DIR):
                if not fn.endswith('.json') or fn == 'manifest.json':
                    continue
                # files are named "<lang>__<work>.json"
                stem = fn[:-5]
                work = stem.split('__', 1)[1] if '__' in stem else stem
                idx[work] = fn
        _index = idx
        logger.info('[TRANSLATIONS] %d aligned works available', len(idx))
        return _index


def _norm_work(work):
    # Callers hand us a work name either bare (vergil.aeneid) or with the language
    # directory the corpus files sit in (la/vergil.aeneid). Both mean the same work.
    return (work or '').replace('.tess', '').split('/')[-1]


def _load(work):
    """Parsed translation file for a work, or None. Cached per work."""
    key = _norm_work(work)
    if key in _cache:
        return _cache[key]
    idx = _build_index()
    fn = idx.get(key)
    if not fn:
        # A part file (vergil.aeneid.part.6) may be covered by its whole work.
        base = key.split('.part.')[0]
        fn = idx.get(base)
    data = None
    if fn:
        try:
            with open(os.path.join(_DIR, fn), encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, ValueError) as e:
            logger.warning('[TRANSLATIONS] could not read %s: %s', fn, e)
    _cache[key] = data
    return data


def available_works():
    return sorted(_build_index().keys())


def for_passage(work, refs):
    """English for a selection.

    Args:
        work: our work name, with or without .tess
        refs: the reference tags of the selected lines, in order

    Returns a dict with the translation text (deduplicated, since consecutive
    source lines often share one unit), the translator and licence, and an
    honest note when the alignment is coarse.
    """
    data = _load(work)
    if not data:
        return {'available': False,
                'reason': 'No aligned public-domain translation for this work.',
                'work': _norm_work(work)}

    ref_to_unit = data.get('ref_to_unit') or {}
    units = data.get('units') or []
    seen = []
    matched = 0
    for ref in refs or []:
        i = ref_to_unit.get(ref)
        if i is None:
            i = ref_to_unit.get(str(ref).strip())
        if i is None or i >= len(units):
            continue
        matched += 1
        if i not in seen:
            seen.append(i)
    if not seen:
        return {'available': False,
                'reason': 'This work has a translation, but not for the selected lines.',
                'work': _norm_work(work)}

    src = (data.get('sources') or [{}])[0]
    per_unit = data.get('mean_source_lines_per_translation_unit') or 1
    coarse = per_unit and per_unit > 3
    # Some translations carry no subdivision below the book. Lucretius' smallest
    # unit averages over a thousand source lines, so what comes back for one line
    # is the whole book. That is still worth reading, but a reader must not take
    # it for a rendering of the lines selected, so it is said outright rather
    # than left to a footnote.
    block = per_unit and per_unit > 40
    if block:
        note = (f'The smallest unit this translation offers runs to about '
                f'{round(per_unit)} lines, so what follows is the whole passage '
                f'containing your selection, not a translation of those lines.')
    elif coarse:
        note = ('This translation is aligned in blocks of about '
                f'{round(per_unit)} lines, so it covers the selection rather than '
                'matching it line by line.')
    else:
        note = None
    return {
        'available': True,
        'work': _norm_work(work),
        'text': '\n\n'.join(str(units[i]) for i in seen),
        'units': len(seen),
        'lines_matched': matched,
        'translator': src.get('translator'),
        'year': src.get('year'),
        'license': data.get('license'),
        'attribution': data.get('attribution'),
        'alignment_confidence': data.get('alignment_confidence'),
        'approximate': bool(coarse),
        'block_only': bool(block),
        'block_lines': round(per_unit) if coarse else None,
        'note': note,
    }
