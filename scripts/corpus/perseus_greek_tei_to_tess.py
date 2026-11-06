#!/usr/bin/env python3
"""A Perseus or First1KGreek TEI edition of any shape into .tess.

Generalizes perseus_greek_history_to_tess.py (which expects book / chapter /
section) to the shapes of the 2026-10-24 Greek tranche: speech / section (Dio
Chrysostom), book / chapter / section (Diogenes Laertius, Plotinus), chapter
only (the apologists), epistle / chapter / section (Ignatius), letter /
paragraph (Julian), verse lines with no divisions (Nicander).

One .tess line is one deepest numbered division ("leaf"), cited by the
edition's own numbers joined by dots, preceded by --tag. A leaf that holds
<l n="..."> verse lines gives one line per verse line, cited by the line
number under the leaf's path. Text that stands in a division before its
sub-divisions (a preface paragraph) is a line cited by the division's path
with a final .0, the convention the earlier imports use for prefaces. A
division labelled pr, praef, arg or pref counts as 0.

Dropped: notes, critical apparatus, headings and labels, page, line and
milestone breaks, English bibliographic matter. Kept: everything else,
including editorial additions and deletions (<add>, <del>), as the earlier
Perseus imports did. A word hyphenated across a line or page break is
rejoined. Perseus's modifier-letter apostrophe and raised stop become the
plain apostrophe and colon the rest of the Greek corpus carries.

    perseus_greek_tei_to_tess.py SOURCE.xml OUT.tess --tag 'diog. laert.' \
        [--parts-dir DIR] [--min-parts 2]

--rules NAME[,NAME] applies the named cleanup rules of RULES (below) to every line after the standard
cleaning. A rule is written for one flagged work and says which in its comment.

With --parts-dir it also writes one file per top-level division named
<OUT stem>.part.<n>.tess when the edition has at least --min-parts of them
(Herodotus, Hellenica and Dio Cassius are filed this way). Prints the line
count, the Greek letters in the source body against those in the lines, and
any duplicate citation. Exits 1 on a duplicate citation, 2 when more than
1.5 percent of the Greek letters are not in any line (not checked with
--stop-before).
"""
import argparse
import collections
import os
import re
import sys
import unicodedata

from lxml import etree

SKIP = {'note', 'app', 'head', 'label', 'pb', 'milestone', 'gap', 'teiHeader'}
BREAKS = {'lb', 'pb', 'cb'}
PREFACE = {'pr', 'praef', 'arg', 'pref', 'prol', 'proem'}
GREEK = re.compile(r'[Ͱ-Ͽἀ-῿]')
SENTINEL = '\x00'


def local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def is_part(el):
    if local(el) != 'div':
        return False
    if el.get('type') == 'edition' or el.get('type') == 'translation':
        return False
    return el.get('type') == 'textpart' or el.get('subtype') is not None


def raw_text(el, stop_parts=False, out=None):
    """Text of el in document order. Skips SKIP elements (keeping tails), turns
    line and page breaks into a sentinel, and stops at sub-divisions when
    stop_parts is set (their tails are kept)."""
    out = [] if out is None else out
    if el.text:
        out.append(el.text)
    for ch in el:
        name = local(ch)
        if name is None:                      # comment or processing instruction
            pass
        elif name in BREAKS:
            out.append(SENTINEL)
        elif name in SKIP:
            pass
        elif name == 'bibl' and (ch.get('{http://www.w3.org/XML/1998/namespace}lang') or '') == 'eng':
            pass
        elif stop_parts and is_part(ch):
            pass
        else:
            raw_text(ch, stop_parts, out)
        if ch.tail:
            out.append(ch.tail)
    return out


def drop_latin_runs(text):
    """Remove a run of tokens with no Greek letter in which at least two tokens
    hold Latin letters ("Vgl. Zonar. XIII 9, 10", "a. Artemii Passio 45"): the
    German, Latin or French apparatus that the OCR left in the running text
    of some First1KGreek editions. A single Latin token is kept."""
    toks = text.split(' ')
    out, run = [], []

    def flush():
        if sum(1 for t in run if re.search('[A-Za-z]', t)) < 2:
            out.extend(run)
        run.clear()

    for t in toks:
        if GREEK.search(t):
            flush()
            out.append(t)
        else:
            run.append(t)
    flush()
    return ' '.join(out)


# ---------------------------------------------------------------------------
# Named cleanup rules, applied after the standard cleaning (--rules NAME[,NAME]).
# Added 2026-10-25 for the apparatus and heading residue found in the Greek
# tranche of 2026-10-24. Each rule says which works it was written for. None
# of them removes a whole line: a line that would lose all its Greek is kept as
# it was, so references never change.
# ---------------------------------------------------------------------------
G = '[Ͱ-Ͽἀ-῿]'
RULES = {}
ACTIVE_RULES = []


