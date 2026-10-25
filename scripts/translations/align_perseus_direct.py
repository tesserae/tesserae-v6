#!/usr/bin/env python3
"""Works whose Perseus translation is on disk but which align_perseus.py left
without English because its identity step found no match (Part C, 2026-10-24):
Apollodorus (Library, Epitome: Frazer, Loeb 1921), Epictetus (Discourses,
Encheiridion: George Long, 1890) and Hippocrates (Ancient Medicine: Francis Adams, 1886, by section).

NOT WRITTEN: Hippocrates, Aphorisms (Adams 1886). Adams's numbering does not match ours:
section 7 has 88 aphorisms in Adams and 84 distinct numbers in our Greek, and inside
section 4 two aphorisms stand in the other order (Adams 4.50 'Apostemes in fevers...'
is our 4.51, his 4.51 'dyspnoea and delirium' is our 4.50). Pairing by number would
put the wrong English beside two or more aphorisms with no check able to see it, so
the work is reported instead of written.

Each pairing is by exact citation: our reference ends in the same numbers
Perseus's TEI uses as anchors (book.chapter.section for the Library,
chapter.section for the Epitome, book.chapter for the Discourses, chapter for the
Encheiridion). The counts line up one to one (209, 177, 96 and 53). Where a
Greek reference has no chunk of its own it shares the English of the one before.
Fragments and the Stobaean Gnomologium are not attempted: their numbering is not
shared (Long numbers the Fragments from Schweighaeuser, ours from Schenkl).

    align_perseus_direct.py OUT_DIR [--dry]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, perseus_find   # noqa: E402

out_dir = sys.argv[1]
dry = '--dry' in sys.argv


def nums(t):
    return tuple(int(x) for x in re.findall(r'\d+', t))


WORKS = [
    # stem, author, translator, title, anchor names, key from our tail
    ('apollodorus.library', 'Apollodorus', 'Frazer', 'Library', ('book', 'chapter', 'section'),
     lambda t: nums(t.split('Library.')[1]) if 'Library.' in t else None),
    ('apollodorus.epitome', 'Apollodorus', 'Frazer', 'Epitome', ('chapter', 'section'),
     lambda t: nums(t.split('Epitome.')[1].replace('E.', '', 1)) if 'Epitome.' in t else None),
    ('epictetus.discourses', 'Epictetus', 'George Long', "Arrian's Discourses of Epictetus", ('book', 'chapter'),
     lambda t: nums(t.split('disc.')[1]) if 'disc.' in t else None),
    ('epictetus.enchiridion', 'Epictetus', 'George Long', 'The Encheiridion, or Manual.', ('chapter',),
     lambda t: nums(t.split('enc.')[1]) if 'enc.' in t else None),
    ('hippocrates.de_prisca_medicina', 'Hippocrates', 'Francis Adams', 'On Ancient Medicine', ('section',),
     lambda t: nums(t.split('vm.')[1]) if 'vm.' in t else None),
]
for stem, author, trans, title, anchors, keyf in WORKS:
    recs = perseus_find(author, trans, title_eq=title)
    assert len(recs) == 1 and recs[0]['meta']['year'] <= 1930, (stem, len(recs))
    meta = recs[0]['meta']
    english = {}
    for ch in recs[0]['chunks']:
        try:
            k = tuple(int(ch['anchors'][a]) for a in anchors)
        except (KeyError, ValueError):
            continue
        english[k] = (english.get(k, '') + ' ' + ch['text']).strip()
    refs, src, _ = load_work('grc', stem)
    units, ref_to_unit, last, shared = [], {}, None, 0
    for r in refs:
        k = keyf(tail(r))
        t = english.get(k) if k else None
        if t:
            last = len(units)
            units.append(clean(t))
            ref_to_unit[r] = last
        elif last is not None and k:
            ref_to_unit[r] = last
            shared += 1
    finish('grc', stem, units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
           attribution=f"{meta['translator']}, {meta.get('source_title') or title} ({meta['year']}); Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)",
           license='CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain (published before 1931)',
           sources=[{'translator': meta['translator'], 'year': meta['year'], 'place': meta.get('pub_place'),
                     'publisher': meta.get('publisher'), 'title': meta.get('title'),
                     'mode': 'exact', 'ref_composition': list(anchors),
                     'cts_urn': meta.get('cts_urn'), 'source_file': meta.get('source_file'),
                     'pd_reason': f"published {meta['year']}, US public domain"}],
           notes=f'{shared} references with no chunk of their own share the English of the one before.')
