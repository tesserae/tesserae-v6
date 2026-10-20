"""The link table from a place to the corpus names that are Latin adjectives of it (People & Places, 2026-10-20).

data/entity_index/place_adjectives.json (built by scripts/entities/build_place_adjectives.py) maps a place's
entity_id to the entity_ids of corpus names such as Rusellanum, Tusculanum and Formianum, which the store keeps
apart from the Pleiades place. The place's page lists them under their own heading. The ids are entity_ids,
never the numeric eid, because the eid changes at a store rebuild. A missing file, an unreadable file, an
id the store does not hold: each gives an empty list, never an error.

File shape:
    {"version": 1, "places": {"pl:423108": {"label": "Tusculum", "adjectives": [
        {"entity_id": "nm:tusku", "label": "Tusculanum",
         "exclude_lines": [{"work": "cicero.de_fato", "key": "cic. fat. 4|tusculanae"}]}]}}}
An exclude_lines entry names one line group (the work, and the line reference with the form key joined by a
bar, as entity_extras.LINE_GROUP_SQL builds it) that the page leaves out, such as a book title.
"""
import json
import os
import threading

PATH = os.environ.get('TESSERAE_PLACE_ADJECTIVES') or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'entity_index', 'place_adjectives.json')

_lock = threading.Lock()
_cache = {}


def _load():
    path = os.environ.get('TESSERAE_PLACE_ADJECTIVES') or PATH
    try:
        st = os.stat(path)
    except OSError:
        return {}
    key = (path, st.st_mtime_ns, st.st_size)
    with _lock:
        hit = _cache.get('t')
        if hit and hit[0] == key:
            return hit[1]
    try:
        with open(path, encoding='utf-8') as f:
            places = json.load(f).get('places') or {}
        if not isinstance(places, dict):
            places = {}
    except (OSError, ValueError, AttributeError):
        places = {}
    with _lock:
        _cache['t'] = (key, places)
    return places


def adjectives_of(place_id):
    """[{entity_id, label, exclude_lines}] for a place entity_id, [] when it has none."""
    out = []
    for a in (_load().get(place_id) or {}).get('adjectives') or []:
        if isinstance(a, dict) and a.get('entity_id'):
            out.append({'entity_id': a['entity_id'], 'label': a.get('label'),
                        'exclude_lines': [x for x in a.get('exclude_lines') or []
                                          if isinstance(x, dict) and x.get('work') and x.get('key')]})
    return out


def exclusions(place_id, adjective_id):
    """The [(work, key)] line groups the place's page leaves out of this adjective entity."""
    for a in adjectives_of(place_id):
        if a['entity_id'] == adjective_id:
            return [(x['work'], x['key']) for x in a['exclude_lines']]
    return []
