#!/usr/bin/env python3
"""Anonymous, Origo Gentis Romanae: the 2004 collaborative translation
published on tertullian.org (ed. Roger Pearse), aligned to the corpus text
`texts/la/pseudo_aurelius_victor.origo_gentis_romanae.tess`.

SOURCE: https://www.tertullian.org/fathers/origo_01_trans.htm (the single
translation page; introduction at origo_00_intro.htm). The intro page
states "All material on this page is in the public domain - copy freely."
Pearse's own site-wide policy page extends that to the translation pages
themselves; this script treats the fetched HTML as a straight public-domain
source and does not re-derive that judgement.

LAYOUT: one HTML page. An opening, unnumbered paragraph (the dedication
sentence naming Verrius Flaccus, Livy, etc.) precedes chapter "I.". Each
chapter opens with `<SPAN class="chapterno"><A NAME="C<n>"></A><roman>.`
and each subsection with `<SPAN class="verse"><A NAME="<n>_<m>"></A>[<m>]`.
Inline footnote markers are `<A HREF="#N"><SUP>N</SUP></A>` and are
stripped from the running text; the translators' own "Comments and
discussion" apparatus after section 23.6 is cut entirely (it is marginal
commentary, not the translation).

ALIGNMENT: the corpus's own Latin transcription (The Latin Library, via
`scripts/corpus/latinlibrary_to_tess.py`) numbers sections 1:1 with this
translation in every chapter except three places, where the corpus's
single numbered Latin line visibly carries the content of TWO of this
translation's numbered sections (checked by reading both: the Latin line
runs on past where the first English section ends and into the content of
the next). Those three merges are listed explicitly below rather than
inferred, because inference over a gap this small (three places in 126
refs) is more likely to hide a mistake than catch one:

  - 3.7   <- translation sections 3.[7] + 3.[8]
  - 4.3   <- translation sections 4.[3] + 4.[4]  (corpus has no 4.4 at all)
  - 5.3   <- translation sections 5.[3] + 5.[4]

Every other corpus ref maps to the translation section of the same number.
The preface line `pr.1` maps to the page's opening unnumbered paragraph.

Usage:
    python scripts/translations/align_origo.py \
        --html <local copy of origo_01_trans.htm> \
        --tess texts/la/pseudo_aurelius_victor.origo_gentis_romanae.tess \
        --out  data/translations/la__pseudo_aurelius_victor.origo_gentis_romanae.json
"""
import argparse
import html as html_lib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

# Chapter head: <SPAN class="chapterno"><A NAME="C7"></A>VII.</SPAN>
CHAPTER_RE = re.compile(
    r'<SPAN class="chapterno"><A NAME="C(\d+)"></A>[^<]*</SPAN>')
# Section head: <SPAN class="verse"><A NAME="7_3"></A>[3]</SPAN>
SECTION_RE = re.compile(
    r'<SPAN class="verse"><A NAME="(\d+)_(\d+)"></A>\[(\d+)\]</SPAN>')
COMMENTS_RE = re.compile(r'<b>\s*<em>\s*Comments and discussion', re.I)
FOOTNOTE_MARKER_RE = re.compile(r'<A HREF="#\d+">\s*<SUP>\d+</SUP>\s*</A>',
                                 re.I)
TAG_RE = re.compile(r'<[^>]+>')

# The three places where one corpus (Latin Library) line carries the
# content of two of this translation's numbered sections. See module
# docstring. Keys are (chapter, corpus_section); values are the list of
# translation section numbers (within that chapter) whose text is joined.
KNOWN_MERGES = {
    (3, 7): [7, 8],
    (4, 3): [3, 4],
    (5, 3): [3, 4],
}
# Corpus sections with no translation section of their own because they
# are absorbed into a merge target above (so a direct same-number lookup
# must not be attempted for them).
MERGE_ABSORBED = {(4, 4)}


def clean_text(fragment):
    frag = FOOTNOTE_MARKER_RE.sub('', fragment)
    frag = re.sub(r'<br\s*/?>', ' ', frag, flags=re.I)
    frag = TAG_RE.sub(' ', frag)
    frag = html_lib.unescape(frag)
    frag = re.sub(r'\s+', ' ', frag).strip()
    return frag


