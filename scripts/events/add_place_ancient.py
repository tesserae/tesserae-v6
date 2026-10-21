#!/usr/bin/env python3
"""Add events.place_ancient, the name of the event's place in the time of the event.

  add_place_ancient.py INPUT.sqlite OUTPUT.sqlite RAW_DIR [--report PATH] [--apply]

RAW_DIR holds places/<pleiades id>.json and periods.json from fetch_pleiades_names.py. INPUT is never
modified. Dry run unless --apply. OUTPUT may not be under /var/www.

The rule (also in docs/DECISIONS.md). A Pleiades name qualifies for an event when it is geographic,
transcribed accurately, and attested in at least one named Pleiades period whose year range overlaps
the years of the event. The year ranges come from the Pleiades time-periods vocabulary
(https://pleiades.stoa.org/vocabularies/time-periods, for example hellenistic-republican -330 to -30 and
roman -30 to 300). A name with no attested period does not qualify, because nothing dates it.
Only names whose language is Latin, Ancient Greek (romanized) or English qualify, and only if the
romanized form is in Latin letters. Among the qualifying names Latin comes first, then English, then
Greek, and within one language the one attested in the narrowest overlapping period wins, then one that
matches the place's Pleiades title, then the first listed. A Pleiades name is a list of romanized variants, and the first variant is used with its
diacritics removed. Where English has a standard form of the same ancient name (Syracusae, Syracuse),
ENGLISH_FORMS gives it. The Latin or Greek form stays when English uses it as it stands (Actium,
Brundisium). The column stays empty when no name qualifies.
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import unicodedata

# Same ancient name, standard English form (key: lower-case ASCII romanization).
ENGLISH_FORMS = {
    'roma': 'Rome', 'athenai': 'Athens', 'athenae': 'Athens', 'syracusae': 'Syracuse', 'surakousai': 'Syracuse',
    'syrakousai': 'Syracuse', 'karthago': 'Carthage', 'carthago': 'Carthage', 'thebai': 'Thebes',
    'thebae': 'Thebes', 'korinthos': 'Corinth', 'corinthus': 'Corinth', 'ephesos': 'Ephesus',
    'alexandreia': 'Alexandria', 'alexandria': 'Alexandria', 'antiocheia': 'Antioch', 'antiochia': 'Antioch',
    'byzantion': 'Byzantium', 'sparte': 'Sparta', 'lakedaimon': 'Sparta', 'massalia': 'Massalia',
    'neapolis': 'Neapolis', 'pergamon': 'Pergamum', 'pergamum': 'Pergamum', 'sardeis': 'Sardis',
    'sardes': 'Sardis', 'milesios': 'Miletus', 'miletos': 'Miletus', 'miletus': 'Miletus',
    'rhodos': 'Rhodes', 'kyrene': 'Cyrene', 'cyrene': 'Cyrene', 'ilion': 'Troy', 'ilium': 'Troy',
    'troia': 'Troy', 'marathon': 'Marathon', 'thermopylai': 'Thermopylae', 'plataiai': 'Plataea',
    'plataeae': 'Plataea', 'salamis': 'Salamis', 'delphoi': 'Delphi', 'delphi': 'Delphi',
    'olympia': 'Olympia', 'arbela': 'Arbela', 'babylon': 'Babylon', 'memphis': 'Memphis',
    'pelousion': 'Pelusium', 'pelusium': 'Pelusium', 'tarentum': 'Tarentum', 'taras': 'Taras',
    'mediolanum': 'Mediolanum', 'londinium': 'Londinium', 'lugdunum': 'Lugdunum', 'ravenna': 'Ravenna',
    'konstantinoupolis': 'Constantinople', 'constantinopolis': 'Constantinople', 'byzantium': 'Byzantium', 'kerkyra': 'Corcyra', 'korkyra': 'Corcyra', 'kyzikos': 'Cyzicus',
    'chalkedon': 'Chalcedon', 'halikarnassos': 'Halicarnassus', 'sidon': 'Sidon', 'tyros': 'Tyre',
    'tyrus': 'Tyre', 'hierosolyma': 'Jerusalem', 'ierousalem': 'Jerusalem', 'damaskos': 'Damascus',
    'damascus': 'Damascus', 'nikaia': 'Nicaea', 'nicaea': 'Nicaea', 'nikomedeia': 'Nicomedia',
    'thessalonike': 'Thessalonica', 'amphipolis': 'Amphipolis', 'aigyptos': 'Egypt', 'aegyptus': 'Egypt',
    'ionium mare': 'Ionian Sea', 'pontus euxinus': 'Black Sea', 'mare internum': 'Mediterranean Sea',
    'hellas': 'Greece', 'italia': 'Italy', 'sikelia': 'Sicily', 'sicilia': 'Sicily', 'gallia': 'Gaul',
    'hispania': 'Hispania', 'britannia': 'Britain', 'germania': 'Germany',
}
# Only these languages qualify, in the order of preference (English scholarship uses the Latin form of
# most ancient places: Tarentum, Pherae, Caesarea, Syrian Gates).
LANG_RANK = {'la': 0, 'en': 1, 'grc': 2}


def ascii_fold(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c)).replace('ʻ', '').replace('ʼ', '').strip()


def first_variant(romanized):
    first = (romanized or '').split(',')[0].strip()
    return ascii_fold(first)


def latin_letters(form):
    return bool(form) and all(c.isascii() for c in form) and any(c.isalpha() for c in form)


def overlaps(a0, a1, b0, b1):
    return a0 <= b1 and b0 <= a1


def title_forms(title):
    """Pleiades titles mix forms ('Harran/Carrhae', 'Lydia/Maionia (region)'). Return the folded forms."""
    t = re.sub(r'\([^)]*\)', '', title or '')
    return {ascii_fold(x).lower() for x in t.split('/') if x.strip()}


def candidates(place, periods, y0, y1):
    """Qualifying names as (sort key, form, periods overlapped, language)."""
    tforms = title_forms(place.get('title'))
    out = []
    for order, n in enumerate(place.get('names') or []):
        if n.get('nameType') != 'geographic' or n.get('transcriptionAccuracy') == 'inaccurate':
            continue
        form = first_variant(n.get('romanized'))
        if not form:
            continue
        hit = []
        for att in n.get('attestations') or []:
            key = att.get('timePeriod')
            rng = periods.get(key)
            if rng and overlaps(rng[0], rng[1], y0, y1):
                hit.append((rng[1] - rng[0], key))
        if not hit:
            continue
        span = min(h[0] for h in hit)
        lang_rank = LANG_RANK.get(n.get('language'))
        if lang_rank is None or not latin_letters(form):
            continue
        variants = {ascii_fold(v).lower() for v in (n.get('romanized') or '').split(',')}
        title_rank = 0 if variants & tforms else 1
        out.append(((lang_rank, span, title_rank, order), form, sorted(h[1] for h in hit), n.get('language') or ''))
    out.sort(key=lambda c: c[0])
    return out


def english(form):
    return ENGLISH_FORMS.get(form.lower(), form)


def choose(place, periods, y0, y1):
    """Return (ancient name, periods it is attested in, language) or None."""
    c = candidates(place, periods, y0, y1)
    if not c:
        return None
    _, form, keys, lang = c[0]
    return english(form), keys, lang


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('raw_dir')
    ap.add_argument('--report')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('refusing to write under /var/www')
    periods = json.load(open(os.path.join(a.raw_dir, 'periods.json')))
    src = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    rows = src.execute("SELECT id, label, date_start, date_end, place, pleiades_id FROM events").fetchall()
    result = {}
    rep = {'with_pleiades': 0, 'named': 0, 'none': 0, 'no_file': 0, 'examples': []}
    for eid, label, ds, de, place, pid in rows:
        if not pid:
            continue
        rep['with_pleiades'] += 1
        path = os.path.join(a.raw_dir, 'places', pid + '.json')
        if not os.path.exists(path):
            rep['no_file'] += 1
            continue
        pl = json.load(open(path))
        if 'names' not in pl:
            rep['no_file'] += 1
            continue
        y0, y1 = (ds, de) if ds is not None and de is not None else (ds or de, ds or de)
        if y0 is None:
            continue
        got = choose(pl, periods, min(y0, y1), max(y0, y1))
        if got:
            result[eid] = got
            rep['named'] += 1
            rep['examples'].append([eid, label, ds, de, place, got[0], got[1], got[2]])
        else:
            rep['none'] += 1
    rep['same_as_modern'] = sum(1 for e in rep['examples'] if ascii_fold(e[4] or '').lower() == e[5].lower())
    if a.report:
        with open(a.report, 'w') as f:
            json.dump(rep, f, indent=1, ensure_ascii=False)
    print({k: v for k, v in rep.items() if k != 'examples'})
    if not a.apply:
        print('dry run, nothing written')
        return 0
    shutil.copyfile(a.input, a.output)
    dst = sqlite3.connect(a.output)
    cols = [r[1] for r in dst.execute('PRAGMA table_info(events)')]
    if 'place_ancient' not in cols:
        dst.execute('ALTER TABLE events ADD COLUMN place_ancient TEXT')
    dst.execute('UPDATE events SET place_ancient = NULL')
    for eid, (name, _, _) in result.items():
        dst.execute('UPDATE events SET place_ancient = ? WHERE id = ?', (name, eid))
    dst.commit()
    dst.close()
    print('written', a.output, len(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