def rule(fn):
    RULES[fn.__name__] = fn
    return fn


@rule
def edition_numbers(text):
    """Section, verse, footnote and line numbers of the edition left in the text of a line.

    Written for Athanasius Contra Arianos I to III, Ignatius, Enoch, Nicander (Theriaca, Alexipharmaca),
    Dio Chrysostom, Diogenes Laertius, Longus, Plotinus, Clement of Rome II and Origen on John.
    A Roman numeral heading is taken off the front of a line only when it is made of X, I, V and L.
    """
    text = re.sub(r'\(\d+\.?\)', ' ', text)                                  # "(1.)" "(16.)": a marginal footnote number
    text = re.sub(r'^[A-Z][a-z]{1,3}\.\s*\d+,\s*\d+(?=\S)', '', text)         # "Mt. 7, 21Μὴ": a Bible reference at the head (Clement II 4.1)
    text = re.sub(r'^\d+[a-zα]?(?:[.,]"?\s*(?=[^\d\s])|(?=[^\d\s.,]))[¹²³⁴⁵⁶⁷⁸⁹⁰]*', '', text)   # "29." "4."" "1, " "3Καὶ" "64ἢ" "1¹καὶ": the number of the section or verse
    text = re.sub('^[¹²³⁴⁵⁶⁷⁸⁹⁰\\d]+\\s*(?=' + G + ')', '', text)                  # "¹7τὸ": a verse number with a superscript footnote mark
    text = re.sub(r'^[XΧIΙVL]{2,}\.?\s+(?=' + G + ')', '', text)               # "ΧΧVII Ὥσπερ"
    text = re.sub(r"(?<=[Ͱ-Ͽἀ-῿.:;,·'])\s*\d+$", '', text)                    # "πνιχμὸς 190", ". 6": a verse or line number at the end
    text = re.sub(r'(?<=[;:.,?])\d+(?=\s+' + G + ')', '', text)               # "ἀνομίας;6 Ὁ"
    text = re.sub('(?<=' + G + ')%?\\d+(?=' + G + ')', ' ', text)              # "Ἕλληνας2καὶ"
    text = re.sub('(?<=' + G + ')%?\\d+(?=[;:.,]?(?:\\s|$))', '', text)         # "ἥττονες1;" "ἐκείνῳ%5,"
    text = re.sub('(?<=\\s)\\d+(?=' + G + ')(?![αβγδ]\\.)', '', text)           # " 3μέσου"
    return text


@rule
def stray_angle_marks(text):
    """A ">" with no "<" in its line is not an editorial bracket (those come in pairs, <supplied words>): it is the mark
    the OCR took from the print's line starts. Theodoret has about 2,100 of them ("Ἀλέξανδρος >ἐν κυρίῳ"), Philostorgius,
    Dio Chrysostom, Anna Comnena and Diogenes Laertius a few. Inside a word it is dropped, between words it is a space."""
    if '<' in text:
        return text
    text = re.sub('(?<=' + G + ')>(?=' + G + ')', '', text)
    return text.replace('>', ' ')


@rule
def ignatius_sections(text):
    """Ignatius, Epistles: the edition's section numbers inside a line ("πατρός, 2, εἰ γὰρ ἦσαν")."""
    return re.sub('(?<=\\s)\\d+,\\s+(?=' + G + ')', '', text)


@rule
def dio_citation(text):
    """Dio Chrysostom, Oration 2.63: a reference to Bergk's Poetae Lyrici Graeci printed inside the quotation marks."""
    return re.sub(r"ʽ[^ʽ'’ʼ]*\d+['’ʼ]\s*", '', text)


@rule
def origen_john(text):
    """Origen, Commentary on John: the edition's lemma references ("VIII, 20.", "II, 14-17", "1, 1."), folio marks
    ("114r"), and the "x003E;" left by an unread character entity for the editor's angle bracket."""
    text = re.sub(r'x00[0-9A-F]{2}E?;', ' ', text)
    text = re.sub(r'(?<!\S)\d+[rv](?!\S)', ' ', text)
    text = re.sub(r'\bJohn\s+\d+(?:[.,]\s*\d+)?\.?', ' ', text)                  # "John 11.27" printed before a lemma
    text = re.sub(r'(?<![\w])(?:[XΧIΙVL]+|\d+),\s*\d+(?:\s*[-–]\s*\d+)?\s*(?:ff?\.)?[.,]?(?=\s+[Ͱ-Ͽἀ-῿»‘ʼ’\'"])', ' ', text)
    text = re.sub(r'(?<![\w])(?:[XΧIΙVL]+|\d+),(?=\s+[Ͱ-Ͽἀ-῿»‘ʼ’\'"])', ' ', text)        # a lemma reference whose verse the bracket rule had already taken
    text = re.sub(r'(?<=\s)\d{1,3}\](?=\s)', ' ', text)
    text = re.sub(r'(?<=\s)\d{1,3}(?=\s)', ' ', text)                       # "τῇ 1 πρὸς", "15 καὶ": a verse or footnote number between words
    text = re.sub('(?<=[Ͱ-Ͽἀ-῿])-\\d+\\s+(?=' + G + ')', '', text)         # "κατα-15 παύσωμεν": a line number after the hyphen of a split word
    return text