def parse_html(path, report):
    raw = open(path, encoding='utf-8', errors='replace').read()
    cut = COMMENTS_RE.search(raw)
    if cut:
        raw = raw[:cut.start()]
    else:
        report.append('WARNING: "Comments and discussion" marker not found; '
                       'the whole file was used, which risks pulling '
                       'footnote apparatus into the translation text.')

    chapter_matches = list(CHAPTER_RE.finditer(raw))
    section_matches = list(SECTION_RE.finditer(raw))
    if not chapter_matches or not section_matches:
        report.append('FATAL: no chapter or section markers found in the '
                       'HTML; page structure may have changed.')
        return None, None

    # The preface is the page's own opening dedication paragraph, which
    # sits after the page's nav links and title, not at the raw start of
    # the file (that would pull in the nav bar and the repeated title).
    title_marker = re.search(
        r'On the Origin of the Roman People</font></p>', raw)
    preface_start = title_marker.end() if title_marker else 0
    if not title_marker:
        report.append('WARNING: page title marker not found; preface text '
                       'may include navigation/title boilerplate.')
    preface_text = clean_text(raw[preface_start:chapter_matches[0].start()])

    # Build ordered list of (kind, chapter, section, start, end) boundaries
    # so each marker's text runs to the next marker of either kind.
    markers = [('chapter', int(m.group(1)), None, m.start(), m.end())
               for m in chapter_matches]
    markers += [('section', int(m.group(1)), int(m.group(2)), m.start(),
                 m.end()) for m in section_matches]
    markers.sort(key=lambda t: t[3])

    chapters = {}  # chapter -> {section: text}
    cur_chapter = None
    cur_section = None
    cur_start = None
    for i, (kind, c, s, start, end) in enumerate(markers):
        if cur_section is not None:
            text = clean_text(raw[cur_start:start])
            chapters.setdefault(cur_chapter, {})[cur_section] = text
        if kind == 'chapter':
            cur_chapter = c
            cur_section = None
        else:
            cur_chapter = c
            cur_section = s
            cur_start = end
    if cur_section is not None:
        text = clean_text(raw[cur_start:len(raw)])
        chapters.setdefault(cur_chapter, {})[cur_section] = text

    report.append(f'parsed {len(chapter_matches)} chapter heads, '
                  f'{len(section_matches)} section heads')
    for c in sorted(chapters):
        nums = sorted(chapters[c])
        expected = list(range(1, len(nums) + 1))
        if nums != expected:
            report.append(f'WARNING: chapter {c} translation sections are '
                          f'not a gap-free 1..N sequence: {nums}')
    return preface_text, chapters


