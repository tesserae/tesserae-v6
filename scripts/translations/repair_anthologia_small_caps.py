#!/usr/bin/env python3
"""Repair the first words that the Loeb's small capitals left garbled in the aligned
Greek Anthology files ("TuereE" for There, "Tue" for The, "ImaGInE" for Imagine).

BACKGROUND. Every Loeb translation opens in small capitals. This OCR reads some of them
as lower-case letters (H as u, D as p, F as r), keeps others as capitals, and sometimes
doubles a letter. The 2026-09-10 install repaired 512 first words with the table
FIRST_WORD_REPAIRS in align_anthologia_graeca.py, which only sees the very first word of
a unit. In the staged files of 2026-10-24 about a quarter of the units still opened with a
garbled word, most of them after a heading ("On the Same TuereE ...").

WHAT THIS DOES, on the first eight words of a unit only:
  1. the fixed table (the 2026-09-10 one, plus the words found since) applies to any of
     those words, not only the first, because the heading in front of the word is the reason
     it was missed;
  2. a word with capitals in the middle ("PaLias", "sTRANGER", "OnE") is put back into
     ordinary case. If its lower-case form is an English word the corpus itself uses
     (counted over the body of all the units, at least three times) that is all it needs.
     If not, the OCR's usual confusions are undone (u for h, p for d, r for f, a doubled
     letter) and the result is accepted only if it is a word the corpus uses at least
     ten times, at a cost of at most two repairs. A proper name that matches no such word keeps
     its letters and only has its case repaired;
  3. an all-capital word that is an ordinary English word ("WE", "TELL") is put into ordinary case.
Every change is written to the log with its unit, so the list can be read.

Usage:
    python repair_anthologia_small_caps.py LOG.tsv FILE.json [FILE.json ...]
(the files are rewritten in place, so work on staged copies and rebuild their checksums).
"""
import json
import re
import sys
from collections import Counter

# the 2026-09-10 table and the words found since, each confirmed from its own sentence
TABLE = {
    'Tue': 'The', 'Wuen': 'When', 'Ir': 'If', 'Tuis': 'This', 'Tuou': 'Thou',
    'Wuart': 'What', 'Wuo': 'Who', 'Tuus': 'Thus', 'Wuy': 'Why',
    'Wuere': 'Where', 'Wuether': 'Whether', 'Tuese': 'These', 'Tuere': 'There',
    'Tuey': 'They', 'Tuen': 'Then', 'Wuile': 'While',
    'Tuts': 'This', 'Tus': 'This', 'Sue': 'She', 'Buest': 'Blest',
    'Wuite': 'White', 'Guarpian': 'Guardian', 'Wueruer': 'Whether',
    'Wuertuer': 'Whether',
    # found in the staged files of 2026-10-24
    'Ar': 'At', 'Hai': 'Hail', 'orpERED': 'ordered',
    # garbles the confusion search cannot reach, each read from its own sentence
    'TueE': 'The', 'PaLtas': 'Pallas', 'PaLias': 'Pallas', 'ImaGInE': 'Imagine',
    'TremBe': 'Tremble', 'AsouT': 'About', 'SitenT': 'Silent', 'WnrN': 'When',
    'puysiciaNn': 'physician', 'sNEEzZED': 'sneezed', 'sHortT': 'short', 'uTT': 'little',
    'uiTTLE': 'little', 'cavauT': 'caught', 'tamENT': 'lament', 'eLogueNce': 'eloquence',
    'macpIE': 'magpie', 'rerryMaAN': 'ferryman', 'WiwcED': 'Winged', 'BnavELv': 'Bravely',
    'CrLEoBULUs': 'Cleobulus', 'YestTerDay': 'Yesterday', 'FortTunaTe': 'Fortunate',
    'ConstTantinus': 'Constantinus', 'RemMemBer': 'Remember', 'ProtTomacuus': 'Protomachus',
    'TxHouau': 'Though', 'GrammMarians': 'Grammarians', 'MournFut': 'Mournful',
    'SonE': 'Some', 'SuHameE': 'Shame', 'amI': 'am I', 'THovu': 'Thou', 'trxHou': 'thou',
    'NeirHer': 'Neither', 'WayrareER': 'Wayfarer', 'WayrareEr': 'Wayfarer',
    'WickepestT': 'Wickedest', 'pETEsT': 'detest', 'SrRANGER': 'Stranger', 'lIoannes': 'Ioannes',
    'SatyraA': 'Satyra', 'CurisT': 'Christ', 'EKurystheus': 'Eurystheus',
    'PnaxrrELES': 'Praxiteles', 'PnaxrrELEs': 'Praxiteles', 'PuiLocLESs': 'Philocles',
    'PnuiLocLEs': 'Philocles', 'CuarEREMON': 'Chaeremon', 'CuarINus': 'Charinus',
    'DiorpHanTus': 'Diophantus',
    # Th and Wh and Ch read as Tu, Tur, Tx, Wu, Wn, Cu (read from their sentences)
    'Tuy': 'Thy', 'Tuovu': 'Thou', 'Tuov': 'Thou', 'Tuouen': 'Though', 'Tuovau': 'Though',
    'Tuoucu': 'Though', 'Txoueu': 'Thou', 'Txuov': 'Thou', 'Txou': 'Thou',
    'Turovuen': 'Through', 'Turow': 'Throw', 'Turee': 'Three', 'Turice': 'Thrice',
    'Wuat': 'What', 'Wuar': 'What', 'Wnuar': 'What', 'Wnuo': 'Who', 'Wuetuer': 'Whether',
    'Wuerg': 'Whence', 'Wuire': 'While', 'Wuew': 'When', 'Tuery': 'They', 'Tury': 'They',
    'Turse': 'These', 'Tuesr': 'These', 'Turis': 'This', 'Turs': 'This', 'Tunis': 'This',
    'Tug': 'The', 'Tun': 'The', 'Tur': 'The', 'Tuar': 'That', 'Tuer': 'There', 'Turre': 'There',
    'Tuemis': 'Themis', 'Tuyrsis': 'Thyrsis', 'Cuitp': 'Child', 'Cuares': 'Chares',
    'Cuaron': 'Charon', 'Cuarmus': 'Charmus', 'Curysippus': 'Chrysippus',
    'Aas': 'Alas', 'fue': 'The', 'Maipen': 'Maiden', 'Ler': 'Let', 'stanp': 'stand',
}
# the words of the 2026-09-10 table that are not English words at all, so they are
# safe to repair anywhere in a unit and not only among its first words
IT_NEXT = {'is', 'was', 'has', 'hath', 'seems', 'came', 'will', 'cannot'}
EVERYWHERE = {'Tue', 'Wuen', 'Tuis', 'Tuou', 'Wuart', 'Wuo', 'Tuus', 'Wuy', 'Wuere', 'Wuether',
              'Tuese', 'Tuere', 'Tuey', 'Tuen', 'Wuile', 'Tuts', 'Tus', 'Wuite', 'Wueruer',
              'Wuertuer'}
