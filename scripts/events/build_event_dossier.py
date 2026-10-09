#!/usr/bin/env python3
"""Event dossier prototype: gather what the component anchors of an event reach.

An event (battle, siege, treaty, campaign) is a composite anchor: a date range, places,
participants and primary passages. This script takes one Wikidata event record (see
fetch_wikidata_events.py) and gathers
  (a) literary passages: Latin and Greek windows whose proper-name index entries match the
      event's names, ranked by how many distinct event names the window contains;
  (b) documents: inscriptions and papyri dated within the event span (plus or minus a margin)
      whose Pleiades place lies within a radius of the event's location;
  (c) scholarship: articles citing the primary passages (data/citation_index/citations.db)
      and commentary entries on them;
  (d) a map list: the event locations and the document findspots.
No UI, no writes into the production data. All data paths are read-only.

Usage:
  build_event_dossier.py --events events.jsonl --labels labels.jsonl --countries countries.jsonl \
      --pleiades pleiades_points.tsv --out OUT_DIR (--qid Q... | --sample sample_events.json)
"""
import argparse
import csv
import json
import math
import os
import re
import sqlite3
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # llm_judge, with python -I
from collections import defaultdict

PROD = os.environ.get("TESSERAE_PROD", "/var/www/tesseraev6_flask")
CROSSWALK = os.path.expanduser("~/tesserae-docs/stage2/crosswalk/trismegistos_to_pleiades.tsv")

# ----------------------------------------------------------------- pure helpers

GR = {'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'e', 'θ': 'th', 'ι': 'i', 'κ': 'k', 'λ': 'l',
      'μ': 'm', 'ν': 'n', 'ξ': 'ks', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't', 'υ': 'u', 'φ': 'f',
      'χ': 'kh', 'ψ': 'ps', 'ω': 'o'}


def _strip(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if not unicodedata.combining(c))


def norm_full(tok):
    """key() of scripts/corpus/build_window_names.py without the [:5] cut: accent-stripped,
    Greek transliterated, a-z only, the same letter substitutions."""
    t = ''.join(GR.get(c, c) for c in _strip(tok).lower())
    t = re.sub(r'[^a-z]', '', t)
    for a, b in (('ph', 'f'), ('th', 't'), ('ch', 'kh'), ('ae', 'ai'), ('oe', 'oi'), ('c', 'k'), ('y', 'u'),
                 ('x', 'ks'), ('j', 'i'), ('v', 'u')):
        t = t.replace(a, b)
    return t


def name_key(tok):
    """The name-index key of scripts/corpus/build_window_names.py (same algorithm, copied so
    this script needs no heavy imports): the normalised form cut to its first 5 letters."""
    t = norm_full(tok)
    return t[:5] if len(t) >= 4 else None


# Inflectional endings of the normalised (transliterated) forms, longest first. 'us' is stripped
# only after a consonant, so that Delius (deli+us) stays a different stem from Delium/Delio/Delii
# (deli), while Varus, Vari and Varum share var-. A final 's' alone is never an ending.
ENDINGS = sorted("orum arum ibus ous ois ais um us os on ou oi ai ae am as an em en es is a e i o u".split(),
                 key=lambda e: (-len(e), e))
MIN_STEM = 3


def stem_form(norm):
    """Strip one inflectional ending (at most 3 letters) if a stem of MIN_STEM letters or more is
    left. Applied to the normalised event name and to the normalised window form alike."""
    for e in ENDINGS:
        if norm.endswith(e) and len(norm) - len(e) >= MIN_STEM:
            st = norm[:-len(e)]
            if e == "us" and st.endswith("i"):
                continue
            return st
    return norm


PRAENOMINA = {name_key(x) for x in """Gaius Gaios Lucius Leukios Marcus Markos Gnaeus Gnaios Publius Poplios Quintus Kointos Titus Titos
Aulus Decimus Sextus Tiberius Tiberios Manius Servius Spurius Appius Caesar Imperator Autokrator""".split()} - {None}
STOP = set("""of the and in on at by for to a an ancient battle siege treaty war wars kingdom empire republic league
city state island islands sea river gulf bay mount mountain mountains region province army fleet campaign
expedition conquest first second third great little upper lower north south east west
bellum bella proelium pugna obsidio foedus regnum res publica
πόλεμος πολεμος μάχη μαχη πολιορκία συνθήκη""".split())


def label_keys(label):
    """Name keys of the capitalised content words of one label (English, Latin or Greek)."""
    keys = set()
    for tok in re.findall(r"[^\W\d_]+", label or "", re.UNICODE):
        if tok.lower() in STOP:
            continue
        k = name_key(tok)
        if k:
            keys.add(k)
    return keys


IUS_EXPANSION = False  # off by default: it did not change the 12-event numbers


def name_stems(norm):
    """Stems an event-name token accepts. The stem after one ending is always accepted. A name in
    -ius (Arminius, Pompeius, Darius) also accepts its oblique forms (Arminii, Pompei, Darium),
    which strip to different stems: it gets the stem minus 'us' and, when long enough, minus
    'ius'. This is applied to the NAME only, so a window form Delius still does not match the
    name Delium (stem deli), while the name Delius accepts Delii and Delio."""
    out = {stem_form(norm)}
    if IUS_EXPANSION and norm.endswith("ius") and len(norm) >= 6:
        out.add(norm[:-2])
        if len(norm) - 3 >= 4:
            out.add(norm[:-3])
    return out


def label_tokens(label):
    """Normalised full tokens of the content words of one label (stop words and praenomina out,
    and at least four letters, as for the keys)."""
    out = set()
    for tok in re.findall(r"[^\W\d_]+", label or "", re.UNICODE):
        if tok.lower() in STOP:
            continue
        k = name_key(tok)
        if k and k not in PRAENOMINA:
            out.add(norm_full(tok))
    return out


def label_variants(names):
    """One key set per label (praenomina dropped: 'Gaius' names a hundred people). Whether every
    key of a variant, or any key of the entity, must be present is decided in literary()."""
    out = []
    for n in names:
        ks = frozenset(label_keys(n) - PRAENOMINA)
        if ks and ks not in out:
            out.append(ks)
    return out


def wikidata_year(iso):
    """Wikidata/SPARQL dates use astronomical numbering (year 0 = 1 BC). Return the historian's
    year: negative for BC (astronomical -423 is 424 BC), positive for AD."""
    m = re.match(r"^(-?)(\d+)-", iso or "")
    if not m:
        return None
    y = int(m.group(2)) * (-1 if m.group(1) else 1)
    return y - 1 if y <= 0 else y


