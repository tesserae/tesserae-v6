#!/usr/bin/env python3
"""Shared helpers of Part G (2026-10-25): section-level alignment from the Perseus TEI of the Loeb translations.

Perseus numbers its English by the same section numbers our references end in (Demosthenes
sections, Isocrates sections, Stephanus pages and letters). Each of the scripts of this part builds
{key: English} from one Perseus record and gives every reference of ours the English of its key,
then hands the result to chapter_common.finish(), which measures proper names, length correlation
and the rival-unit test and refuses to write a file that no check vouches for.

Nothing here installs anything. TESSERAE_TEXTS defaults to the production text folder (read only).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, perseus_find, perseus_records   # noqa: E402,F401

RENEWAL_NOTE = 'renewal check 2026-10-24 and 2026-10-25, NYPL cce-renewals 1954 to 1991'

# One row per Loeb volume used: key -> (place, publisher, title page read at, year)
VOLUMES = {
    'dem1': dict(year=1930, title='Demosthenes, vol. I: Olynthiacs, Philippics, Minor Public Speeches (Loeb Classical Library)',
                 scan='by date, no title page read'),
    'dem2': dict(year=1926, title='Demosthenes, vol. II: On the Crown, On the Embassy (Loeb Classical Library)',
                 scan='by date, no title page read'),
    'dem3': dict(year=1935, title='Demosthenes, vol. III: Against Meidias, Androtion, Aristocrates, Timocrates, Aristogeiton (Loeb Classical Library)',
                 scan='https://archive.org/details/demosthenesagain00demouoft (title page MCMXXXV, London William Heinemann Ltd, Cambridge, Massachusetts Harvard University Press)'),
    'dem4': dict(year=1936, title='Demosthenes, Private Orations, vol. I: orations 27 to 40 (Loeb Classical Library)',
                 scan='https://archive.org/details/privateorationsw01demouoft (title page MCMXXXVI, Cambridge, Massachusetts Harvard University Press, London William Heinemann Ltd)'),
    'dem5': dict(year=1939, title='Demosthenes, Private Orations, vol. II: orations 41 to 49 (Loeb Classical Library)',
                 scan='https://archive.org/details/privateorationsw02demouoft (title page MCMXXXIX, Cambridge, Massachusetts Harvard University Press, London William Heinemann Ltd)'),
    'dem6': dict(year=1939, title='Demosthenes, Private Orations, vol. III: orations 50 to 59 (Loeb Classical Library)',
                 scan='https://archive.org/details/privateorationsw03demouoft (title page MCMXXXIX, Cambridge, Massachusetts Harvard University Press, London William Heinemann Ltd)'),
    'dem7': dict(year=1949, title='Demosthenes, vol. VII: Funeral Speech, Erotic Essay, Exordia, Letters (Loeb Classical Library)',
                 scan='https://archive.org/details/funeralspeechero00demouoft (title page MCMXLIX, London William Heinemann Ltd, Cambridge, Massachusetts Harvard University Press)'),
    'iso3': dict(year=1945, title='Isocrates, vol. III (Loeb Classical Library)',
                 scan='https://archive.org/details/isocrateswitheng03isocuoft (title page MCMXLV, Cambridge, Massachusetts Harvard University Press, London William Heinemann Ltd)'),
}


def license_for(year, scan=None):
    """The license wording of a Perseus-carried Loeb translation by year of first publication."""
    base = 'CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain'
    if year <= 1930:
        return f'{base} (published {year}, public domain by date)'
    return (f'{base}: published {year} with a United States imprint and no renewal of the copyright found '
            f'({RENEWAL_NOTE})')


def pd_reason(year):
    if year <= 1930:
        return f'published {year}, United States public domain by date'
    return f'published {year} with a United States imprint; no renewal found ({RENEWAL_NOTE})'


def source_dict(translator, year, title, url, mode='exact', ref_composition=None, place='London and Cambridge, MA',
                publisher='William Heinemann / Harvard University Press', scan=None):
    return {'translator': translator, 'year': year, 'place': place, 'publisher': publisher, 'title': title,
            'mode': mode, 'ref_composition': ref_composition or ['section'], 'url': url,
            'license': license_for(year), 'pd_reason': pd_reason(year), **({'title_page_read': scan} if scan else {})}


def perseus_record(author, title, translator_part):
    recs = perseus_find(author, translator_part, title_eq=title)
    if len(recs) != 1:
        raise SystemExit(f'Perseus: {author} / {title} / {translator_part}: {len(recs)} records')
    return recs[0]


def key_int(x):
    m = re.match(r'(\d+)', x or '')
    return int(m.group(1)) if m else None


def section_text(rec, keys=('section',), numeric=True):
    """{key: English}: chunks of one record joined by their anchor key (a tuple of the named anchors)."""
    out = {}
    for ch in rec['chunks']:
        a = ch['anchors']
        k = tuple((key_int(a.get(n)) if numeric else a.get(n)) for n in keys)
        if any(v is None for v in k):
            continue
        k = k[0] if len(k) == 1 else k
        out[k] = (out.get(k, '') + ' ' + ch['text']).strip()
    return out


def pair_by_key(refs, key_of_ref, english, share_previous=True, group_of_ref=None):
    """units, ref_to_unit, shared. A reference whose key has no English takes the unit of the
    reference before it in the same group (the English runs two sections together); a reference
    with no earlier unit in its group stays unpaired."""
    units, ref_to_unit, last, shared = [], {}, {}, 0
    for r in refs:
        k = key_of_ref(r)
        g = group_of_ref(r) if group_of_ref else None
        t = english.get(k)
        if t:
            last[g] = len(units)
            units.append(clean(t))
            ref_to_unit[r] = last[g]
        elif share_previous and g in last:
            ref_to_unit[r] = last[g]
            shared += 1
    return units, ref_to_unit, shared


def stephanus_text(rec, group=None):
    """{(group, section): English} for a Perseus record of a Plato work, keyed by Stephanus section ('375e').

    Perseus marks the Loeb's page breaks with a bare page number ('375') that comes before, or in place of,
    the lettered sections. Read in document order, a bare number N is
      * the continuation of the chunk before it when a section N+'a' exists in the record or was already taken
        (the page break falls inside the text of the section before, and the text after it belongs there), and
      * the section N+'a' itself when no such section exists (the page break is where 'a' begins).
    Dropping bare chunks, as an exact-key match does, loses the tail of about one section in six."""
    group = group or (lambda a: None)
    chunks = rec['chunks']
    lettered = {(group(c['anchors']), c['anchors']['section'][:-1]) for c in chunks
                if c['anchors'].get('section') and not c['anchors']['section'].isdigit()
                and c['anchors']['section'][-1] == 'a'}
    out, taken_a, last = {}, set(), None
    for c in chunks:
        a = c['anchors']
        sec = a.get('section')
        if not sec:
            continue
        g = group(a)
        if sec.isdigit():
            if (g, sec) in lettered or (g, sec) in taken_a:
                k = last                                   # continuation of the chunk before
            else:
                k = (g, sec + 'a')
                taken_a.add((g, sec))
        else:
            k = (g, sec)
        if k is None:
            continue
        out[k] = (out.get(k, '') + ' ' + c['text']).strip()
        last = k
    return out
