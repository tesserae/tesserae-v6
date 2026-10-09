#!/usr/bin/env python3
"""Query the embedded coin-type descriptions with literary passages (prototype).

For each of ten passages with known coin parallels, embeds (a) the Latin
passage text and (b) a short English paraphrase through the Theme Search
encoder, and prints the top-k distinct coin descriptions by cosine.

    python scripts/coins/query_descriptions.py --texts ~/tesserae-v6-dev/texts/la \\
        --emb DIR --coins coins.jsonl --out results.json
"""
import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed_descriptions import embed  # noqa: E402

# (label, file, tag regex for the first and last ref, paraphrase)
PASSAGES = [
    ("Aeneid 8.675-713 Actium on the shield", "vergil.aeneid.tess", "aen. 8.", 675, 713,
     "The battle of Actium: Augustus leads the Italians, Apollo above, Cleopatra and the fleet, Nile receiving the defeated"),
    ("Horace Odes 1.37 Cleopatra", "horace.odes.tess", "od. 1.37.", 1, 32,
     "Cleopatra defeated, the fall of Egypt, the queen who dared to die by the serpent"),
    ("Res Gestae 34 clipeus virtutis", "caesar_augustus.res_gestae_divi_augusti.tess", "anc. 1.", 34, 34,
     "Augustus given a golden shield in the senate house for courage, clemency, justice and piety, laurels on his doorposts"),
    ("Ovid Fasti 1.709-722 Ara Pacis", "ovid.fasti.part.1.tess", "fast. 1.", 709, 722,
     "The altar of Peace: the goddess Pax with olive branch, the victim sacrificed, peace under the Caesars"),
    ("Virgil Eclogue 4 golden age", "vergil.eclogues.tess", "ecl. 4.", 1, 63,
     "The return of the golden age with the birth of a child, a new race from heaven, earth bearing without toil"),
    ("Horace Carmen Saeculare", "horace.carmen_saeculare.tess", "c.s. ", 1, 76,
     "Secular games hymn to Apollo and Diana, Sun and Moon, fertility of Italy, prosperity of Rome under Augustus"),
    ("Suetonius Augustus 94 Capricorn", "suetonius.de_vita_caesarum.part.2.augustus.tess", "aug. 94.", 1, 12,
     "Augustus' birth omens and horoscope: the sign of Capricorn, the stars and the sun"),
    ("Lucan 1.183-227 Caesar at the Rubicon", "lucan.bellum_civile.tess", "luc. 1.", 183, 227,
     "Caesar crossing the Rubicon with his army marching to civil war, the vision of Rome as a woman"),
    ("Tacitus Annals 1.60-62 Germanicus", "tacitus.annales.part.1.tess", "ann. 1.", 60, 62,
     "Germanicus recovers a lost legionary eagle and buries the dead of Varus in the German forest"),
    ("Pliny Letters 6.31 Trajan's harbour", "pliny_the_younger.letters.tess", "letters 6.31.", 0, 20,
     "Trajan builds a new harbour with an island mole and breakwater at the coast, ships entering the port"),
]


# text file -> (translation file, author key in backend/author_dates.json "la")
TRANSLATION = {'vergil.aeneid.tess': ('la__vergil.aeneid.json', 'vergil'), 'horace.odes.tess': ('la__horace.odes.json', 'horace'), 'caesar_augustus.res_gestae_divi_augusti.tess': ('la__caesar_augustus.res_gestae_divi_augusti.json', 'caesar_augustus'), 'ovid.fasti.part.1.tess': ('la__ovid.fasti.json', 'ovid'), 'vergil.eclogues.tess': ('la__vergil.eclogues.json', 'vergil'), 'horace.carmen_saeculare.tess': ('la__horace.carmen_saeculare.json', 'horace'), 'suetonius.de_vita_caesarum.part.2.augustus.tess': ('la__suetonius.de_vita_caesarum.json', 'suetonius'), 'lucan.bellum_civile.tess': ('la__lucan.bellum_civile.json', 'lucan'), 'tacitus.annales.part.1.tess': ('la__tacitus.annales.json', 'tacitus'), 'pliny_the_younger.letters.tess': ('la__pliny_the_younger.letters.json', 'pliny_the_younger')}

# author_dates.json holds one year per author (the death year or the
# floruit). The lifetime is taken as the 60 years before it, and the filter
# window is that lifetime plus 50 years after.
LIFETIME_BEFORE = 60
YEARS_AFTER = 50


def author_window(authors_json, key):
    year = json.load(open(authors_json))["la"][key]["year"]
    return year - LIFETIME_BEFORE, year + YEARS_AFTER