@rule
def anna_comnena(text):
    """Anna Comnena, Alexias: the running header ΑΛΕΞΙΑΣ and the margin marks of the print (V. 7, P. 87, B, C, D, line
    numbers 15 20 25) that the OCR set between words, and apparatus words such as "ad", "post", "scripsi"."""
    if text.startswith('ARGUMENT'):
        return text                      # the heading lines x.0 hold nothing else; removing them would change references
    text = re.sub('(?<![Ͱ-Ͽἀ-῿])ΑΛΕΞΙΑΣ(?![Ͱ-Ͽἀ-῿])', ' ', text)
    return apparatus_runs(text)


@rule
def apparatus_runs_rule(text):
    """Philostorgius (Bidez's apparatus and sigla: Phot., Suid., Zonar., Vgl., Ebd., "näml." supplements) and Theodoret
    (Parmentier's German apparatus): drop every run of tokens that has no Greek letter and holds a Latin letter or a digit."""
    text = re.sub(r'\(\s*näml\.[^)]{0,60}\)', ' ', text)      # the editor's "(näml. ὁ Κωνστντῖνος)"; a longer stretch keeps its text
    text = re.sub(r'(?<=\s)\d+[αβγδ]\.(?=\s)', ' ', text)    # "2α." a paragraph number set inside the line
    text = re.sub(r'(?<=\s)\d+>(?=\S)', '', text)             # Theodoret "5>ἰδίας": a line number with the apparatus bracket
    text = re.sub(r'Ζonar\.', ' ', text)                        # Philostorgius 2.16b: "Zonar." written with a Greek Zeta
    return apparatus_runs(text)


def apparatus_runs(text):
    """Remove each maximal run of tokens with no Greek letter in which at least one token holds a Latin letter or a
    digit ("Phot.", "V. 7", "Ebd. 45 :", "§ 11]", a lone "B"). A run of punctuation alone is kept."""
    toks = text.split(' ')
    out, run = [], []

    def flush():
        if not any(re.search('[A-Za-z0-9]', t) for t in run):
            out.extend(run)
        run.clear()

    for t in toks:
        if re.search(G, t):
            flush()
            out.append(t)
        else:
            run.append(t)
    flush()
    return ' '.join(x for x in out if x != '')


def clean(pieces):
    text = ''.join(pieces)
    text = re.sub(r'\d*[-‐¬]\s*' + SENTINEL + r'\s*', '', text)   # rejoin a hyphenated word
    text = text.replace(SENTINEL, ' ')
    text = unicodedata.normalize('NFC', re.sub(r'\s+', ' ', text)).strip()
    text = re.sub(r'(?<=[Ͱ-Ͽἀ-῿])\?(?=[Ͱ-Ͽἀ-῿])', '', text)
    # Editorial matter the First1KGreek OCR left in the running text: a bracket
    # holding any Latin letter or digit ("[cf. Ps. CXVIII, 1]", "[fol. 57]",
    # "[I.]"), a run of asterisks marking a lacuna, a stray bar.
    text = re.sub(r'\[[^\]]*[A-Za-z0-9][^\]]*\]', ' ', text)
    text = re.sub(r'\*', ' ', text).replace('|', ' ')
    text = drop_latin_runs(text)
    text = re.sub(r'^\d+[a-z]?\.?\s+(?=[^\d\s])', '', text.strip())     # a paragraph number the edition printed in the text
    # An elision written as a psili (U+1FBF), or as a combining coronis left
    # standing after a consonant, is the plain apostrophe of the corpus.
    text = text.replace('᾿', "'")
    text = re.sub('(?<=[β-δζθκ-ξπ-τφ-ψ])̓', "'", text)
    text = unicodedata.normalize('NFC', re.sub(r'\s+', ' ', text)).strip()
    for name in ACTIVE_RULES:
        cleaned = re.sub(r'\s+', ' ', RULES[name](text)).strip()
        text = cleaned if GREEK.search(cleaned) or not GREEK.search(text) else text   # never empty a line of its Greek
    return (text.replace('ʼ', "'").replace('’', "'")
                .replace('᾽', "'").replace('·', ':'))