def load_corpus(tess_path):
    refs = []  # [(ref, chapter_label, section)]  chapter_label: 'pr' or int
    latin_by_ref = {}
    struct = {}  # chapter_label -> [section,...] in file order
    for line in open(tess_path, encoding='utf-8', errors='replace'):
        m = re.match(r'^<ps-vict\. orig\. (pr|\d+)\.(\d+)>\s*(.*)$', line)
        if not m:
            continue
        chap_raw, sec, latin = m.group(1), int(m.group(2)), m.group(3).strip()
        chap = chap_raw if chap_raw == 'pr' else int(chap_raw)
        ref = f'ps-vict. orig. {chap_raw}.{sec}'
        refs.append((ref, chap, sec))
        latin_by_ref[ref] = latin
        struct.setdefault(chap, []).append(sec)
    return refs, latin_by_ref, struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    report = []
    preface_text, chapters = parse_html(args.html, report)
    if chapters is None:
        print('\n'.join(report))
        sys.exit(1)

    refs, latin_by_ref, struct = load_corpus(args.tess)
    report.append(f'corpus refs total: {len(refs)}')

    units, ref_to_unit, unit_sources = [], {}, []
    unit_index = {}

    def get_unit(text, source_idx):
        key = (text, source_idx)
        if key not in unit_index:
            unit_index[key] = len(units)
            units.append(text)
            unit_sources.append(source_idx)
        return unit_index[key]

    n_direct = n_merged = n_preface = 0
    unmapped = []
    for ref, chap, sec in refs:
        if chap == 'pr':
            ref_to_unit[ref] = get_unit(preface_text, 0)
            n_preface += 1
            continue
        chap_secs = chapters.get(chap, {})
        if (chap, sec) in MERGE_ABSORBED:
            # Should never be looked up directly as a corpus ref (the
            # merge target absorbs it); if it is, that is a real mismatch.
            unmapped.append(ref)
            continue
        if (chap, sec) in KNOWN_MERGES:
            parts = [chap_secs.get(n) for n in KNOWN_MERGES[(chap, sec)]]
            if any(p is None for p in parts):
                unmapped.append(ref)
                continue
            text = ' '.join(parts)
            ref_to_unit[ref] = get_unit(text, 1)
            n_merged += 1
            continue
        text = chap_secs.get(sec)
        if text is None:
            unmapped.append(ref)
            continue
        ref_to_unit[ref] = get_unit(text, 0)
        n_direct += 1

    coverage = len(ref_to_unit) / len(refs) if refs else 0
    report.append(f'preface units: {n_preface}; direct 1:1 sections: '
                  f'{n_direct}; merged (documented) sections: {n_merged}; '
                  f'{len(units)} distinct units stored')
    if unmapped:
        report.append(f'UNMAPPED refs ({len(unmapped)}): {unmapped}')
    report.append(f'coverage: {coverage:.4f} ({len(ref_to_unit)}/{len(refs)})')

    # ---- name-survival check (proper names should carry across) --------
    pairs = [(latin_by_ref[ref], units[ref_to_unit[ref]])
             for ref, chap, sec in refs if ref in ref_to_unit]
    hit, n_tested = V.score(pairs, 'la', sample=300)
    report.append(f'name check: hit_rate={hit} n={n_tested} '
                  f'(of {len(pairs)} translated-ref pairs available)')

    # ---- requested spot-checks ------------------------------------------
    report.append('')
    report.append('spot checks (Latin / English):')
    for suffix in ['pr.1', '1.1', '3.7', '4.3', '5.3', '23.6']:
        ref = f'ps-vict. orig. {suffix}'
        lat = latin_by_ref.get(ref, '<ref not in corpus>')
        eng = units[ref_to_unit[ref]] if ref in ref_to_unit else '<NOT TRANSLATED>'
        report.append(f'  {ref}')
        report.append(f'    LA: {lat[:300]}')
        report.append(f'    EN: {eng[:600]}')

    sources = [
        {
            'translator': 'collaborative translation, ed. Roger Pearse',
            'year': 2004,
            'title': 'Origo Gentis Romanae: The Origin of the Roman People',
            'publisher': 'tertullian.org',
            'mode': 'section',
            'ref_composition': ['chapter', 'section'],
            'source_url': 'https://www.tertullian.org/fathers/origo_01_trans.htm',
            'rights_basis': 'Page statement: "All material on this page is '
                            'in the public domain - copy freely."',
            'short_attribution': 'collaborative translation, ed. Roger Pearse (2004)',
        },
        {
            'translator': 'collaborative translation, ed. Roger Pearse',
            'year': 2004,
            'title': 'Origo Gentis Romanae: The Origin of the Roman People',
            'publisher': 'tertullian.org',
            'mode': 'section-merged',
            'ref_composition': ['chapter', 'section'],
            'source_url': 'https://www.tertullian.org/fathers/origo_01_trans.htm',
            'rights_basis': 'Page statement: "All material on this page is '
                            'in the public domain - copy freely."',
            'short_attribution': 'collaborative translation, ed. Roger Pearse (2004)',
            'note': 'The corpus\'s Latin transcription carries one numbered '
                    'line where this translation prints two numbered '
                    'sections; the two sections\' English is joined for '
                    'this corpus ref. See KNOWN_MERGES in align_origo.py.',
        },
    ]
    out = {
        'tess_work': 'la/pseudo_aurelius_victor.origo_gentis_romanae',
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': round(coverage, 4),
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(units)), 2),
        'alignment_confidence': 'high' if (hit or 0) >= 0.70 else 'medium',
        'name_check_hit_rate': hit,
        'name_check_n': n_tested,
        'sources': sources,
        'unit_sources': unit_sources,
        'license': 'Public domain ("All material on this page is in the '
                   'public domain - copy freely", tertullian.org).',
        'attribution': 'collaborative translation, ed. Roger Pearse (2004)',
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False)
    report.append('')
    report.append(f'wrote {args.out}')

    print('\n'.join(report))
    if unmapped:
        sys.exit(1)


if __name__ == '__main__':
    main()
