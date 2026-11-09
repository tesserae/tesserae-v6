#!/usr/bin/env python3
"""Stage 1 of the CLLG Freed Corpus group one import: the stems table.

Reads ~/tesserae-backups/cllg/tier1_texts.json (the 1,061 texts), our_grc_works.txt (the stems we hold),
data/cts_urns.json (to reuse the author stem of a TLG author we already hold) and the first line of every
texts/grc file (the citation tags in use), and writes the table both to ~/tesserae-backups/cllg/tier1_stems.json
and to scripts/corpus/cllg_tier1_works.json (the converter driver's input).

One object per text: file, urn, stem (author_stem.work_stem), tag, author_stem, author, title, parts.
Rules: docs in research/specs/2026-11-09_cllg_tier1_convert_spec.md (Stage 1).

    cllg_tier1_stems.py REPO_ROOT SRC_DIR
"""
import collections
import glob
import json
import os
import re
import subprocess
import sys
import unicodedata

from lxml import etree

HOME = os.path.expanduser('~/tesserae-backups/cllg')

# Latin author names (the TEI author string up to its first abbreviation) written as the stem we use.
# Names of authors we already hold come first: the stem the corpus already carries.
AUTHOR_OVERRIDES = {
    'Origenes': 'origen', 'Eusebius': 'eusebius_caesarea', 'Galenus': 'galen', 'Aristoteles': 'aristotle',
    'Euclides': 'euclid', 'Plutarchus': 'plutarch', 'Philo Judaeus': 'philo_judaeus', 'Hippocrates': 'hippocrates',
    'Gregorius Nazianzenus': 'gregory_of_nazianzus', 'Claudius Ptolemaeus': 'claudius_ptolemaeus',
    'Heron': 'hero_of_alexandria', 'Socrates Scholasticus': 'socrates_scholasticus',
    'Clemens Romanus': 'clement_of_rome', 'Justinus Martyr': 'justin_martyr', 'Basilius': 'basil_of_caesarea',
    'Theodoretus': 'theodoret', 'Nonnus': 'nonnus_of_panopolis', 'Pseudo-Galenus': 'pseudogalen',
    'Aesopus': 'aesop', 'Nicomachus Math': 'nicomachus_of_gerasa', 'Tryphon I': 'tryphon_i_grammaticus',
    'Aelius Herodianus': 'aelius_herodianus', 'Epicharmus': 'epicharmus',
    'Joannes Philoponus': 'joannes_philoponus', 'Porphyrius': 'porphyry',
    'Joannes Zonaras': 'joannes_zonaras', 'Constantinus VII Porphyrogenitus Imperator': 'constantine_porphyrogenitus',
    'Michael Glycas': 'michael_glycas', 'Joannes Malalas': 'joannes_malalas', 'Joannes Chrysostomus': 'john_chrysostom',
    'Joannes Camaterus': 'joannes_camaterus', 'Gregorius Nyssenus': 'gregory_of_nyssa', 'Michael': 'michael_of_ephesus',
    'Gregorius Thaumaturgus': 'gregory_thaumaturgus', 'Athanasius': 'athanasius', 'Epiphanius': 'epiphanius',
    'Hippolytus': 'hippolytus', 'Irenaeus': 'irenaeus', 'Didymus Caecus': 'didymus_the_blind',
    'Evagrius': 'evagrius_ponticus', 'Claudius Iolaus': 'claudius_iolaus',
    'Sextus Julius Africanus': 'sextus_julius_africanus', 'Ignatius': 'ignatius', 'Menander Protector': 'menander_protector',
    'Eudocia Augusta': 'eudocia_augusta', 'Aëtius': 'aetius_of_amida',
    'Claudius Ptolemaeus': 'claudius_ptolemaeus', 'Gaius Musonius Rufus': 'musonius_rufus',
    'Lucius Annaeus Cornutus': 'cornutus', 'Domitius Callistratus': 'domitius_callistratus',
    'Cornelius Alexander': 'cornelius_alexander_polyhistor', 'Aelius Herodianus et Pseudo-Herodianus': 'aelius_herodianus',
    'Julia Balbilla': 'julia_balbilla', 'Juba II Rex Mauretaniae': 'juba_ii', 'Beros(s)us': 'berossus',
    '(H)agias-Dercylus': 'hagias_dercylus', '(H)eren(n)ius Philo': 'herennius_philo', '[Clitophon]': 'clitophon',
    'Comica Adespota (CAF)': 'comica_adespota', 'Anonymi Historici (FGrH)': 'anonymi_historici',
    'Theophilus Protospatharius et Stephanus Atheniensis': 'theophilus_protospatharius_et_stephanus_atheniensis',
}
# Keyed by the whole TEI author string; wins over everything else (distinct people who share a name, and
# authors we hold under a stem the TLG number does not reach).
RAW_OVERRIDES = {
    'Evagrius Scr. Eccl.': 'evagrius_ponticus',   # TLG 4110 is Evagrius Ponticus, not the church historian
    'Alexander Phil.': 'alexander_of_aphrodisias', 'Alexander Theol.': 'alexander_of_lycopolis',
    'Cyrillus Scr. Eccl.': 'cyril_of_jerusalem', 'Cyrillus Theol.': 'cyril_of_alexandria',
    'Joannes Gramm. et Poeta': 'joannes_of_gaza', 'Joannes Theol.': 'joannes_theologus',
    'Gregorius Nazianzenus Theol.': 'gregory_of_nazianzus', 'Lysias Orat.': 'lysias',
    'Philo Mech.': 'philo_of_byzantium', 'Photius Lexicogr., Scr. Eccl. et Theol.': 'photius',
    'Manuel Philes Poeta et Scr. Rerum Nat.': 'manuel_philes', 'Eratosthenes et Eratosthenica Philol.': 'eratosthenes',
    'Simon Scriptor De Re Equestri': 'simon', 'Damianus Scriptor De Opticis': 'damianus',
    'Eudocia Augusta Poeta': 'eudocia_augusta', 'Lobo Poeta': 'lobo',
    'Melampus Scriptor De Divinatione': 'melampus', 'Basilius Theol.': 'basil_of_caesarea',
}
ROLE_WORD = {'Comic.': 'comicus', 'Hist.': 'historicus', 'Phil.': 'philosophus', 'Rhet.': 'rhetor', 'Gramm.': 'grammaticus',
             'Med.': 'medicus', 'Theol.': 'theologus', 'Math.': 'mathematicus', 'Astrol.': 'astrologus',
             'Epic.': 'epicus', 'Mech.': 'mechanicus', 'Myth.': 'mythographus', 'Trag.': 'tragicus', 'Lyr.': 'lyricus',
             'Orat.': 'orator', 'Geom.': 'geometer', 'Astron.': 'astronomus', 'Soph.': 'sophista', 'Biogr.': 'biographus',
             'Paradox.': 'paradoxographus', 'Perieg.': 'periegeta', 'Parodius': 'parodus', 'Eleg.': 'elegiacus',
             'Poeta': 'poeta', 'Chronogr.': 'chronographus', 'Scr.': 'scriptor'}