def label(n):
    return '0' if n in PREFACE else n


def walk(el, path, rows):
    parts = [c for c in el if is_part(c)]
    verse = [d for d in el.iter() if local(d) == 'l']
    if not parts and verse:
        # Verse mode only when the leaf is verse. A prose division that quotes
        # an epigram in <l> (Diogenes Laertius) stays one prose line.
        in_l = sum(len(GREEK.findall(clean(raw_text(ln)))) for ln in verse)
        if in_l < 0.8 * len(GREEK.findall(clean(raw_text(el)))):
            verse = []
    if not parts and verse:
        counter = 0
        for ln in verse:
            n = ln.get('n')
            if n is None or not n.strip():
                counter += 1
                n = str(counter)
            else:
                counter = int(n) if n.isdigit() else counter
            text = clean(raw_text(ln))
            if text:
                rows.append((path + [n], text))
        return
    if not parts:
        text = clean(raw_text(el))
        if text and path:
            rows.append((path, text))
        return
    lead = clean(raw_text(el, stop_parts=True))
    if lead and path:
        rows.append((path + ['0'], lead))
    for c in parts:
        walk(c, path + [label(c.get('n', '?'))], rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source')
    ap.add_argument('out')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--parts-dir')
    ap.add_argument('--min-parts', type=int, default=2)
    ap.add_argument('--rules', default='', help='comma-separated names from RULES, applied to every line after cleaning')
    ap.add_argument('--drop-top', nargs='*', default=[], help='top-level divisions to leave out (an appendix)')
    ap.add_argument('--stop-before', help='cite, without the tag, of the first line to leave out '
                    'along with everything after it')
    args = ap.parse_args()
    ACTIVE_RULES[:] = [n for n in args.rules.split(',') if n]
    for n in ACTIVE_RULES:
        if n not in RULES:
            sys.exit(f'unknown rule {n}')

    tree = etree.parse(args.source, etree.XMLParser(recover=True, huge_tree=True))
    body = tree.getroot().find('.//{*}body')
    edition = next((d for d in body.iter() if local(d) == 'div' and d.get('type') == 'edition'), body)
    rows = []
    walk(edition, [], rows)
    if not any(r[0] for r in rows):
        sys.exit('no citable divisions found')

    # Verse with no divisions has path [n]; prose leaves have longer paths.
    rows = [(p, t) for p, t in rows if GREEK.search(t) and p[0] not in args.drop_top]
    if args.stop_before:
        keep = []
        for p, t in rows:
            if '.'.join(p) == args.stop_before:
                break
            keep.append((p, t))
        print(f'stopped before {args.stop_before}: kept {len(keep)} of {len(rows)} lines')
        rows = keep
    lines = [(f'{args.tag} ' + '.'.join(p), t) for p, t in rows]
    refs = [r for r, _ in lines]
    dups = [r for r, c in collections.Counter(refs).items() if c > 1]

    def letters(s):
        return len(GREEK.findall(s))

    src = clean(raw_text(body)) if body is not None else ''
    src_letters = letters(src)
    out_letters = sum(letters(t) for _, t in lines)
    ratio = out_letters / src_letters if src_letters else 0
    print(f'{len(lines)} lines; Greek letters in source body {src_letters}, in lines {out_letters} ({ratio:.4f}); '
          f'duplicate citations {len(dups)}')
    for d in dups[:10]:
        print('  DUPLICATE', d)

    with open(args.out, 'w', encoding='utf-8', newline='') as fh:
        for ref, text in lines:
            fh.write(f'<{ref}>\t{text}\n')

    if args.parts_dir:
        by_top = collections.OrderedDict()
        for (p, _), (ref, text) in zip(rows, lines):
            by_top.setdefault(p[0], []).append((ref, text))
        if len(by_top) >= args.min_parts and any(len(p) > 1 for p, _ in rows):
            stem = os.path.basename(args.out)[:-5]
            for b, rs in by_top.items():
                path = os.path.join(args.parts_dir, f'{stem}.part.{b}.tess')
                with open(path, 'w', encoding='utf-8', newline='') as fh:
                    for ref, text in rs:
                        fh.write(f'<{ref}>\t{text}\n')
                print(f'  part {b}: {len(rs)} lines -> {os.path.basename(path)}')
    if dups:
        sys.exit(1)
    if ratio < 0.985 and not args.stop_before and not args.drop_top:
        print('WARNING: more than 1.5% of the Greek is not in any line', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