def event_span(rec):
    ys = [wikidata_year(x) for k in ("point_in_time", "start", "end") for x in rec.get(k, [])]
    ys = [y for y in ys if y is not None]
    return (min(ys), max(ys)) if ys else None


def ranges_overlap(a_lo, a_hi, b_lo, b_hi, margin=0):
    """Closed interval overlap with a symmetric margin applied to the event range (a)."""
    return a_lo - margin <= b_hi and a_hi + margin >= b_lo


def parse_point(s):
    """'Point(lon lat)' to (lat, lon)."""
    m = re.match(r"Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)", s or "")
    return (float(m.group(2)), float(m.group(1))) if m else None


def haversine_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def min_distance_km(pt, centres):
    return min(haversine_km(pt, c) for c in centres) if centres else None


def base_work(w):
    return re.sub(r"\.part\..*$", "", w)


def parse_ref(ref):
    """Trailing locus of a reference as a tuple of ints: 'thuc. pele. 4.89.1' -> (4, 89, 1).
    Non-numeric parts ('pr') count as 0. Returns () when there is no dotted tail."""
    if not ref:
        return ()
    tail = ref.strip().split()[-1]
    if not re.fullmatch(r"[0-9A-Za-z]+(\.[0-9A-Za-z]+)*", tail) or not re.search(r"\d", tail):
        return ()
    return tuple(int(p) if p.isdigit() else 0 for p in tail.split("."))


def loci_overlap(lo1, hi1, lo2, hi2):
    """Do two locus ranges overlap? Compared on the shared prefix length, as
    backend/scholarship.py _locus_overlaps does, so a book.chapter range matches a
    book.chapter.section window."""
    if not (lo1 and hi1 and lo2 and hi2):
        return False
    n = min(len(lo1), len(hi1), len(lo2), len(hi2))
    return lo1[:n] <= hi2[:n] and hi1[:n] >= lo2[:n]


ROLE_WEIGHT = {"place": 1.0, "participant": 1.0, "context": 0.5}

SCORING = "idf2"  # "count" | "idf" | "idf2" | "rareN"
REQUIRE_PLACE = False  # keep only windows that name one of the event's places (when a rare place name exists)
PLACE_RARE_DF = 2000
MATCH = "any"  # "any" | "all"
MAX_DF = 1500  # keys in more windows than this are too common to identify an event on their own


def entity_score(roles, idfs=None, scoring=None):
    """Weight of the matched event names. 'count': a place or participant counts 1, the war the
    event is part of counts 0.5 (a broad context, not the event itself). 'idf' and 'idf2' weight
    each matched name by its rarity in the name index (ln(N/df), or its square), because a
    window naming Athenians and Thebans says less than one naming Delium."""
    scoring = scoring or SCORING
    if scoring == "count" or idfs is None:
        return sum(ROLE_WEIGHT[r] for r in roles)
    if scoring.startswith("rare"):
        # number of matched names rarer than ln(N/df) >= T, then the squared-idf sum as tie-break
        t = float(scoring[4:] or 6)
        return sum(ROLE_WEIGHT[r] for r, i in zip(roles, idfs) if i >= t) * 1000 + sum(ROLE_WEIGHT[r] * i * i for r, i in zip(roles, idfs))
    p = 1 if scoring == "idf" else 2
    return sum(ROLE_WEIGHT[r] * (i ** p) for r, i in zip(roles, idfs))


def key_df(prod, k):
    """Windows holding key k. A pseudo key '#i' stands for entity i matched on the full form;
    its count is the number of windows that matched (set in literary())."""
    return prod.exact_df.get(k, 1) if k.startswith("#") else prod.name_df.get(k, 1)


def score_of_names(ents, em, prod):
    eidf = [max(math.log(prod.n_windows / max(1, key_df(prod, k))) for k in ks) for ks in em.values()]
    return entity_score([ents[ei]["role"] for ei in em], eidf)


def rank_key(score, idf_sum):
    """Sort key, best first: higher score, then rarer names."""
    return (-score, -idf_sum)


def suppress_overlaps(ranked, get_span):
    """Keep a ranked window only if its (work, locus range) does not overlap one already kept.
    Adjacent windows share most of their lines, so without this the top 20 is five passages."""
    kept, by_work = [], defaultdict(list)
    for item in ranked:
        work, lo, hi = get_span(item)
        if any(loci_overlap(lo, hi, l2, h2) for l2, h2 in by_work[work]):
            continue
        by_work[work].append((lo, hi))
        kept.append(item)
    return kept


# ----------------------------------------------------------------- event record to names

def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def load_jsonl(path, keyed="qid"):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d[keyed]] = d
    return out


def specific_locations(rec, countries):
    """Locations that can centre a search. A location listed only as a country (P17), not as a
    P276 'location', is dropped. Among the rest, those with a Pleiades id are preferred."""
    c = countries.get(rec["qid"], {})
    p276, p17 = set(c.get("p276", [])), set(c.get("p17", []))
    locs = [l for l in rec["locations"] if not (l["qid"] in p17 and l["qid"] not in p276)]
    with_pl = [l for l in locs if l.get("pleiades")]
    return with_pl or locs


def build_entities(rec, labels, countries, curated=()):
    """Name entities of the event: specific locations, participants, and the war it is part of
    (role 'context'). Each has the keys of all its labels in English, Latin and Greek."""
    ents = []
    for role, items in (("place", specific_locations(rec, countries)), ("participant", rec["participants"]),
                        ("context", rec["part_of"])):
        for it in items:
            names = [it["label"]] if it.get("label") else []
            lab = labels.get(it["qid"], {})
            names += lab.get("la", []) + lab.get("grc", []) + lab.get("el", [])
            variants = label_variants(names)
            if variants:
                stems = sorted({st for n in names for t in label_tokens(n) for st in name_stems(t)})
                ents.append({"qid": it["qid"], "label": it.get("label"), "role": role,
                             "keys": sorted(set().union(*variants)), "variants": [sorted(v) for v in variants],
                             "stems": stems, "names": names, "n_labels": len(names)})
    for c in curated:
        variants = label_variants(c["variants"])
        if variants:
            stems = sorted({st for n in c["variants"] for t in label_tokens(n) for st in name_stems(t)})
            ents.append({"qid": None, "label": c["variants"][0], "role": c.get("role", "participant"),
                         "keys": sorted(set().union(*variants)), "variants": [sorted(v) for v in variants],
                         "stems": stems, "names": list(c["variants"]), "n_labels": len(c["variants"]), "curated": True})
    return ents