GREEK_LETTERS = dict(zip('αβγδεζηθικλμνξοπρσςτυφχψω', ['a', 'b', 'g', 'd', 'e', 'z', 'e', 'th', 'i', 'k', 'l', 'm', 'n', 'x', 'o', 'p',
                                                       'r', 's', 's', 't', 'y', 'ph', 'ch', 'ps', 'o']))


def translit(s):
    out = []
    for c in unicodedata.normalize('NFD', s):
        if unicodedata.combining(c):
            continue
        out.append(GREEK_LETTERS.get(c.lower(), c) if re.match('[Ͱ-Ͽἀ-῿]', c) else c)
    return ''.join(out)


def fold(s):
    s = translit(s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'\([^)]*\)', lambda m: m.group(0)[1:-1] if len(m.group(0)) <= 4 else ' ', s)
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower()
    return s


def author_name(raw):
    """The Latin name part of the TEI author string: tokens up to the first abbreviation ending in a stop."""
    toks = raw.split()
    out = []
    for t in toks:
        if t.endswith('.') and t not in ('Jr.',):
            break
        out.append(t)
    # "Aristoteles Phil. et Corpus ..." stops at Phil.; "Iuba II Rex ..." keeps the numeral.
    return ' '.join(out) or raw


def role_of(raw):
    for t in raw.split():
        if t in ROLE_WORD:
            return ROLE_WORD[t]
    return 'incertus'


def work_stem(title):
    t = re.sub(r'\[[^\]]*\]', ' ', title)
    t = re.sub(r'\s\(.*$', '', t)                       # a parenthetical (manuscript, recension) ends the title
    s = fold(t)
    if len(s) > 60:
        words = s.split('_')
        cut = ''
        for w in words:
            if len(cut) + len(w) + (1 if cut else 0) > 60:
                break
            cut = f'{cut}_{w}' if cut else w
        s = cut or s[:60]
    return s or 'opus'


STOP = {'de', 'in', 'ad', 'et', 'libros', 'libri', 'liber', 'commentaria', 'commentarium', 'commentarius', 'sive',
        'quae', 'qui', 'quod', 'cum', 'ex', 'a', 'ab', 'pro', 'contra', 'eis', 'peri', 'ta', 'scholia', 'glossae', 'et'}


def abbrev_word(w, n):
    return w[:n]


