"""Arabic roots for the dictionary channel (2026-09-05, poetics roadmap step 5).

A Qur'anic near-quotation keeps the root and changes the form (yastaghfirun /
istaghfara / al-ghafur / maghfira all on gh-f-r). The lemma channel sees
different dictionary forms and misses them (0 of 32 documented Burda
near-quotations in the top 100). This module gives each word its root
through NLTK's ISRI stemmer, and builds, for a search pair, a lookup from
each lemma to the other lemmas of the same root so the same-language
dictionary channel can treat them as equivalents. ISRI is a light, rule-based
root extractor with known slips (al-sa'a -> s-'-h); a morphological analyzer
(CAMeL Tools) would do better and can replace it behind the same function.
"""
import os
from collections import defaultdict
from functools import lru_cache

_stemmer = None
_TABLE = None
_TABLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'arabic_roots.json')


def _table():
    """Roots from CAMeL Tools' morphological analyzer for the corpus vocabulary
    (scripts/build_arabic_root_table.py -> data/arabic_roots.json), or {}."""
    global _TABLE
    if _TABLE is None:
        try:
            import json
            _TABLE = json.load(open(_TABLE_PATH, encoding='utf-8'))
        except Exception:
            _TABLE = {}
    return _TABLE


def _isri():
    global _stemmer
    if _stemmer is None:
        from nltk.stem.isri import ISRIStemmer
        _stemmer = ISRIStemmer()
    return _stemmer


@lru_cache(maxsize=200000)
def arabic_root(word):
    """The root of a normalized Arabic word, or '' when none is found."""
    if not word:
        return ''
    from backend.arabic.processor import normalize_arabic
    t = _table()
    r = t.get(word) or t.get(normalize_arabic(word))
    if r:
        return r
    w = normalize_arabic(word)
    try:
        r = _isri().stem(w)
    except Exception:  # pragma: no cover
        return ''
    return r if 2 <= len(r) <= 4 else ''


def build_root_lookup(units_a, units_b, stopwords=frozenset()):
    """{lemma: set of OTHER lemmas sharing its root} over both sides' lemmas."""
    by_root = defaultdict(set)
    for units in (units_a, units_b):
        for u in units:
            for lem in u.get('lemmas', []) or []:
                if not lem or lem in stopwords or len(lem) < 3:
                    continue
                r = arabic_root(lem)
                if r:
                    by_root[r].add(lem)
    lookup = {}
    for r, lems in by_root.items():
        if len(lems) < 2:
            continue
        for l in lems:
            lookup[l] = lems - {l}
    return lookup


_ROOT_FREQ = None


def root_frequencies():
    """{root: corpus token count} aggregated from the Arabic frequency cache
    through the root table, and the total, for root-level rarity: a rare
    FORM of a common root (yastaghfirun of gh-f-r) must not look rare."""
    global _ROOT_FREQ
    if _ROOT_FREQ is None:
        counts = defaultdict(int); total = 0
        try:
            import json
            path = os.path.join(os.path.dirname(_TABLE_PATH), '..', 'cache', 'frequencies', 'ar.json')
            d = json.load(open(os.path.normpath(path), encoding='utf-8'))
            for form, n in (d.get('frequencies') or {}).items():
                total += n
                r = arabic_root(form)
                if r:
                    counts[r] += n
        except Exception:
            pass
        _ROOT_FREQ = (dict(counts), total)
    return _ROOT_FREQ