def translation_text(trans_dir, tfile, prefix, lo, hi):
    """The aligned English for the passage's lines: the translation units the
    lines map to, in order, each once, joined. Units are chunks of the
    translator's text (about 40 source lines for the Aeneid), so this can run
    past the passage on either side."""
    path = os.path.join(trans_dir, tfile)
    if not os.path.exists(path):
        return ""
    t = json.load(open(path, encoding="utf-8"))
    units, r2u = t.get("units") or [], t.get("ref_to_unit") or {}
    pat = re.compile(r"^.*?" + re.escape(prefix) + r"(\d+)(?:\.\d+)?$", re.I)
    seen, out = set(), []
    for ref, u in r2u.items():
        m = pat.match(ref)
        if m and lo <= int(m.group(1)) <= hi and u not in seen:
            seen.add(u)
            out.append((u, units[u]))
    out.sort()
    return " ".join(x[1].strip() for x in out)


def longest_sentence(text):
    sents = [x.strip() for x in re.split(r"(?<=[.!?;])\s+", text) if x.strip()]
    return max(sents, key=len) if sents else ""


# passage -> (work key in the passage index, first ref numbers, last ref numbers)
WINDOW_WORK = {
    "vergil.aeneid.tess": ("vergil.aeneid.part.8", (8, 675), (8, 713)),
    "horace.odes.tess": ("horace.odes.part.1", (1, 37), (1, 37)),
    "caesar_augustus.res_gestae_divi_augusti.tess": ("caesar_augustus.res_gestae_divi_augusti", (1, 34), (1, 34)),
    "ovid.fasti.part.1.tess": ("ovid.fasti.part.1", (1, 709), (1, 722)),
    "vergil.eclogues.tess": ("vergil.eclogues.part.4", (4, 1), (4, 63)),
    "horace.carmen_saeculare.tess": ("horace.carmen_saeculare", (1,), (76,)),
    "suetonius.de_vita_caesarum.part.2.augustus.tess": ("suetonius.de_vita_caesarum.part.2.augustus", (94,), (94,)),
    "lucan.bellum_civile.tess": ("lucan.bellum_civile.part.1", (1, 183), (1, 227)),
    "tacitus.annales.part.1.tess": ("tacitus.annales.part.1", (1, 60), (1, 62)),
    "pliny_the_younger.letters.tess": ("pliny_the_younger.letters.part.6", (6, 31), (6, 31)),
}
DESC_KEYS = ("mode", "setting", "participants", "action_steps", "props",
             "themes", "imagery_tone", "gist")


def ref_nums(ref):
    return tuple(int(x) for x in re.findall(r"\d+", (ref or "").rsplit(" ", 1)[-1]))


def description_blob(desc):
    """The text the passage index embeds for a window (scripts/corpus/apply_passage_rows.py
    blob_for), without the query prefix."""
    parts = []
    for k in DESC_KEYS:
        v = desc.get(k)
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        if v:
            parts.append(f"{k}: {v}")
    return " | ".join(parts)


def concreteness(desc):
    """Count of named things: props, participants, and setting words."""
    n = len(desc.get("props") or [])
    part = desc.get("participants") or ""
    n += len([x for x in re.split(r",| and ", part if isinstance(part, str) else ", ".join(part)) if x.strip()])
    n += len((desc.get("setting") or "").split()) // 3
    return n


def covering_windows(path, cache=None):
    """Fine windows whose ref range overlaps each passage. Streams the big
    descriptions file once and keeps only the ten works needed."""
    if cache and os.path.exists(cache):
        return json.load(open(cache))
    wanted = {v[0]: k for k, v in WINDOW_WORK.items()}
    needles = {w: f'"work": "{w}"' for w in wanted}
    found = {k: [] for k in WINDOW_WORK}
    with open(path, encoding="utf-8") as f:
        for line in f:
            for w, needle in needles.items():
                if needle in line[:400]:
                    rec = json.loads(line)
                    if rec.get("scale") != "fine" or rec["work"] != w:
                        break
                    _, a, b = WINDOW_WORK[wanted[w]]
                    n = len(a)
                    s0, e0 = ref_nums(rec["ref_start"])[:n], ref_nums(rec["ref_end"])[:n]
                    if s0 <= b and e0 >= a:
                        found[wanted[w]].append({"id": rec["id"], "ref_start": rec["ref_start"],
                                                 "ref_end": rec["ref_end"], "desc": rec["desc"]})
                    break
    if cache:
        json.dump(found, open(cache, "w"))
    return found