# what the OCR wrote for the letter on the right
CONFUSED = {'u': 'h', 'p': 'd', 'r': 'f', 'n': 'h', 'c': 'e', 'x': ''}
WORD = re.compile(r"[A-Za-z]+")


def odd_case(w):
    """Capitals after the first letter mixed with lower case: PaLias, sTRANGER, OnE."""
    return len(w) > 1 and any(c.isupper() for c in w[1:]) and any(c.islower() for c in w) \
        and not (w[0].isupper() and w[1:].islower())


def vocabulary(files):
    cnt = Counter()
    for f in files:
        for u in json.load(open(f, encoding='utf-8'))['units']:
            toks = WORD.findall(u)
            for w in toks[8:]:
                if w.islower() and len(w) >= 3:
                    cnt[w] += 1
    return cnt


def variants(base):
    """(cost, word) the OCR's usual confusions could turn `base` back into."""
    out = {base: 0}
    frontier = {base: 0}
    for _ in range(2):
        nxt = {}
        for w, c in frontier.items():
            for i, ch in enumerate(w):
                if ch in CONFUSED:
                    nxt.setdefault(w[:i] + CONFUSED[ch] + w[i + 1:], c + 1)
                if i and ch == w[i - 1]:
                    nxt.setdefault(w[:i] + w[i + 1:], c + 1)     # a doubled letter
        for w, c in nxt.items():
            if w not in out or out[w] > c:
                out[w] = c
        frontier = nxt
    return out


def repair_unit(u, vocab, log):
    allw = list(WORD.finditer(u))
    spans = allw[:8] + [m for m in allw[8:] if m.group(0) in EVERYWHERE]
    new, last = [], 0
    for m in spans:
        w = m.group(0)
        r = None
        nxt = re.match(r"\s+([A-Za-z]+)", u[m.end():])
        if w in ('Ir', 'If'):
            # the OCR reads both It and If as Ir (and the first-word table made every Ir an
            # If); the word after it says which. "If is" is not English.
            r = 'It' if nxt and nxt.group(1).lower() in IT_NEXT else 'If'
        elif w == 'Tuouau':
            r = 'Thou' if u[m.end():m.end() + 1] == ',' else 'Though'
        elif w in TABLE:
            r = TABLE[w]
        elif odd_case(w):
            base = w.lower()
            if vocab[base] >= 3:
                r = base
            else:
                best = None
                for v, c in variants(base).items():
                    if c and len(v) >= 3 and vocab[v] >= 10:
                        key = (c, -vocab[v])
                        if best is None or key < best[0]:
                            best = (key, v)
                r = best[1] if best else base
            r = r.capitalize() if w[0].isupper() else r
        elif w.isupper() and len(w) >= 2 and vocab[w.lower()] >= 10:
            r = w.capitalize()
        if r is not None and r != w:
            log.append((w, r, u[:70]))
            new.append(u[last:m.start()] + r)
            last = m.end()
    new.append(u[last:])
    return ''.join(new)


def main():
    logf, files = sys.argv[1], sys.argv[2:]
    vocab = vocabulary(files)
    log = []
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        before = len(log)
        d['units'] = [repair_unit(u, vocab, log) for u in d['units']]
        json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f, 'repaired words:', len(log) - before)
    with open(logf, 'w', encoding='utf-8') as fh:
        for w, r, ctx in log:
            fh.write(f'{w}\t{r}\t{ctx}\n')
    print('total words repaired:', len(log))


if __name__ == '__main__':
    main()
