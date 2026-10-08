"""Build a fast lookup index from data/abbreviations.json for the citation
extractor: normalized abbreviation/title string -> candidate Tesserae works.
"""
import json
import re
from collections import defaultdict

_WS_RE = re.compile(r"\s+")
_DOT_RE = re.compile(r"\.")


def normalize_abbr(s):
    """Fold an abbreviation or title string down to a matchable key: lowercase,
    drop periods, collapse whitespace. 'Verg. Aen.' -> 'verg aen'; 'OT' ->
    'ot'; 'Aeneid' -> 'aeneid'."""
    s = s.lower()
    s = _DOT_RE.sub("", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


class AbbrevIndex:
    def __init__(self, abbreviations_path="data/abbreviations.json"):
        with open(abbreviations_path) as f:
            data = json.load(f)["works"]
        self.works_by_base_id = {w["base_id"]: w for w in data}

        # key -> list of (base_id, priority, source_string)
        # priority: lower number = more specific/reliable, used to break ties
        #   0 = native tesserae tag prefix (e.g. 'verg. aen.') -- ground truth
        #   1 = combined "Author. Work." hucit abbreviation
        #   2 = single work abbreviation (hucit or perseus-catalog)
        #   3 = full work title (least specific: prose often just says "the Aeneid")
        #   4 = single author abbreviation alone (very ambiguous, lowest priority)
        self.index = defaultdict(list)
        self.min_tokens = {}  # key -> token count (for greedy longest-match)

        for w in data:
            base_id = w["base_id"]
            if w.get("native_abbreviation"):
                self._add(w["native_abbreviation"], base_id, 0)
            for a in w.get("abbreviations", []):
                # combined author+work abbreviations contain a space and both
                # sides look abbreviation-shaped; treat plain single-word
                # entries as work-level (priority 2)
                self._add(a, base_id, 1 if " " in a else 2)
            for t in w.get("work_titles", []):
                self._add(t, base_id, 3)
            for aa in w.get("author_abbreviations", []):
                self._add(aa, base_id, 4)

        # collapse duplicate (key, base_id) keeping best (lowest) priority
        for key, entries in self.index.items():
            best = {}
            for base_id, prio, src in entries:
                if base_id not in best or prio < best[base_id][0]:
                    best[base_id] = (prio, src)
            self.index[key] = [(bid, prio, src) for bid, (prio, src) in best.items()]
            self.min_tokens[key] = len(key.split())

        self.max_tokens = max((len(k.split()) for k in self.index), default=1)

    def _add(self, raw, base_id, priority):
        key = normalize_abbr(raw)
        if not key:
            return
        self.index[key].append((base_id, priority, raw))

    def lookup(self, key):
        return self.index.get(key)

    def work_locus_range(self, base_id):
        """Returns (has_base_file, native tesserae_work_id or None, parts list)"""
        w = self.works_by_base_id.get(base_id)
        return w
