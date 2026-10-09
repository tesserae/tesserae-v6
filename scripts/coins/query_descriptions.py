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

    results = []
    for label, fname, prefix, lo, hi, para in PASSAGES:
        text = passage_text(args.texts, fname, prefix, lo, hi)
        entry = {"label": label, "text_chars": len(text), "paraphrase": para, "queries": {}}
        for kind, q in (("text", text[:1500]), ("paraphrase", para)):
            if not q:
                entry["queries"][kind] = "NO TEXT FOUND"
                continue
            qv = embed([q])[0]
            sc = vecs @ qv
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
