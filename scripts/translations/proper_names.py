#!/usr/bin/env python3
"""
Independent check on alignment quality that does not trust the reference scheme at all.

Idea: proper names survive translation. Take a source line that contains a proper name,
look at the English text the alignment assigns to it, and see whether the name is there.
A correct alignment scores high. An alignment off by a systematic offset (for example an
English-verse line number mistaken for a source line number) scores near chance.
"""
import re, unicodedata, random

GREEK = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "e", "θ": "th",
    "ι": "i", "κ": "c", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
    "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "u", "φ": "ph", "χ": "ch", "ψ": "ps",
    "ω": "o",
}

STOP = set("""the and but for with from that this than then when where who whom whose
which what while into unto upon down over under after before through against among
his her its our your their them they thee thou hath hast doth did was were been being
not nor yet all any some such more most only very much many one two three said say says
now here there thus therefore because since though although lord god king son""".split())


def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def translit(w):
    w = deaccent(w).lower()
    if re.search(r"[a-z]", w) and not re.search(r"[α-ω]", w):
        out = w
    else:
        out = "".join(GREEK.get(c, "") for c in w)
    return out


def canon(w):
    """Fold the spelling differences between a classical name and its English form."""
    w = translit(w)
    w = w.replace("j", "i").replace("v", "u").replace("k", "c").replace("y", "i")
    w = w.replace("ae", "e").replace("oe", "e").replace("ai", "e").replace("oi", "e")
    w = w.replace("ph", "f").replace("th", "t").replace("ch", "c").replace("rh", "r")
    w = re.sub(r"(us|um|os|on|es|as|is|em|am|im|ae|ai|oi|ou|o|a|e|i|u)$", "", w)
    return w


def names_in(line, lang):
    """Proper-name candidates: capitalised words that are not line-initial."""
    words = re.findall(r"\S+", line)
    out = []
    for i, w in enumerate(words):
        w = re.sub(r"^[^\wͰ-Ͽἀ-῿]+|[^\wͰ-Ͽἀ-῿]+$", "", w)
        if not w or i == 0:
            continue
        first = deaccent(w[0])
        if lang == "grc":
            cap = first in "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
        else:
            cap = first.isupper()
        if not cap or len(w) < 4:
            continue
        c = canon(w)
        if len(c) >= 4 and c not in STOP:
            out.append((w, c))
    return out


def english_stems(text):
    st = set()
    for w in re.findall(r"[A-Za-z']+", text):
        if len(w) < 4 or w.lower() in STOP:
            continue
        st.add(canon(w))
    return st


def skel(w):
    """Consonant skeleton. Vowels are what transliteration mangles
    (Mouses/Moses, Aigupt-/Egypt-, Iotor/Jethro), consonants survive, so a
    skeleton prefix is the fallback test when the vowelled prefix fails."""
    return re.sub(r"[aeiou]", "", w)


def score(pairs, lang, sample=500, seed=0):
    """pairs: [(source_line, english_text)] -> (hit_rate, n_tested)"""
    rnd = random.Random(seed)
    cand = [(s, e) for s, e in pairs if s and e]
    if len(cand) > sample * 4:
        cand = rnd.sample(cand, sample * 4)
    tested = hits = 0
    for src, eng in cand:
        ns = names_in(src, lang)
        if not ns:
            continue
        st = english_stems(eng)
        if not st:
            continue
        tested += 1
        ok = False
        for _, c in ns:
            sc = skel(c)
            for e in st:
                if e[:4] == c[:4] or (len(c) >= 5 and len(e) >= 5 and e[:5] == c[:5]):
                    ok = True
                    break
                se = skel(e)
                if len(sc) >= 3 and len(se) >= 3 and se[:3] == sc[:3]:
                    ok = True
                    break
            if ok:
                break
        hits += ok
        if tested >= sample:
            break
    return (hits / tested if tested else None), tested