# ----------------------------------------------------------------- data access

class Prod:
    def __init__(self, root=PROD):
        self.root = root
        self.names = ro(f"{root}/data/passage_index/window_names.db")
        self.texts = ro(f"{root}/data/passage_index/window_texts.db")
        self.docs = ro(f"{root}/data/documents/metadata.db")
        self.cites = ro(f"{root}/data/citation_index/citations.db") if os.path.exists(f"{root}/data/citation_index/citations.db") else None
        w = json.load(open(f"{root}/data/passage_index/works_by_language.json"))["languages"]
        self.lang = {}
        for lg in ("la", "grc"):
            for x in w[lg]:
                self.lang[x if isinstance(x, str) else x["work"]] = lg
        ad = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend", "author_dates.json")))
        self.author_year = {}
        for lg in ("la", "grc"):
            for a, d in ad.get(lg, {}).items():
                if d.get("year") is not None:
                    self.author_year.setdefault(a, d["year"])
        self.name_df = dict(self.names.execute("SELECT k, df FROM name_df"))
        self.exact_df = {}
        self.n_windows = 265362


def author_of(work):
    return work.split(".", 1)[0]


# ----------------------------------------------------------------- (a) literary passages

def _strip_map(t):
    """Accent- and breathing-stripped text with a map from each kept character back to its index
    in the original (window text stores some accents as separate combining marks)."""
    out, idx = [], []
    for i, ch in enumerate(t):
        for c in unicodedata.normalize("NFD", ch):
            if not unicodedata.combining(c):
                out.append(c)
                idx.append(i)
    return "".join(out), idx


def localize_ords(prod, wid, ords_by_entity, ents, max_lines=6):
    """Lines of a window found through the lemma caches: line ref, the entity and the line start."""
    work, _, start = wid.split(":")
    ord0 = int(start)
    allo = sorted({o for os_ in ords_by_entity.values() for o in os_})[:max_lines]
    rows = {o: (ref, t) for o, ref, t in prod.texts.execute(
        "SELECT ord, ref, text FROM lines WHERE work=? AND ord>=? AND ord<=?", (work, allo[0], allo[-1]))} if allo else {}
    out = []
    for o in allo:
        if o in rows:
            names = sorted({ents[ei]["label"] for ei, os_ in ords_by_entity.items() if o in os_})
            out.append({"ref": rows[o][0], "forms": ["lemma of " + n for n in names], "snippet": rows[o][1][:140].strip()})
    return out


def localize(prod, wid, text, forms, width=70, max_lines=6):
    """A window can be a dozen prose chapters. Return the lines of it that contain a matched
    name form, each with its own reference and a snippet around the form."""
    work, _, start = wid.split(":")
    ord0 = int(start)
    lines = text.split("\n")
    refs = {o: ref for o, ref in prod.texts.execute(
        "SELECT ord, ref FROM lines WHERE work=? AND ord>=? AND ord<?", (work, ord0, ord0 + len(lines)))}
    out = []
    sforms = {_strip_map(f)[0]: f for f in forms}
    for i, ln in enumerate(lines):
        sl, idx = _strip_map(ln)
        pos = [(sl.find(sf), sf, f) for sf, f in sforms.items() if sf and sf in sl]
        if not pos:
            continue
        j, sf, f = min(pos)
        j0, j1 = idx[j], idx[min(j + len(sf), len(idx)) - 1] + 1
        out.append({"ref": refs.get(ord0 + i), "forms": sorted(f for _, _, f in pos),
                    "snippet": ln[max(0, j0 - width):j1 + width].strip()})
    return out[:max_lines]


class Theme:
    """Meaning-based scores of every Latin and Greek fine window against a free-text query,
    computed the way Theme Search computes them (backend/passage_index.py): the query goes to
    the encoder service on port 8090 with the e5 'query: ' prefix, is scored against the stored
    window embeddings, undescribed windows are masked and the lexical boost is applied. The
    only difference is that the ranking here is flat (no one-head-per-work page composition)."""

    def __init__(self, root=PROD):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.path.insert(0, repo)
        from backend import passage_index as pi
        d = os.path.join(root, "data", "passage_index")
        pi._DATA_DIR, pi._LEX_PATH, pi._NAMES_PATH = d, os.path.join(d, "desc_fts.sqlite"), os.path.join(d, "window_names.db")
        pi._ensure_loaded()
        if not pi._state["ok"]:
            raise SystemExit("passage index not loaded: %s" % pi._state["error"])
        import numpy as np
        self.pi, self.np = pi, np
        self.row = {w: i for i, w in enumerate(pi._ids)}
        self.eligible = np.array([(":fine:" in w) and (r.get("language") in ("la", "grc")) for w, r in zip(pi._ids, pi._records)])
        self.scores = None

    def prepare(self, query):
        pi = self.pi
        q = pi.embed_query(pi._E5_PREFIX + query.strip()[:1500])
        sc = pi._mask_undescribed(pi._score_all(q))
        self.lexical = pi._lexical_boost(query, sc)
        self.scores = sc
        return self

    def score_of(self, wid):
        i = self.row.get(wid)
        return None if i is None else float(self.scores[i])

    def top(self, n):
        np = self.np
        sc = np.where(self.eligible, self.scores, -9.0)
        idx = np.argpartition(-sc, n)[:n]
        idx = idx[np.argsort(-sc[idx])]
        return [(self.pi._ids[i], float(sc[i])) for i in idx]

    def gist(self, wid):
        d = (self.pi._records[self.row[wid]].get("desc") or {})
        return d.get("gist") or d.get("setting") or ""


THEME_POOL = 3000
MATCHING = "form"  # "form": full normalised form (stem plus ending) | "key": the index's 5-letter key


LEMMA_CHOICE = "cap"  # lemma of a name: most frequent among capitalised occurrences ("cap") or among all ("all")
LEMMA_DIR = None   # directory with name_lemmas.json and lemma_hits.pkl (lemma_name_index.py)
LEMMA_ORDS = {}    # window id -> entity index -> [line ords holding the name's lemma]
_LEMMA = {}


