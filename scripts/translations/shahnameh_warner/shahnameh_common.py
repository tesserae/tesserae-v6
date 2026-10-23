import re
import unicodedata
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import concepts

PMAP = {
    "ب": "b",
    "پ": "b",
    "ت": "t",
    "ط": "t",
    "ث": "s",
    "س": "s",
    "ص": "s",
    "ج": "j",
    "چ": "C",
    "ح": "",
    "ه": "",
    "خ": "K",
    "د": "d",
    "ذ": "z",
    "ز": "z",
    "ض": "z",
    "ظ": "z",
    "ژ": "Z",
    "ر": "r",
    "ش": "S",
    "ع": "",
    "غ": "k",
    "ق": "k",
    "ک": "k",
    "گ": "k",
    "ف": "f",
    "ل": "l",
    "م": "m",
    "ن": "n",
    "ا": "",
    "آ": "",
    "و": "",
    "ی": "",
    "ء": "",
    "ئ": "",
    "ؤ": "",
    "أ": "",
    "ۀ": "",
}


def pers_skel(w):
    w = unicodedata.normalize("NFKD", w)
    w = w.replace("ي", "ی").replace("ك", "ک")
    s = "".join(PMAP.get(c, "") for c in w)
    return re.sub(r"(.)\1+", r"\1", s)


def lat_skel(w):
    w = unicodedata.normalize("NFKD", w.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    w = re.sub(r"[^a-z]", "", w)
    w = (
        w.replace("sh", "S")
        .replace("kh", "K")
        .replace("ch", "C")
        .replace("gh", "k")
        .replace("zh", "Z")
        .replace("th", "s")
        .replace("dh", "z")
        .replace("ph", "f")
    )
    w = (
        w.replace("q", "k")
        .replace("g", "k")
        .replace("c", "k")
        .replace("x", "ks")
        .replace("p", "b")
        .replace("v", "f")
        .replace("w", "")
        .replace("y", "")
        .replace("h", "")
    )
    w = re.sub(r"[aeiou]", "", w)
    w = w.replace("t", "t").replace("z", "z")
    return re.sub(r"(.)\1+", r"\1", w)


STOP = set(
    "The He She It They We You I His Her Their Our My Thy Thou Thee Then Thus Now When What Who Whom How That This There These Those And But For If In On At To Of By With From As Or So Not No Yes Lo O Oh Ay Ah God Lord Shah King Khan Prince Is Are Was Were Be Been Let Say Said Come Came Go Went Each All Some Such One Two Three Four Five Six Seven Ten Hundred Thousand Heaven Earth World Sun Moon Master Sire Sir Hail Hark Behold Anon Yet Though While Whence Whither Wherefore Where Why Which Whose Even Ere Till Whoso Wherein Mighty Great Good Fair Brave Noble Wise Lion Day Night Fortune Fate".split()
)


def warner_tokens(sec):
    toks = collections.Counter()
    for t in re.findall(r"[A-Za-zÀ-ɏ'’\-]+", sec["title"]):
        t = t.strip("'’-")
        if t[:1].isupper() and t not in STOP and len(t) > 2:
            toks[lat_skel(t)] += 3
    for p in sec["paragraphs"]:
        for m in re.finditer(
            r"(?<![\.\!\?\"”“/:;] )(?<!^)\b([A-Z][a-zÀ-ɏ'’\-]{2,})", p
        ):
            w = m.group(1)
            if w in STOP:
                continue
            toks[lat_skel(w)] += 1
    for t in re.findall(r"[a-z]+", sec["title"].lower()):
        c = concepts.EN.get(t)
        if c:
            toks["#" + c] += 3
    toks.pop("", None)
    return {k: v for k, v in toks.items() if len(k) >= 2}


def persian_tokens(st, lines):
    toks = collections.Counter()
    for t in re.findall(r"[؀-ۿ]+", st["title_fa"]):
        s = pers_skel(t)
        if len(s) >= 2:
            toks[s] += 3
    for t in re.findall(r"[\u0600-\u06ff]+", st["title_fa"]):
        c = concepts.FA.get(concepts.norm_fa(t))
        if c:
            toks["#" + c] += 3
    for line in lines:
        for t in line.split():
            s = pers_skel(t)
            if len(s) >= 2:
                toks[s] += 1
    return toks
