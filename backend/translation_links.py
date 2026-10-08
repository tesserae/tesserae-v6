"""External translator links for a passage, additive alongside any aligned
translation text the Reader's Translation tab already shows.

Some translators' work carries no stated licence, so their English cannot be
copied into Tesserae the way the aligned-translation files in
data/translations/ are (see backend/translations.py). What the site CAN do
is point the Reader at the translator's own page for that verse. The first
case is Frances W. Pritchett's "A Desertful of Roses" (her Ghalib diwan
translation and commentary, franpritchett.com/00ghalib/): the site states no
licence, so a link stands in where copied text cannot.

Each file in data/translations/links/ is built offline (see
scripts/build_ghalib_pritchett_links.py for the Ghalib case) and maps one
work's refs to the translator's verse-page URL, plus enough of the matching
evidence to audit a given link later. This module only reads that table; it
never fetches the translator's site at request time.
"""
import json
import os
import threading

from backend.logging_config import get_logger
from backend.work_names import work_id

logger = get_logger('translation_links')

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'translations', 'links')

_lock = threading.Lock()
_index = None  # work_id -> {ref: [{translator, site_title, source_url, url}, ...]}


def _load_all():
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        idx = {}
        if os.path.isdir(_DIR):
            for fn in sorted(os.listdir(_DIR)):
                if not fn.endswith('.json'):
                    continue
                path = os.path.join(_DIR, fn)
                try:
                    with open(path, encoding='utf-8') as fh:
                        data = json.load(fh)
                except (OSError, ValueError) as e:
                    logger.warning('[TRANSLATION_LINKS] could not read %s: %s', fn, e)
                    continue
                work = data.get('work')
                links = data.get('links')
                if not work or not isinstance(links, dict):
                    logger.warning('[TRANSLATION_LINKS] %s has no work/links; skipped', fn)
                    continue
                translator = data.get('translator')
                site_title = data.get('site_title')
                source_url = data.get('source_url')
                by_ref = idx.setdefault(work_id(work), {})
                for ref, rec in links.items():
                    url = (rec or {}).get('url')
                    if not url:
                        continue
                    by_ref.setdefault(ref, []).append({
                        'translator': translator,
                        'site_title': site_title,
                        'source_url': source_url,
                        'url': url,
                    })
        _index = idx
        total = sum(len(v) for v in idx.values())
        logger.info('[TRANSLATION_LINKS] %d work(s), %d linked refs', len(idx), total)
        return _index


def available_works():
    return sorted(_load_all().keys())


def for_refs(work, refs):
    """External links for a selection: [{source, source_url, url}, ...],
    deduplicated by URL in first-seen order. Empty list when the work has
    no link table, or none of the refs are covered -- never raises."""
    by_ref = _load_all().get(work_id(work))
    if not by_ref:
        return []
    seen_urls = set()
    out = []
    for ref in refs or []:
        entries = by_ref.get(ref)
        if entries is None and isinstance(ref, str):
            entries = by_ref.get(ref.strip())
        for entry in entries or []:
            if entry['url'] in seen_urls:
                continue
            seen_urls.add(entry['url'])
            out.append(entry)
    return out