def tag_for(author_stem, title, level):
    """Author abbreviation fixed; the title part grows with `level` until the tag is unused."""
    if author_stem == 'anonymous':
        a = 'anon.'
    elif author_stem == 'scholia':
        a = 'schol.'
    elif author_stem.startswith('joannes_'):
        a = 'joann.' + author_stem.split('_', 1)[1][0] + '.'
    elif author_stem.startswith('pseudo'):
        a = 'ps.' + (author_stem[6:].lstrip('_').split('_')[0])[:6] + '.'
    else:
        first = author_stem.split('_')[0]
        a = (first if len(first) <= 7 else first[:6]) + '.'
    words = [w for w in fold(re.sub(r'\[[^\]]*\]', ' ', title)).split('_') if w]
    sig = [w for w in words if w not in STOP] or words
    head = []
    if words and words[0] == 'in' and author_stem != 'scholia':
        head.append('in')
    head += [w[:4 + (level // 2)] + '.' for w in sig[:2 + level % 2 + level // 2]]
    return (a + ' ' + ' '.join(head)).strip()


BOOKLIKE = {'book', 'oration', 'letter', 'homily', 'declamation', 'iliad_book', 'oration_declamation_dialexis'}


def parts_flag(root, units):
    if len(units) < 2 or units[0] not in BOOKLIKE:
        return False
    body = root.find('.//{*}body')
    n = 0
    for d in body.iter('{*}div'):
        if d.get('n') and d.get('type') not in ('edition', 'translation'):
            anc = d.getparent()
            top = True
            while anc is not None and anc is not body:
                if anc.tag.endswith('}div') and anc.get('n') and anc.get('type') not in ('edition', 'translation'):
                    top = False
                    break
                anc = anc.getparent()
            if top:
                n += 1
    return n >= 2


def main():
    repo, src = sys.argv[1], sys.argv[2]
    texts = json.load(open(os.path.join(HOME, 'tier1_texts.json'), encoding='utf-8'))
    # A comic title with no text: the file holds only the name of a lost play, 1 to 4 tokens in a heading.
    left_out = [t for t in texts if t['title'] in ('Titulus', 'Tituli') and t['tokens'] <= 4]
    # Probable duplicates (step 2), found by title and by shared word sequences: cllg_tier1_duplicates.json maps
    # the file to the reason. They are left out of the table.
    DUPLICATES = json.load(open(os.path.join(repo, 'scripts/corpus/cllg_tier1_duplicates.json'), encoding='utf-8'))
    dup_rows = [dict(t, reason='probable duplicate: ' + DUPLICATES[t['file']]) for t in texts if t['file'] in DUPLICATES]
    texts = [t for t in texts if t['file'] not in DUPLICATES]
    # Editions of 1930 or later are not in group one (read from the sourceDesc by a person): file -> imprint.
    LATE = json.load(open(os.path.join(repo, 'scripts/corpus/cllg_tier1_edition_after_1930.json'), encoding='utf-8'))
    late_rows = [dict(t, reason='edition after 1930: ' + LATE[t['file']]) for t in texts if t['file'] in LATE]
    texts = [t for t in texts if t['file'] not in LATE]
    texts = [t for t in texts if t not in left_out]
    held_stems = set(l.strip() for l in open(os.path.join(HOME, 'our_grc_works.txt')) if l.strip())
    cts = json.load(open(os.path.join(repo, 'data/cts_urns.json')))['grc']
    held_author_by_id = {}
    for k, v in cts.items():
        m = re.search(r'(tlg\d+)\.', v.get('urn') or '')
        if m:
            held_author_by_id.setdefault(m.group(1), k.split('.')[0])
    used_tags = set()
    # Only the files git tracks: a file this import wrote earlier must not count as a tag already in use.
    tracked = subprocess.check_output(['git', '-C', repo, 'ls-files', 'texts/grc'], text=True).split()
    prior = set()
    wp = os.path.join(repo, 'scripts/corpus/cllg_tier1_works.json')
    if os.path.exists(wp):
        prior = {r['stem'] for r in json.load(open(wp, encoding='utf-8'))}     # this import's own files, tracked on its branch
    for f in tracked:
        if not f.endswith('.tess') or any(os.path.basename(f).startswith(p + '.') for p in prior):
            continue
        with open(os.path.join(repo, f), encoding='utf-8') as fh:
            used_tags.add(fh.readline()[1:].split('>')[0].rsplit(' ', 1)[0])

    # author stem per TLG author id
    by_id = collections.OrderedDict()
    for t in texts:
        by_id.setdefault(t['urn'].split(':')[-1].split('.')[0], []).append(t)
    taken = collections.Counter()
    author_stem_of = {}
    held_stems_authors = set(s.split('.')[0] for s in held_stems)
    for aid, ts in by_id.items():
        raw = ts[0]['author']
        name = author_name(raw)
        if raw in RAW_OVERRIDES:
            stem = RAW_OVERRIDES[raw]
        elif name.startswith('Scholia In'):
            stem = 'scholia'
        elif name.startswith('Anonymi In '):
            stem = 'anonymous'
        elif aid in held_author_by_id:
            stem = held_author_by_id[aid]
        elif name in AUTHOR_OVERRIDES:
            stem = AUTHOR_OVERRIDES[name]
        elif raw in AUTHOR_OVERRIDES:
            stem = AUTHOR_OVERRIDES[raw]
        else:
            stem = fold(name)
        if stem.startswith('pseudo_'):
            stem = 'pseudo' + stem[7:]
        author_stem_of[aid] = stem
    # Distinct TLG authors sharing one stem that we do not already hold under it: add the role word.
    users = collections.defaultdict(list)
    for aid, s in author_stem_of.items():
        users[s].append(aid)
    for s, ids in users.items():
        if s in ('scholia', 'anonymous') or all(by_id[i][0]['author'] in RAW_OVERRIDES for i in ids):
            continue
        reserved = [i for i in ids if i in held_author_by_id and held_author_by_id[i] == s]
        clash = len(ids) > 1 or (s in held_stems_authors and not reserved)
        if not clash:
            continue
        for i in ids:
            if i in reserved or by_id[i][0]['author'] in RAW_OVERRIDES:
                continue
            author_stem_of[i] = f'{s}_{role_of(by_id[i][0]["author"])}'
    users = collections.defaultdict(list)
    for aid, s in author_stem_of.items():
        users[s].append(aid)
    for s, ids in users.items():
        if len(ids) > 1 and s not in ('scholia', 'anonymous') and not all(held_author_by_id.get(i) == s for i in ids):
            for n, i in enumerate(sorted(ids)[1:], 2):
                author_stem_of[i] = f'{s}_{n}' if not by_id[i][0]['author'].count(' ') else f'{s}_{i[3:]}'

    rows, stems = [], set(held_stems)
    for t in texts:
        aid = t['urn'].split(':')[-1].split('.')[0]
        a = author_stem_of[aid]
        w = work_stem(t['title'])
        if a == 'scholia':
            target = fold(re.sub(r'^scholia in ', 'in ', author_name(t['author']).lower()))
            rest = re.sub(r'^(scholia(_et_glossae)?(_in)?_?|argumentum_in_margine_et_glossae_interlineariae_ad_)', '', w)
            w = target + ('_' + rest if rest and rest != target.replace('in_', '') else '')[:60]
        stem = f'{a}.{w}'
        if stem in stems:
            alt = f'{a}.{w}_{t["urn"].split(".")[-1]}'
            stem = alt if alt not in stems else f'{a}.{w}_{t["urn"].split(":")[-1].replace(".", "_")}'
        stems.add(stem)
        root = etree.parse(os.path.join(src, t['file']), etree.XMLParser(recover=True, huge_tree=True)).getroot()
        rows.append({'file': t['file'], 'urn': t['urn'], 'stem': stem, 'tag': None, 'author_stem': a,
                     'author': t['author'], 'title': t['title'], 'parts': parts_flag(root, t['units']),
                     'units': t['units']})
    for r in rows:
        for level in range(0, 8):
            tag = tag_for(r['author_stem'], r['title'], level)
            if tag not in used_tags:
                break
        else:
            tag = f'{tag} {r["urn"].split(":")[-1].replace("tlg", "")}'
        used_tags.add(tag)
        r['tag'] = tag
    for r in rows:
        r.pop('units')
    out = json.dumps(rows, ensure_ascii=False, indent=1) + '\n'
    open(os.path.join(HOME, 'tier1_stems.json'), 'w', encoding='utf-8').write(out)
    open(os.path.join(repo, 'scripts/corpus/cllg_tier1_works.json'), 'w', encoding='utf-8').write(out)
    json.dump([{'file': t['file'], 'urn': t['urn'], 'author': t['author'], 'title': t['title'], 'tokens': t['tokens'],
                'reason': t.get('reason', 'title only: the file holds the name of a lost play and no text')}
               for t in left_out + dup_rows + late_rows],
              open(os.path.join(repo, 'scripts/corpus/cllg_tier1_left_out.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(len(left_out), 'title-only and', len(dup_rows), 'duplicates left out;', len(rows), 'rows;', len(set(r['stem'] for r in rows)), 'unique stems;', len(set(r['tag'] for r in rows)), 'unique tags;',
          sum(r['parts'] for r in rows), 'with parts')


if __name__ == '__main__':
    main()
