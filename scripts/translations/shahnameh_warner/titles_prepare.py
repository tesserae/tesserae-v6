import json
import re
import sys

base = sys.argv[1]
st = json.load(open(base + "/stories_raw.json"))
W = json.load(open(base + "/warner_stories.json"))
T = json.load(open(base + "/match_table.json"))
FIX = {
    "Bahrain": "Bahram",
    "Bahnim": "Bahram",
    "Bahriim": "Bahram",
    "Bahrdm": "Bahram",
    "Kaiis": "Kaus",
    "Kaus": "Kaus",
    "Afnisiyab": "Afrasiyab",
    "Afrasiydb": "Afrasiyab",
    "Afrdsiyab": "Afrasiyab",
    "Rustarn": "Rustam",
    "Kustam": "Rustam",
    "Eustam": "Rustam",
    "Zdl": "Zal",
    "Zdbulistdn": "Zabulistan",
    "Zabulistdn": "Zabulistan",
    "ol": "of",
    "Siydwush": "Siyawush",
    "Siyuwus": "Siyawush",
    "Nushirwiin": "Nushirwan",
    "Nushirwdn": "Nushirwan",
    "Niishirwan": "Nushirwan",
    "Nushinvan": "Nushirwan",
    "Minuchihr": "Minuchihr",
    "Khusrau": "Khusrau",
    "Tiis": "Tus",
    "Giv": "Giv",
    "Gi'v": "Giv",
    "Giidarz": "Gudarz",
    "Gtidarz": "Gudarz",
    "Kai": "Kai",
    "Asfandi}Tar": "Asfandiyar",
    "Sikandar": "Sikandar",
    "Mihrdb": "Mihrab",
    "Mihrab": "Mihrab",
    "Faridiin": "Faridun",
}


def clean(t):
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"(?<=[A-Za-z])ii(?=[A-Za-z])", "u", t)
    t = re.sub(r"(?<=[A-Za-z])ll?(?=[A-Z])", "", t)
    t = re.sub(r"\s*[\.\-_,;:]*\s*\d+\s*$", "", t)  # trailing page numbers
    t = re.sub(r"\s*\.{2,}.*$", "", t)
    t = re.sub(r"- (?=[a-z])", "", t)  # hyphenated line breaks
    for a, b in FIX.items():
        t = re.sub(r"\b" + re.escape(a) + r"\b", b, t)
    return t.strip(" .,;:-")


def junk(t):
    return (
        bool(re.search(r"[^A-Za-z ,'’\-\.\(\)?!:;\"]|\\\\|  ", t))
        or len(t) < 6
        or bool(re.search(r"\b[a-z]\b(?<!a)", t.replace(" a ", " ")))
    )


rows = {}
for g in T:
    if not g["stories"]:
        continue
    for s in g["stories"]:
        rows[s] = {
            "status": g["status"],
            "ns": len(g["stories"]),
            "nw": len(g["warner"]),
            "warner": g["warner"],
        }
need = []
ok = {}
for n in range(1, len(st) + 1):
    r = rows.get(n)
    if r and r["ns"] == 1 and r["nw"] == 1 and r["status"].startswith("matched"):
        h = clean(W[r["warner"][0] - 1]["title"])
        if not junk(h):
            ok[n] = h
            continue
    need.append(n)
json.dump({"ok": ok, "need": need}, open(base + "/titles_prep.json", "w"))
print(len(ok), len(need))