def passage_text(texts, fname, prefix, lo, hi):
    out = []
    pat = re.compile(r"^<[^>]*?" + re.escape(prefix) + r"(\d+)(?:\.\d+)?>\s*(.*)$", re.I)
    with open(os.path.join(texts, fname), encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.strip())
            if m and lo <= int(m.group(1)) <= hi:
                out.append(m.group(2).strip())
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", required=True)
    ap.add_argument("--emb", required=True)
    ap.add_argument("--coins", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--query-source", choices=["hand", "translation", "window-description"], default="hand",
                    help="hand: Latin text and hand paraphrase (original run). "
                         "translation: the Reader's English translation of the passage, "
                         "whole and its longest sentence. "
                         "window-description: the model-written English description of "
                         "the passage index's fine windows that cover the passage")
    ap.add_argument("--descriptions", default="/var/www/tesseraev6_flask/data/passage_index/descriptions.jsonl",
                    help="read-only passage index descriptions")
    ap.add_argument("--window-cache", default=None,
                    help="JSON cache of the covering windows (written if absent)")
    ap.add_argument("--translations", default="/var/www/tesseraev6_flask/data/translations",
                    help="read-only folder of la__<work>.json translations")
    ap.add_argument("--date-filter", action="store_true",
                    help="keep only coin types whose date range overlaps the author's "
                         "lifetime plus 50 years (backend/author_dates.json)")
    ap.add_argument("--authors", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend", "author_dates.json"))
    args = ap.parse_args()

    vecs = np.load(os.path.join(args.emb, "vectors.npy")).astype(np.float32)
    strings = json.load(open(os.path.join(args.emb, "strings.json")))
    types = json.load(open(os.path.join(args.emb, "types.json")))
    by_row = {}
    for tid, row in types.items():
        by_row.setdefault(row, []).append(tid)
    meta = {}
    with open(args.coins, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in types:
                meta[r["id"]] = (r["authority"] or r["issuer"], r["date_not_before"], r["date_not_after"],
                                 r["obverse_legend"], r["reverse_legend"], r["denomination"])

    # per-row date range (a row shared by several types uses the widest)
    lo_row = np.full(len(strings), 10**6, dtype=np.int32)
    hi_row = np.full(len(strings), -10**6, dtype=np.int32)
    with open(args.coins, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            row = types.get(r["id"])
            if row is None or r["date_not_before"] is None:
                continue
            lo_row[row] = min(lo_row[row], r["date_not_before"])
            hi_row[row] = max(hi_row[row], r["date_not_after"])

    windows_all = (covering_windows(args.descriptions, args.window_cache)
                   if args.query_source == "window-description" else None)
    results = []
    for label, fname, prefix, lo, hi, para in PASSAGES:
        text = passage_text(args.texts, fname, prefix, lo, hi)
        entry = {"label": label, "text_chars": len(text), "paraphrase": para, "queries": {}}
        mask = None
        if args.date_filter:
            w0, w1 = author_window(args.authors, TRANSLATION[fname][1])
            mask = (hi_row >= w0) & (lo_row <= w1)
            entry["date_window"] = [w0, w1]
            entry["rows_kept"] = int(mask.sum())
        if args.query_source == "window-description":
            wins = windows_all[fname]
            entry["windows"] = [{"id": w["id"], "refs": [w["ref_start"], w["ref_end"]],
                                 "gist": w["desc"].get("gist")} for w in wins]
            queries = []
            if wins:
                blobs = [description_blob(w["desc"]) for w in wins]
                queries.append(("window_concat", " ".join(blobs)[:1500]))
                best = max(wins, key=lambda w: concreteness(w["desc"]))
                entry["best_window"] = best["id"]
                queries.append(("window_single", description_blob(best["desc"])[:1500]))
                queries.append(("window_single_gist", (best["desc"].get("gist") or "")[:1500]))
            else:
                queries = [("window_concat", ""), ("window_single", ""), ("window_single_gist", "")]
        elif args.query_source == "translation":
            tr = translation_text(args.translations, TRANSLATION[fname][0], prefix, lo, hi)
            entry["translation_chars"] = len(tr)
            entry["translation_sentence"] = longest_sentence(tr)
            queries = (("translation", tr[:1500]), ("translation_sentence", entry["translation_sentence"][:1500]))
        else:
            queries = (("text", text[:1500]), ("paraphrase", para))
        for kind, q in queries:
            if not q:
                entry["queries"][kind] = "NO TEXT FOUND"
                continue
            qv = embed([q])[0]
            sc = vecs @ qv
            if mask is not None:
                sc = np.where(mask, sc, -2.0)
            top = np.argsort(-sc)[:args.k]
            hits = []
            for row in top:
                ids = by_row[int(row)]
                m = meta[ids[0]]
                hits.append({"score": round(float(sc[row]), 4), "description": strings[row],
                             "n_types": len(ids), "example": ids[0], "authority": m[0],
                             "dates": [m[1], m[2]], "legends": [m[3], m[4]], "denomination": m[5]})
            entry["queries"][kind] = hits
        results.append(entry)
    json.dump(results, open(args.out, "w"), indent=1, ensure_ascii=False)
    print("wrote", args.out, file=sys.stderr)


if __name__ == "__main__":
    main()