def load_lemma_data(d):
    if d not in _LEMMA:
        import pickle
        j = json.load(open(os.path.join(d, "name_lemmas.json"), encoding="utf-8"))
        top = j["top_all"] if LEMMA_CHOICE == "all" else j["top"]
        hits = pickle.load(open(os.path.join(d, "lemma_hits.pkl"), "rb"))
        _LEMMA[d] = (top, hits)
    return _LEMMA[d]


def prep_lemmas(ents, top):
    """Per entity: the normalised lemmas of its name tokens (the most frequent lemma of each
    surface form in the lemma caches) and, for tokens that never occur in the caches, the stems
    used by form matching."""
    for e in ents:
        lems, fb = set(), set()
        for n in e.get("names", []):
            for t in label_tokens(n):
                if t in top:
                    lems.add(norm_full(top[t]))
                else:
                    fb |= name_stems(t)
        e["lemmas"], e["stems_fb"] = sorted(lems), sorted(fb)


def _match_forms(prod, ents, wkeys, lemma=None):
    """Match event names on the window's own token. An entity matches a window if some token of
    the window, normalised like the name index does but without the 5-letter cut and with one
    inflectional ending stripped, equals a normalised, ending-stripped name token of the entity.
    The index key is used only to fetch candidates (all keys that start like the stem)."""
    stem2ents = defaultdict(set)
    if lemma is not None:
        prep_lemmas(ents, lemma[0])
    for ei, e in enumerate(ents):
        for st in (e["stems"] if lemma is None else e["stems_fb"]):
            stem2ents[st].add(ei)
    seen = defaultdict(set)  # entity -> windows
    LEMMA_ORDS.clear()
    if lemma is not None:
        lem2ents = defaultdict(set)
        for ei, e in enumerate(ents):
            for l in e["lemmas"]:
                lem2ents[l].add(ei)
        for work, hl in lemma[1].items():
            if base_work(work) not in prod.lang and work not in prod.lang:
                continue
            for o, lems in hl.items():
                for l in lems:
                    for ei in lem2ents.get(l, ()):
                        for st0 in {o // 6 * 6, o // 6 * 6 - 6}:
                            if st0 < 0:
                                continue
                            wid = f"{work}:fine:{st0}"
                            seen[ei].add(wid)
                            wkeys[wid].setdefault(f"#{ei}", set()).add("[" + l + "]")
                            LEMMA_ORDS.setdefault(wid, {}).setdefault(ei, set()).add(o)
    for st in stem2ents:
        if len(st) >= 5:
            sql, arg = "SELECT id, k, form FROM window_names WHERE k = ?", (st[:5],)
        else:  # short stem: every key that starts with it
            sql, arg = "SELECT id, k, form FROM window_names WHERE k >= ? AND k < ?", (st, st[:-1] + chr(ord(st[-1]) + 1))
        for wid, k, form in prod.names.execute(sql, arg):
            if ":fine:" not in wid:
                continue
            work = wid.split(":", 1)[0]
            if base_work(work) not in prod.lang and work not in prod.lang:
                continue
            fs = stem_form(norm_full(form))
            for ei in stem2ents.get(fs, ()):
                seen[ei].add(wid)
                wkeys[wid].setdefault(f"#{ei}", set()).add(form)
    # exact document frequency per entity; an entity in more windows than MAX_DF is too common
    # to identify the event, unless every entity is
    for ei in range(len(ents)):
        prod.exact_df[f"#{ei}"] = len(seen[ei])
    live = [ei for ei in range(len(ents)) if 0 < len(seen[ei]) <= MAX_DF]
    if not live:
        live = sorted((ei for ei in range(len(ents)) if seen[ei]), key=lambda ei: len(seen[ei]))[:1]
    for ei, e in enumerate(ents):
        e["match_keys"] = [f"#{ei}"] if ei in live else []


def literary(prod, ents, span, limit=100, restrict_authors=True, ranking="names", theme=None, seeds=None):
    """ranking: 'names' (name occurrence), 'theme' (Theme Search score alone), or 'theme_names'
    (Theme Search score among windows that hold at least one event name), or 'fused' (reciprocal-rank
    fusion of the name ranking and the Theme Search ranking among windows that hold an event name)."""
    if ranking == "theme":
        ranked, dropped_author = [], 0
        for wid, sc in theme.top(THEME_POOL):
            work = base_work(wid.split(":", 1)[0])
            ay = prod.author_year.get(author_of(work))
            if restrict_authors and span and ay is not None and ay < span[0]:
                dropped_author += 1
                continue
            ranked.append(((-sc, 0.0), wid, {}, {}, ay))
        return _finish(prod, ents, ranked, limit, dropped_author, len(ranked), theme)
    wkeys = defaultdict(dict)  # window id -> key -> forms
    prod.exact_df = {}
    if MATCHING in ("form", "lemma"):
        _match_forms(prod, ents, wkeys, load_lemma_data(LEMMA_DIR) if MATCHING == "lemma" else None)
    else:
        for e in ents:
            ks = [k for k in e["keys"] if prod.name_df.get(k, 0) > 0]
            rare = [k for k in ks if prod.name_df[k] <= MAX_DF]
            e["match_keys"] = rare or sorted(ks, key=lambda k: prod.name_df[k])[:1]
        keys = sorted({k for e in ents for k in e["match_keys"]})
        for n in range(0, len(keys), 400):
            chunk = keys[n:n + 400]
            q = "SELECT id, k, form FROM window_names WHERE k IN (%s)" % ",".join("?" * len(chunk))  # nosec B608
            for wid, k, form in prod.names.execute(q, chunk):
                if ":fine:" not in wid:
                    continue
                work = wid.split(":", 1)[0]
                if base_work(work) not in prod.lang and work not in prod.lang:
                    continue
                wkeys[wid].setdefault(k, set()).add(form)
    keys = sorted({k for e in ents for k in e["match_keys"]})
    has_place = any(e["role"] == "place" and e["match_keys"] and min(key_df(prod, k) for k in e["match_keys"]) <= PLACE_RARE_DF for e in ents)
    if not keys:
        return {"n_raw_windows": 0, "n_after_overlap_suppression": 0, "passages": [], "all_ranked": []}
    ranked = []
    dropped_author = 0
    n_matched = 0
    for wid, kf in wkeys.items():
        em = {}  # entity index -> keys that matched
        for ei, e in enumerate(ents):
            if MATCH == "all":
                for v in e["variants"]:
                    if all(k in kf for k in v):
                        em.setdefault(ei, set()).update(v)
            else:  # "any": one distinctive key of the entity is enough
                hit = {k for k in e["match_keys"] if k in kf}
                if hit:
                    em[ei] = hit
        if not em:
            continue
        if REQUIRE_PLACE and has_place and not any(ents[ei]["role"] == "place" for ei in em):
            continue
        n_matched += 1
        work = base_work(wid.split(":", 1)[0])
        ay = prod.author_year.get(author_of(work))
        if restrict_authors and span and ay is not None and ay < span[0]:
            dropped_author += 1  # the author died before the event began
            continue
        if ranking == "theme_names":
            ts = theme.score_of(wid)
            if ts is not None and ts > -1.0:
                ranked.append(((-ts, 0.0), wid, em, kf, ay))
            continue
        if ranking in ("fused", "fused3"):
            ts = theme.score_of(wid)
            if ts is None or ts <= -1.0:
                continue
            ranked.append(((rank_key(score_of_names(ents, em, prod), 0.0)[0], -ts), wid, em, kf, ay))
            continue
        idf = sum(math.log(prod.n_windows / max(1, key_df(prod, k))) for ks in em.values() for k in ks)
        eidf = [max(math.log(prod.n_windows / max(1, key_df(prod, k))) for k in ks) for ks in em.values()]
        score = entity_score([ents[ei]["role"] for ei in em], eidf)
        ranked.append((rank_key(score, idf), wid, em, kf, ay))
    cocite = CoCite(prod, seeds or []) if ranking == "fused3" else None
    return _finish(prod, ents, ranked, limit, dropped_author, n_matched, theme,
                   fuse=(ranking if ranking in ("fused", "fused3") else False), cocite=cocite)


def _finish(prod, ents, ranked, limit, dropped_author, n_matched, theme, fuse=False, cocite=None):
    ranked.sort(key=lambda r: (r[0], r[1]))
    # fetch refs for every ranked window (needed for overlap suppression and co-citation)
    info = {}
    ids = [r[1] for r in ranked]
    for n in range(0, len(ids), 500):
        chunk = ids[n:n + 500]
        q = "SELECT id, ref_start, ref_end FROM window_texts WHERE id IN (%s)" % ",".join("?" * len(chunk))  # nosec B608
        for wid, rs, re_ in prod.texts.execute(q, chunk):
            info[wid] = (rs, re_)
    if fuse:
        # reciprocal-rank fusion (k=60) of the name ranking and the Theme Search ranking and, for
        # 'fused3', the co-citation ranking (only windows co-cited with a seed are in that list)
        by_names = sorted(ranked, key=lambda r: (r[0][0], r[1]))
        by_theme = sorted(ranked, key=lambda r: (r[0][1], r[1]))
        rn = {r[1]: i for i, r in enumerate(by_names, 1)}
        rt = {r[1]: i for i, r in enumerate(by_theme, 1)}
        rc = {}
        if cocite is not None:
            cs = {}
            for r in ranked:
                if r[1] in info:
                    sc = cocite.score(base_work(r[1].split(":", 1)[0]), parse_ref(info[r[1]][0]), parse_ref(info[r[1]][1]))
                    if sc > 0:
                        cs[r[1]] = sc
            rc = {w: i for i, w in enumerate(sorted(cs, key=lambda w: (-cs[w], w)), 1)}
        ranked = [((-(1 / (60 + rn[r[1]]) + 1 / (60 + rt[r[1]]) + (1 / (60 + rc[r[1]]) if r[1] in rc else 0.0)), 0.0),) + r[1:] for r in ranked]
        ranked.sort(key=lambda r: (r[0], r[1]))

    def span_of(r):
        rs, re_ = info.get(r[1], (None, None))
        return base_work(r[1].split(":", 1)[0]), parse_ref(rs), parse_ref(re_)

    kept = suppress_overlaps([r for r in ranked if r[1] in info], span_of)
    out = []
    for rank, r in enumerate(kept[:limit], 1):
        wid = r[1]
        text = prod.texts.execute("SELECT text FROM window_texts WHERE id=?", (wid,)).fetchone()[0]
        work = base_work(wid.split(":", 1)[0])
        forms = {f for fs in (r[3][k] for ks in r[2].values() for k in ks) for f in fs}
        hit_lines = localize(prod, wid, text, {f for f in forms if not f.startswith("[")})
        if wid in LEMMA_ORDS:
            hit_lines += localize_ords(prod, wid, LEMMA_ORDS[wid], ents)
        out.append({"rank": rank, "window_id": wid, "work": work, "language": prod.lang.get(work) or prod.lang.get(wid.split(":", 1)[0]),
                    "ref_start": info[wid][0], "ref_end": info[wid][1], "author_year": r[4],
                    "score": round(-r[0][0], 4), "n_entities": len(r[2]), "idf_sum": round(-r[0][1], 2),
                    "gist": theme.gist(wid) if theme is not None and wid in theme.row else None,
                    "matched": sorted({f"{ents[ei]['label']} [{ents[ei]['role']}] = {form}" for ei, ks in r[2].items() for k in ks for form in r[3][k]}),
                    "hit_lines": hit_lines, "text": text[:500]})
    all_ranked = [{"work": span_of(r)[0], "lo": span_of(r)[1], "hi": span_of(r)[2], "score": round(-r[0][0], 4)} for r in kept]
    return {"n_raw_windows": n_matched, "n_dropped_author_before_event": dropped_author, "n_after_overlap_suppression": len(kept),
            "passages": out, "all_ranked": all_ranked}


# ----------------------------------------------------------------- (b) documents

def load_crosswalk(path=CROSSWALK):
    m = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            m[int(r["tm_place_id"])] = r["pleiades_id"]
    return m


def load_points(path):
    pts = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            i, la, lo, t = line.rstrip("\n").split("\t")
            pts[i] = (float(la), float(lo), t)
    return pts


def documents(prod, span, centres, points, crosswalk, margin=10, radius_km=100, sample_cap=300):
    if not span or not centres:
        return {"n": 0, "items": [], "findspots": [], "reason": "no date span or no location"}
    lo, hi = span[0] - margin, span[1] + margin
    q = ("SELECT id, source, text_type_label, object_type_label, date_not_before, date_not_after, ancient_place, modern_place, "
         "region, pleiades_id, place_tm_id, principal_edition FROM documents WHERE date_not_before IS NOT NULL "
         "AND date_not_before <= ? AND date_not_after >= ?")
    items, n_nodate_place, n_dates, by_radius = [], 0, 0, {50: 0, 100: 0, 300: 0, 1000: 0}
    for r in prod.docs.execute(q, (hi, lo)):
        n_dates += 1
        (did, src, ttype, otype, dnb, dna, anc, mod, reg, pid, tm, ed) = r
        if not pid and tm in crosswalk:
            pid = crosswalk[tm]
        if not pid or pid not in points:
            n_nodate_place += 1
            continue
        d = min_distance_km(points[pid][:2], centres)
        for rr in by_radius:
            by_radius[rr] += d is not None and d <= rr
        if d is None or d > radius_km:
            continue
        items.append({"id": did, "source": src, "text_type": ttype, "object_type": otype, "not_before": dnb, "not_after": dna,
                      "date_width": dna - dnb, "place": anc or mod, "region": reg, "pleiades_id": pid,
                      "lat": points[pid][0], "lon": points[pid][1], "distance_km": round(d, 1), "edition": ed})
    # narrower dates are more informative about the event; then nearer
    items.sort(key=lambda x: (x["date_width"], x["distance_km"], x["id"]))
    fs = defaultdict(lambda: {"n": 0})
    for it in items:
        f = fs[it["pleiades_id"]]
        f.update(pleiades_id=it["pleiades_id"], label=points[it["pleiades_id"]][2], lat=it["lat"], lon=it["lon"])
        f["n"] += 1
    narrow = sum(1 for i in items if i["date_width"] <= 50)
    return {"n": len(items), "n_date_overlap_anywhere": n_dates, "n_by_radius_km": by_radius, "n_dated_within_50_years": narrow, "n_overlapping_but_no_usable_place": n_nodate_place,
            "span_used": [lo, hi], "radius_km": radius_km, "items": items[:sample_cap],
            "findspots": sorted(fs.values(), key=lambda x: -x["n"])}


# ----------------------------------------------------------------- co-citation ranker

_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
_XREF = re.compile(r"\b([ivxlc]{1,6})\.\s?(\d{1,3})(?:\.\s?(\d{1,3}))?")


def _roman(t):
    tot = 0
    for i, ch in enumerate(t):
        v = _ROMAN[ch]
        tot += -v if i + 1 < len(t) and _ROMAN[t[i + 1]] > v else v
    return tot


class CoCite:
    """Passages cited on the same page as a seed passage.

    seeds: [(work, lo, hi)] primary passages. Every row of the citation index that cites a seed
    (work_id plus overlapping locus) gives a page (article, page). Every OTHER citation on those
    pages, in any work, is a co-cited passage, weighted by the number of distinct pages that
    co-cite it. Commentary units that fall on a seed give the cross-references in their text
    (for example How and Wells on Herodotus: 'cf. vi. 54') as co-cited passages of the same work.
    Passages that overlap a seed are not boosted (they are the seeds)."""

    def __init__(self, prod, seeds):
        self.seeds = seeds
        self.by_work = defaultdict(lambda: defaultdict(list))  # work -> book -> [(cs, ce, page)]
        self.pages, self.n_loci = set(), 0
        if prod.cites is None:
            return
        for work, lo, hi in seeds:
            first = lo[0]
            for ar, pg, ls, le, oe in prod.cites.execute(
                    "SELECT article_id, page, locus_start, locus_end, open_ended FROM citations WHERE work_id=? AND (locus_start LIKE ? OR locus_start=?)",
                    (work, f"{first}.%", str(first))):
                cs, ce = self._span(ls, le, oe)
                if loci_overlap(cs, ce, lo, hi):
                    self.pages.add((ar, pg))
        for ar, pg in self.pages:
            for w2, ls, le, oe in prod.cites.execute(
                    "SELECT work_id, locus_start, locus_end, open_ended FROM citations WHERE article_id=? AND page=?", (ar, pg)):
                cs, ce = self._span(ls, le, oe)
                if cs and not any(w2 == w and loci_overlap(cs, ce, lo, hi) for w, lo, hi in seeds):
                    self._add(w2, cs, ce, (ar, pg))
        self._commentary(prod)

    @staticmethod
    def _span(ls, le, oe):
        cs, ce = parse_ref("x " + (ls or "")), parse_ref("x " + (le or ls or ""))
        if oe:
            ce = cs[:-1] + (cs[-1] + 30,) if len(cs) > 1 else (10 ** 6,)
        return cs, ce

    def _add(self, work, cs, ce, page):
        self.n_loci += 1
        for book in range(cs[0], min(ce[0], cs[0] + 3) + 1):
            self.by_work[work][book].append((cs, ce, page))

    def _commentary(self, prod):
        d = os.path.join(prod.root, "data", "commentaries")
        for work, lo, hi in self.seeds:
            for fn in sorted(os.listdir(d)):
                if not (fn.endswith(f"__{work}.json") or (f"__{work}.part." in fn and fn.endswith(".json"))):
                    continue
                doc = json.load(open(os.path.join(d, fn), encoding="utf-8"))
                for i, u in enumerate(doc.get("units", [])):
                    r = parse_ref(u.get("ref"))
                    if not (r and loci_overlap(r, r, lo, hi)):
                        continue
                    for m in _XREF.finditer((u.get("text") or "").lower()):
                        try:
                            loc = (_roman(m.group(1)), int(m.group(2))) + ((int(m.group(3)),) if m.group(3) else ())
                        except KeyError:
                            continue
                        if not loci_overlap(loc, loc, lo, hi):
                            self._add(work, loc, loc, ("commentary", fn, i))

    def score(self, work, lo, hi):
        """Number of distinct pages that co-cite a passage overlapping the window lo..hi."""
        if not lo or not hi or any(work == w and loci_overlap(lo, hi, l2, h2) for w, l2, h2 in self.seeds):
            return 0
        pages = set()
        for book in range(lo[0], min(hi[0], lo[0] + 3) + 1):
            for cs, ce, pg in self.by_work.get(work, {}).get(book, ()):
                if loci_overlap(cs, ce, lo, hi):
                    pages.add(pg)
        return len(pages)


# ----------------------------------------------------------------- LLM rerank (fused_llm)

def fmt_year(y):
    return f"{-y} BC" if y < 0 else f"AD {y}"


def llm_context(rec, ents, span, intro, countries):
    """The event description the judge sees: name, date, place, participants, encyclopedia summary."""
    places = [l["label"] for l in specific_locations(rec, countries) if l.get("label")]
    people = [e["label"] for e in ents if e["role"] in ("participant",) and e.get("label")]
    date = fmt_year(span[0]) if span and span[0] == span[1] else (f"{fmt_year(span[0])} to {fmt_year(span[1])}" if span else "unknown")
    return {"name": rec["label"], "date": date, "place": ", ".join(places) or "unknown",
            "participants": ", ".join(dict.fromkeys(people)) or "not recorded", "intro": intro}


def llm_passage(prod, p, translations_mod):
    """What the judge sees of one dossier passage: reference, index description, the lines that
    hold the event names (original language) and the aligned English translation when there is one."""
    work = p["window_id"].split(":", 1)[0]
    lines, refs = [], []
    for h in p.get("hit_lines", [])[:3]:
        if not h.get("ref"):
            continue
        r = prod.texts.execute("SELECT text FROM lines WHERE work=? AND ref=? LIMIT 1", (work, h["ref"])).fetchone()
        lines.append((h["ref"], (r[0] if r else h["snippet"]).strip()[:350]))
        refs.append(h["ref"])
    if not lines:
        lines = [(p["ref_start"], p["text"].strip()[:350])]
        refs = [p["ref_start"]]
    tr = ""
    try:
        info = translations_mod.for_passage(base_work(work), refs)
        if info and info.get("available"):
            tr = (info.get("text") or "")[:450]
    except Exception:  # noqa: BLE001 - a missing translation is normal
        tr = ""
    return {"window_id": p["window_id"], "ref": f"{p['ref_start']} to {p['ref_end']}", "language": p["language"],
            "gist": p.get("gist"), "lines": lines, "translation": tr}


def llm_rerank(prod, lit, ctx, event_key, judge, top=100):
    """Reorder the first `top` passages of a fused dossier: yes, then mention, then no, with the
    fused rank as the tie-break. Passages after `top` keep their order."""
    from backend import translations as tmod
    tmod._DIR = os.path.join(prod.root, "data", "translations")
    tmod._index = None
    tmod._cache.clear()
    head = lit["passages"][:top]
    labels = judge.judge_event(event_key, ctx, [llm_passage(prod, p, tmod) for p in head])
    import llm_judge
    new = llm_judge.rerank(head, labels)
    order = {p["window_id"]: i for i, p in enumerate(new)}
    ar = lit["all_ranked"]
    lit["all_ranked"] = [ar[i] for i in sorted(range(len(head)), key=lambda i: order[head[i]["window_id"]])] + ar[len(head):]
    for i, p in enumerate(new, 1):
        p["rank"], p["llm_label"] = i, labels.get(p["window_id"])
    lit["passages"] = new + lit["passages"][top:]
    lit["llm"] = {"model": judge.model, "counts": {k: sum(1 for v in labels.values() if v == k) for k in ("yes", "mention", "no", None)}}
    return lit


# ----------------------------------------------------------------- (c) scholarship

def citing(prod, work, lo, hi, limit=25):
    if prod.cites is None:
        return []
    out, seen = [], set()
    first = lo[0] if lo else None
    rows = prod.cites.execute(
        "SELECT c.article_id, c.page, c.locus_start, c.locus_end, c.open_ended, c.surface, c.sentence, a.title, a.authors, a.journal, a.year, a.url_jstor, a.url_ia "
        "FROM citations c JOIN articles a ON a.id=c.article_id WHERE c.work_id=? AND (c.locus_start LIKE ? OR c.locus_start=?)",
        (work, f"{first}.%", str(first))).fetchall()
    for r in rows:
        cs, ce = parse_ref("x " + (r[2] or "")), parse_ref("x " + (r[3] or r[2] or ""))
        if not re.search(r"[A-Za-z]", r[5] or ""):
            continue
        if r[4]:
            ce = cs[:-1] + (cs[-1] + 30,) if len(cs) > 1 else (10 ** 6,)
        if not loci_overlap(cs, ce, lo, hi):
            continue
        if r[0] in seen:
            continue
        seen.add(r[0])
        out.append({"article_id": r[0], "title": r[7], "authors": r[8], "journal": r[9], "year": r[10], "page": r[1],
                    "cites": re.sub(r"\s+", " ", r[5] or ""), "url": r[11] or r[12]})
    out.sort(key=lambda x: (-(x["year"] or 0), x["title"] or ""))
    return out[:limit]


def commentary(prod, work, lo, hi, limit=15):
    d = os.path.join(prod.root, "data", "commentaries")
    out = []
    for fn in sorted(os.listdir(d)):
        if not (fn.endswith(f"__{work}.json") or (f"__{work}.part." in fn and fn.endswith(".json"))):
            continue
        doc = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        for u in doc.get("units", []):
            r = parse_ref(u.get("ref"))
            if r and loci_overlap(r, r, lo, hi):
                out.append({"commentator": doc.get("commentator"), "ref": u.get("ref"), "lemma": u.get("lemma"), "text": (u.get("text") or "")[:300]})
    return out[:limit]


def scholarship(prod, passages):
    res = []
    for p in passages:
        lo, hi = p["lo"], p["hi"]
        res.append({"work": p["work"], "range": p["range"], "source": p["source"],
                    "citations": citing(prod, p["work"], lo, hi), "commentary": commentary(prod, p["work"], lo, hi)})
    return res


# ----------------------------------------------------------------- main

def hand_passages(spec):
    out = []
    for work, a, b in spec.get("passages", []):
        lo, hi = parse_ref("x " + a), parse_ref("x " + b)
        if lo and hi:
            out.append({"work": work, "range": f"{a}-{b}", "lo": lo, "hi": hi, "source": "hand list"})
    return out


def build(rec, labels, countries, prod, points, crosswalk, spec=None, limit=100, use_curated=False,
          ranking="names", theme=None, query=None, restrict_authors=True, judge=None, event_key=None):
    t0 = time.time()
    span = event_span(rec)
    ents = build_entities(rec, labels, countries, (spec or {}).get("curated_names", []) if use_curated else ())
    if theme is not None:
        theme.prepare(query)
    seeds = [(p["work"], p["lo"], p["hi"]) for p in hand_passages(spec)] if spec else []
    llm = ranking == "fused_llm"
    lit = literary(prod, ents, span, limit=max(limit, 100) if llm else limit, restrict_authors=restrict_authors,
                   ranking="fused" if llm else ranking, theme=theme, seeds=seeds)
    if llm:
        lit = llm_rerank(prod, lit, llm_context(rec, ents, span, query, countries), event_key, judge)
    t1 = time.time()
    locs = specific_locations(rec, countries)
    centres = []
    for l in locs:
        if l.get("pleiades") and l["pleiades"] in points:
            centres.append(points[l["pleiades"]][:2])
        elif l.get("coord") and parse_point(l["coord"]):
            centres.append(parse_point(l["coord"]))
    cc = (spec or {}).get("curated_centre") if use_curated else None
    if cc:  # Wikidata gives a sea or a country for some events; an editor supplies the site
        centres, locs = [(cc[0], cc[1])], [{"label": cc[2], "pleiades": None, "coord": f"Point({cc[1]} {cc[0]})"}]
    docs = documents(prod, span, centres, points, crosswalk)
    t2 = time.time()
    prim = hand_passages(spec) if spec else []
    if not prim:
        for p in lit["passages"][:5]:
            lo, hi = parse_ref(p["ref_start"]), parse_ref(p["ref_end"])
            prim.append({"work": p["work"], "range": f"{p['ref_start']} - {p['ref_end']}", "lo": lo, "hi": hi, "source": "top literary hits"})
    sch = scholarship(prod, prim)
    t3 = time.time()
    mp = [{"kind": "event location", "label": l["label"], "lat": c[0], "lon": c[1]} for l, c in
          zip([x for x in locs if (x.get("pleiades") and x["pleiades"] in points) or (x.get("coord") and parse_point(x["coord"]))], centres)]
    mp += [{"kind": "document findspot", "label": f["label"], "lat": f["lat"], "lon": f["lon"], "n_documents": f["n"]} for f in docs.get("findspots", [])]
    all_ranked = lit.pop("all_ranked")
    dossier = {
        "event": {k: rec[k] for k in ("qid", "label", "description", "types", "wikipedia_title", "locations", "participants", "part_of")} | {"span": span, "names_used": ents},
        "literary": lit, "documents": docs, "scholarship": {"primary_passages": [{k: v for k, v in p.items() if k not in ("lo", "hi")} for p in prim], "results": sch},
        "map": mp, "timings_s": {"literary": round(t1 - t0, 2), "documents": round(t2 - t1, 2), "scholarship": round(t3 - t2, 2)},
    }
    return dossier, all_ranked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--countries", required=True)
    ap.add_argument("--pleiades", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--qid")
    ap.add_argument("--sample")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--scoring", default="idf2", choices=["count", "idf", "idf2", "rare5", "rare6", "rare7", "rare8"])
    ap.add_argument("--match", default="any", choices=["any", "all"])
    ap.add_argument("--require-place", action="store_true")
    ap.add_argument("--matching", default="form", choices=["form", "key", "lemma"],
                    help="form: full normalised form plus one ending (default). key: the index's 5-letter key. "
                         "lemma: the dictionary form from the lemma caches (needs --lemma-dir).")
    ap.add_argument("--lemma-dir", help="output directory of lemma_name_index.py")
    ap.add_argument("--lemma-choice", default="cap", choices=["cap", "all"])
    ap.add_argument("--ius", action="store_true", help="let a name in -ius accept its oblique forms (Arminii, Pompei, Darium)")
    ap.add_argument("--max-df", type=int, default=1500)
    ap.add_argument("--ranking", default="names", choices=["names", "theme", "theme_names", "fused", "fused3", "fused_llm"])
    ap.add_argument("--intros", help="intros.json from fetch_wikipedia_intros.py (the Theme Search queries)")
    ap.add_argument("--llm-model", default="Qwen/Qwen3.8-27B-FP8", help="BullsAI model for --ranking fused_llm")
    ap.add_argument("--llm-cache", help="SQLite file of cached judgements (default: llm_judgements.sqlite in --out)")
    ap.add_argument("--llm-workers", type=int, default=8, help="requests in flight")
    ap.add_argument("--no-author-filter", action="store_true")
    ap.add_argument("--curated", action="store_true", help="add the hand-curated names of the sample file")
    a = ap.parse_args()
    events, labels, countries = load_jsonl(a.events), load_jsonl(a.labels), load_jsonl(a.countries)
    points, crosswalk = load_points(a.pleiades), load_crosswalk()
    global SCORING, MATCH, REQUIRE_PLACE, MAX_DF, MATCHING, IUS_EXPANSION, LEMMA_DIR, LEMMA_CHOICE
    SCORING, MATCH, REQUIRE_PLACE, MAX_DF, MATCHING = a.scoring, a.match, a.require_place, a.max_df, a.matching
    LEMMA_DIR, LEMMA_CHOICE = a.lemma_dir, a.lemma_choice
    IUS_EXPANSION = a.ius
    prod = Prod()
    theme = Theme() if a.ranking != "names" else None
    judge = None
    if a.ranking == "fused_llm":
        import llm_judge
        os.makedirs(a.out, exist_ok=True)
        judge = llm_judge.Judge(a.llm_model, a.llm_cache or os.path.join(a.out, "llm_judgements.sqlite"), a.llm_workers)
    intros = json.load(open(a.intros)) if a.intros else {}
    os.makedirs(a.out, exist_ok=True)
    jobs = []
    if a.sample:
        for s in json.load(open(a.sample))["events"]:
            jobs.append((s["key"], events[s["qid"]], s))
    else:
        jobs.append((a.qid, events[a.qid], None))
    for key, rec, spec in jobs:
        d, ranked = build(rec, labels, countries, prod, points, crosswalk, spec, a.limit, a.curated, a.ranking, theme,
                         intros.get(key, {}).get("query") or rec["description"] or rec["label"], not a.no_author_filter,
                         judge, key)
        json.dump(d, open(os.path.join(a.out, f"{key}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=sorted)
        json.dump(ranked, open(os.path.join(a.out, f"{key}.ranked.json"), "w"))
        print(key, rec["label"], "lit", d["literary"]["n_after_overlap_suppression"], "docs", d["documents"]["n"],
              "sch", sum(len(r["citations"]) for r in d["scholarship"]["results"]), d["timings_s"], file=sys.stderr)


if __name__ == "__main__":
    main()
