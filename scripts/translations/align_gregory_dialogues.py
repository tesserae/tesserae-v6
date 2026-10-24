#!/usr/bin/env python3
"""Gregory the Great, Dialogues, in the English of 1608 as edited by E. G. Gardner (1911).

Source: Internet Archive dialoguesofsaint00greg (OCR text). The book is
"The Dialogues of Saint Gregory, surnamed the Great, Pope of Rome and the first of
that name, translated into English by P. W. (1608), edited with an introduction and
notes by Edmund G. Gardner (London: Philip Lee Warner, 1911)". The translation is
early seventeenth century and the edition 1911, both public domain.

THE SCAN IS BLACKLETTER. The 1911 reprint is set in the 1608 black letter, and the
OCR reads it badly: "Chapter Two" arrives as "Ctoo", "Chapter Three" as "Cftree",
and about one chapter heading in five is lost altogether. So chapter numbers cannot
be read, and counting headings would drift.

METHOD. Within each book the detected chapter headings are numbered by a monotone
fit: each heading's number-word is compared (letter similarity, after undoing the
commonest blackletter confusions) with the number words, and the numbers are chosen
to increase through the book while matching the words as well as possible. A heading
the scan lost is simply a gap in the numbers, and the English block before the next
heading is then assigned to every one of our chapters in the gap (one coarse unit,
not a wrong one). The number of chapters per book is taken from our own file.

Our references are book.chapter.section ("greg. dial. 2.8.3"), so a chapter's English
is stored once and every section ref of the chapter points at it. The four prologues
(1.pr and so on) are left unpaired.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_common as C

SRC_FILE = os.path.join(C.SRC, 'dialoguesofsaint00greg.txt')
# 0-based line index of each book's chapters in the scan. Book 4 is NOT aligned:
# our Latin ends at chapter 60 while the English runs to 62 chapters, so the two
# numberings disagree (the spec's report-don't-improvise rule). The counts are
# printed by --show-book4.
BOOKS = [(1, 1507, 3408), (2, 3408, 5694), (3, 5694, 8850)]
BOOK4 = (4, 8850, 12575)
HEAD = re.compile(r'^\W{0,5}C\S{1,4}(?:apter|mpter|pter)\b')
WORDS = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
         'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
TENS = {20: 'twenty', 30: 'thirty', 40: 'forty', 50: 'fifty', 60: 'sixty'}


def number_word(n):
    if n < 20:
        return WORDS[n - 1]
    t, u = divmod(n, 10)
    return TENS[t * 10] + (WORDS[u - 1] if u else '')


def garble(tok):
    """Undo the commonest blackletter misreadings in a number word."""
    t = tok.lower()
    t = re.sub(r'^\W*c', '', t)                       # the C of Chapter's capital-C spill
    t = t.replace('f)', 'h').replace('tfj', 'th').replace('t&', 'th').replace('tb', 'th').replace('t)', 'th')
    t = t.replace('to', 'w').replace('oo', 'o')
    return re.sub(r'[^a-z]', '', t)


def sim(tok, n):
    a = garble(tok)
    b = number_word(n).replace('oo', 'o')
    b = b.replace('tw', 'w')
    return difflib.SequenceMatcher(None, a, b).ratio()


def number_headings(tokens, nmax):
    """Choose strictly increasing chapter numbers maximizing total similarity."""
    k = len(tokens)
    NEG = -1e9
    best = [[NEG] * (nmax + 1) for _ in range(k)]
    back = [[0] * (nmax + 1) for _ in range(k)]
    for n in range(1, nmax + 1):
        best[0][n] = sim(tokens[0], n) - 0.01 * (n - 1)
    for i in range(1, k):
        run, arg = NEG, 0
        for n in range(1, nmax + 1):
            if n - 1 >= 1 and best[i - 1][n - 1] > run:
                run, arg = best[i - 1][n - 1], n - 1
            if run > NEG:
                best[i][n] = run + sim(tokens[i], n) - 0.01 * 0       # gaps cost nothing extra
                back[i][n] = arg
    n = max(range(1, nmax + 1), key=lambda x: best[k - 1][x])
    out = [n]
    for i in range(k - 1, 0, -1):
        n = back[i][n]
        out.append(n)
    return out[::-1]


def clean_block(lines, first=False):
    keep = []
    for ln in lines:
        t = re.sub(r'[ \t]+', ' ', ln).strip()
        if not t:
            keep.append('')
            continue
        if re.match(r'^\d{1,3}$', t) or re.search(r'Dialogues of St', t) or C.english_score(t) < 0.05 and len(t) < 40:
            continue
        keep.append(t)
    return keep


def split_heading(block):
    """Drop the chapter's title lines, which the scan reads as blackletter noise.
    A title runs to the first blank line, unless the body follows on the same line
    after a pilcrow the scan renders as <& or ^."""
    i = 0
    while i < len(block) and not block[i]:
        i += 1
    j = i
    while j < len(block) and block[j]:
        j += 1
    head = block[i:j]
    rest = block[j:]
    for k, ln in enumerate(head):
        m = re.search(r'\s(?:<&|<\{&|&\s|\^|¶|§)\s+(?=[A-Z"“])', ln)
        if m:
            return [ln[m.end():]] + head[k + 1:] + rest
    return rest


def main():
    raw = open(SRC_FILE, encoding='utf-8', errors='replace').read().split('\n')
    tl = C.load_tess(os.path.join(C.TEXTS, 'la', 'gregorius_magnus.dialogi.tess'))
    chap_refs = {}          # (book, chapter) -> [refs]
    for ref, _ in tl:
        m = re.search(r'(\d+)\.(\d+)\.(\d+)\s*$', ref)
        if m:
            chap_refs.setdefault((int(m.group(1)), int(m.group(2))), []).append(ref)
    mapping = {}
    for book, lo, hi in BOOKS:
        nmax = max(c for (b, c) in chap_refs if b == book)
        idx = [i for i in range(lo, hi) if HEAD.match(re.sub(r'[ \t]+', ' ', raw[i]))]
        toks = []
        for i in idx:
            t = re.sub(r'[ \t]+', ' ', raw[i]).strip()
            tok = re.sub(r'^\W*\S+\s*', '', t)
            tok = re.split(r'[:;]|\s{1}(?:of|how|that|bow|boto|fjoto|tbat|&oto|bote)\b', tok)[0].strip().split(' ')[0] if tok else ''
            toks.append(tok or 'x')
        nums = number_headings(toks, nmax)
        print(f'book {book}: {len(idx)} headings of {nmax} chapters; numbers {nums[:6]}...{nums[-4:]}')
        bounds = idx + [hi]
        for k, i in enumerate(idx):
            lines = clean_block(raw[i:bounds[k + 1]])
            block = split_heading(lines)
            text = C.clean_english(block)
            text = re.sub(r'\s+', ' ', text)
            # words the scan made of blackletter capitals and ornaments ("3t)t)Cp.")
            text = ' '.join(w for w in text.split(' ') if not re.search(r'[)\u00a3$@^<>{}|\\\u00a7]', w)
                            and not re.search(r'[A-Za-z]\d|\d[A-Za-z]', w)
                            and not re.search(r'[a-z][A-Z]', w))
            if len(text) < 80:
                continue
            first = nums[k]
            last = (nums[k + 1] - 1) if k + 1 < len(nums) else nmax
            for c in range(first, last + 1):
                for ref in chap_refs.get((book, c), []):
                    mapping.setdefault(ref, text)
    source = {'translator': 'P. W.', 'year': 1608, 'editor': 'Edmund G. Gardner (1911)',
              'edition_year': 1911, 'place': 'London', 'publisher': 'Philip Lee Warner (Medici Society)',
              'title': 'The Dialogues of Saint Gregory, surnamed the Great, translated into English by P. W. 1608, '
                       'edited by Edmund G. Gardner',
              'license': 'public domain', 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
              'url': 'https://archive.org/details/dialoguesofsaint00greg',
              'source_url': 'https://archive.org/details/dialoguesofsaint00greg'}
    # per-book name check, so a book that disagrees cannot hide inside the total
    import proper_names as V
    src_of = {}
    for ref, t in tl:
        src_of.setdefault(ref, t)
    for book, _, _ in BOOKS:
        pairs = [(src_of[r], t) for r, t in mapping.items() if re.search(r'\s%d\.' % book, r)]
        hit, n = V.score(pairs, 'la', sample=300)
        print(f'  book {book}: paired {len(pairs)} refs, names {hit if hit is None else round(hit, 3)} (n={n})')
    row = C.finish('gregorius_magnus.dialogi', 'la', tl, mapping, source,
                   'Public domain: translation of 1608, edition of 1911 (London: Philip Lee Warner).',
                   'Internet Archive')
    C.save_report('gregory', [row])


if __name__ == '__main__':
    main()
