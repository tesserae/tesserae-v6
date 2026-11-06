#!/usr/bin/env python3
"""Find our references inside a Loeb scan by their own text (Part F, 2026-10-24).

For prose whose running headers carry chapter or section numerals that OCR
reads badly (Pliny: "BOOK VIII. xvi. 40-xvii. 42"), the Latin on the facing page
is a better address than any numeral: it is the text our own .tess holds. The
scan is split into spreads (a source-language page followed by its English
page), each reference of ours is located in the source-language pages by a
normalized probe of its opening words, walked in order so a probe can only be
found after the previous reference, and a reference gets the English pages from
the one under its opening to the one under the opening of the next reference.

The position is checked afterwards by the same two measured checks every
pipeline uses (proper names, and the length of a unit against the length of the
source it claims to translate).
"""
import re
import unicodedata


GREEK_MODE = False


def norm(s):
    """Letters only, without accents: Latin folded (j to i, v to u) or, when
    GREEK_MODE is set for a Greek work, the Greek letters alone (final sigma folded)."""
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    if GREEK_MODE:
        return re.sub(r'[^α-ω]', '', s.replace('ς', 'σ'))
    s = s.replace('j', 'i').replace('v', 'u').replace('æ', 'ae')
    return re.sub(r'[^a-z]', '', s)


def spreads(lines, is_src_head, is_eng_head, is_title=None):
    """[{'src': [lines], 'eng': [lines]}] in page order.

    A book's opening pages (a source page and an English page) carry no running
    header, only the book's bare title, usually under the series header. The
    first such page starts a spread and the second switches it to English.
    """
    out, cur, mode = [], None, None
    n = len(lines)
    for i, raw in enumerate(lines):
        s = re.sub(r'\s+', ' ', raw.strip())
        opening = False
        if is_title:
            if is_title(s):
                opening = True
            elif is_src_head(s):
                for j in range(i + 1, min(n, i + 8)):
                    t = re.sub(r'\s+', ' ', lines[j].strip())
                    if t:
                        opening = is_title(t)
                        break
                if opening:
                    continue          # the title line itself comes next
        if opening:
            if cur is not None and mode == 'src' and any(x.strip() for x in cur['src']):
                mode = 'eng'
            else:
                if cur:
                    out.append(cur)
                cur, mode = {'src': [], 'eng': []}, 'src'
            continue
        if is_src_head(s):
            if cur:
                out.append(cur)
            cur, mode = {'src': [], 'eng': []}, 'src'
            continue
        if is_eng_head(s):
            if cur is None or mode == 'eng':
                # an English page whose source page header was lost
                if cur:
                    out.append(cur)
                cur = {'src': [], 'eng': []}
            mode = 'eng'
            continue
        if cur is not None:
            cur[mode].append(raw)
    if cur:
        out.append(cur)
    return out


def locate(refs_in_order, spreads_, probe=22, window=90000):
    """{ref: first spread index} by walking the refs in order.

    refs_in_order: [(ref, source_text)]. Returns (found, missed).
    """
    big, starts = [], []
    pos = 0
    for i, sp in enumerate(spreads_):
        t = norm(' '.join(sp['src']))
        starts.append(pos)
        big.append(t)
        pos += len(t)
    text = ''.join(big)

    def page_of(off):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def probe_at(n, lo, hi, unique):
        for k in range(0, min(len(n) - probe, probe * 4) + 1, probe // 2):
            seg = n[k:k + probe]
            if len(seg) < probe:
                break
            j = text.find(seg, lo, hi)
            if j >= 0 and (not unique or text.find(seg, j + 1) < 0):
                return max(lo, j - k), j
        return None

    found, missed, cursor = {}, [], None
    chain = []          # candidate opening refs, trusted once three agree in order

    def commit(ref, hit):
        pg = page_of(hit)
        found[ref] = (pg, (hit - starts[pg]) / max(1, len(big[pg])))

    for ref, src in refs_in_order:
        n = norm(src)
        if cursor is None:
            # not yet inside this volume: only a probe that occurs once counts, and
            # three refs in a row must follow each other before the walk begins
            r = probe_at(n, chain[-1][1] if chain else 0, len(text), True)
            if r and (not chain or r[0] - chain[-1][1] < window):
                chain.append((ref, r[0]))
                if len(chain) >= 3:
                    for cref, chit in chain:
                        commit(cref, chit)
                    cursor = chain[-1][1]
            else:
                missed.append(ref)
                chain = []
            continue
        r = probe_at(n, cursor, cursor + window, False)
        if r is None:
            missed.append(ref)
            continue
        commit(ref, r[0])
        cursor = r[0]
    return found, missed
