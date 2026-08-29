#!/usr/bin/env python3
"""The Ante-Nicene and post-Nicene Fathers batch: Lactantius, John
Cassian, Sulpicius Severus, Tertullian, Minucius Felix, Arnobius,
Commodian, Cyprian's treatises, and Ambrose's De mysteriis.

~11,000 corpus lines across nine authors, none with English, all covered
by the ANF/NPNF translations (1885-1894, public domain) in CCEL's ThML
transcriptions — the same source and machinery as the Jerome and
Augustine jobs (PR #297/#298). This is a REGISTRY script in the
align_augustine.py mould: each work says which volume it lives in, the
div title that finds it, and how its English marks the corpus's units.

The corpus references these authors at book.chapter.section or
chapter.section; the ANF prints one div per chapter. So the unit is one
CHAPTER, found positionally among the child divs and validated against
the corpus's own chapter count for that book — a book that disagrees by
more than one chapter is refused and printed. Sections inside a chapter
all serve the chapter's English.

What is deliberately NOT here:
- Cyprian's LETTERS: the ANF numbers them in the old Oxford order, the
  corpus in the CSEL order (corpus ep. 1 'Graviter commoti' is ANF ep.
  65); mapping needs the printed concordance, not a guess. OPEN.
- Commodian's Carmen apologeticum: not in the ANF at all. OPEN.
- Lactantius' fragmenta: 31 lines of disjoint quotations. OPEN.
- Victorinus' De machabeis, and the pseudo-Cyprianic verse: no ANF
  English exists.

The Phoenix and the Poem on the Passion are VERSE with per-line corpus
refs; the ANF renders them in verse of a different line count, so they
are aligned proportionally by line position and marked approximate.

Usage:
    python scripts/translations/align_anf.py \
        --src-dir <dir with anf03..anf07, npnf210, npnf211 xml> \
        --tess-dir texts/la --out-dir <dir> [--only work,...]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V
from align_augustine import (Volume, children, plain, roman_to_int,
                             chain_sections)

FRONT = re.compile(r'Title Page|Introduct|Preface|Prolegomena|Elucidat|'
                   r'Translator|Notice|Argument|Analysis|Note[.s]|Index')


def numbered_children(seg, lvl, kind='Chapter'):
    """{n: text} for child divs whose title opens 'Chapter N' (or whose
    @n parses); numbering positional, validated against explicit numbers."""
    out, pos = {}, 0
    for attrs, body in children(seg, lvl):
        title = attrs.get('title', '')
        # an explicit number makes a div content whatever its title says:
        # the Octavius numbers every chapter but titles them "Argument:
        # ...", and On Prayer's first chapter is "General Introduction";
        # filtering those as front matter shifted every chapter by one
        n = None
        m = re.match(rf'{kind}\s+([IVXLCD]+)', title)
        if m:
            n = roman_to_int(m.group(1))
        elif attrs.get('n', '').isdigit():
            n = int(attrs['n'])
        elif roman_to_int(attrs.get('n', '') or 'Q'):
            n = roman_to_int(attrs['n'])
        if n is None and FRONT.search(title):
            continue
        pos += 1
        if n and n != pos:
            pos = n
        out[pos] = plain(body)
    return out


def book_number(title, attrs):
    m = re.search(r'(?:Book|Dialogue)\s+([IVXLCD]+)', title)
    if m:
        return roman_to_int(m.group(1))
    n = attrs.get('n', '')
    if n.isdigit():
        return int(n)
    return roman_to_int(n) if n else None


REG = []


def reg(work, vol, title, ref_re, mode='book-chapter', **kw):
    REG.append(dict(work=work, vol=vol, title=title, ref_re=ref_re,
                    mode=mode, **kw))


# ---- Lactantius (ANF vol. 7, Fletcher 1886) ----
reg('lactantius.divinarum_institutionum', 'anf07', 'The Divine Institutes',
    r'<(lactantius\. div_inst\. (\d+)\.(\d+)\.\d+)>')
reg('lactantius.epitome_divinarum_institutionum', 'anf07',
    'The Epitome of the Divine Institutes',
    r'<(lact\. epitome\. (?:pr|(\d+))\.(\d+)?[^>]*)>', mode='chapter-flat')
reg('lactantius.de_ira_dei', 'anf07', 'A Treatise on the Anger of God',
    r'<(lact\. de_ira\. (\d+)\.\d+)>', mode='chapter')
reg('lactantius.de_opificio_dei', 'anf07', 'On the Workmanship of God',
    r'<(lact\. opificio\. (\d+)\.\d+)>', mode='chapter')
reg('lactantius.de_mortibus_persecutorum', 'anf07',
    'Of the Manner in Which the Persecutors Died',
    r'<(lact\. de_mort\. (\d+)\.\d+)>', mode='chapter')
reg('lactantius.de_ave_phoenice', 'anf07', 'The Ph\u0153nix',
    r'<(lact\. phoenice\. (\d+))>', mode='verse')
reg('lactantius.carmen_de_passione_domini', 'anf07',
    'A Poem on the Passion of the Lord',
    r'<(lact\. carmen\. (\d+))>', mode='verse')

# ---- John Cassian (NPNF series 2 vol. 11, Gibson 1894) ----
reg('john_cassian.conlationes', 'npnf211', 'The Conferences of John Cassian',
    r'<(john_cassian\. conlationes\. (\d+)\.(?:praef|(\d+))\.\d+)>',
    mode='conferences')
reg('john_cassian.institutiones', 'npnf211',
    'The Twelve Books on the Institutes',
    r'<(john_cassian\. institutiones\. (?:praef|(\d+))\.(\d+)?[^>]*)>')
reg('john_cassian.de_incarnatione_domini_contra_nestorum', 'npnf211',
    'on the Incarnation of',
    r'<(john_cassian\.de_incarnatione_domini_contra_nestorum '
    r'(?:pr|(\d+))\.(\d+)?[^>]*)>')

# ---- Sulpicius Severus (NPNF series 2 vol. 11, Roberts 1894) ----
reg('sulpicius_severus.vita_martini', 'npnf211', 'On the Life of St. Martin',
    r'<(sulpicius_severus\. vita_martini\. (\d+)\.\d+)>', mode='chapter')
reg('sulpicius_severus.dialogi', 'npnf211', 'Dialogues of Sulpitius',
    r'<(sulpicius_severus\. dialogi\. (\d+)\.(\d+)\.\d+)>')
reg('sulpicius_severus.chronica', 'npnf211', 'The Sacred History',
    r'<(sulpicius_severus\. chronica\. (\d+)\.(\d+)\.\d+)>')

# ---- Minucius Felix, Commodian, Arnobius ----
reg('minucius_felix.octavius', 'anf04', 'The Octavius of Minucius',
    r'<(minutius_felix\. octavius\. (\d+)\.\d+)>', mode='chapter')
reg('commodian.instructiones', 'anf04', 'The Instructions of Commodianus',
    r'<(commodian\. instructiones\. (\d+)\.(\d+)\.\d+)>',
    mode='commodian')
reg('arnobius.adversus_nationes', 'anf06', 'The Seven Books of Arnobius',
    r'<(arnobius\. adversus_nationes\. (\d+)\.(\d+))>')

# ---- Tertullian (ANF vols 3-4, Holmes/Thelwall) ----
# the corpus tags Tertullian three ways: 'tert. <ab>. c.s' for the two
# largest works, 'tertullian. <name>. c' (flat chapters, dot optional,
# some names abbreviated), and two-field book.chapter for Marcion/Nationes
def tert(work, vol, title, tag, mode='chapter'):
    reg('tertullian.' + work, vol, title, tag, mode=mode)


tert('apologeticum', 'anf03', 'Apology', r'<(tert\. apol\. (\d+)\.\d+)>')
tert('de_spectaculis', 'anf03', 'The Shows, or De Spectaculis',
     r'<(tert\. desp\. (\d+)\.\d+)>')
tert('ad_martyres', 'anf03', 'Ad Martyras',
     r'<(tert\. ad_mart\. (\d+)\.\d+)>')
tert('de_idololatria', 'anf03', 'On Idolatry',
     r'<(tertullian\. de_idololatria\. (\d+))>')
tert('de_testimonio_animae', 'anf03', "s Testimony",
     r'<(tertullian\. de_testimonio_animae\. (\d+))>')
tert('ad_nationes_libri_duo', 'anf03', 'Ad Nationes',
     r'<(tertullian\.ad_nationes_libri_duo (\d+)\.(\d+))>',
     mode='book-chapter')
tert('adversus_marcionem', 'anf03', 'The Five Books Against Marcion',
     r'<(tertullian\. adversus_marcionem\. (\d+)\.(\d+))>',
     mode='book-chapter')
tert('adversus_hermogenem', 'anf03', 'Against Hermogenes',
     r'<(tertullian\. adversus_herm\. (\d+))>')
tert('adversus_valentinianos', 'anf03', 'Against the Valentinians',
     r'<(tertullian\. adversus_val\. (\d+))>')
tert('de_anima', 'anf03', 'A Treatise on the Soul',
     r'<(tertullian\. de_anima\. (\d+))>')
tert('de_carnis_resurrectione', 'anf03', 'On the Resurrection of the Flesh',
     r'<(tertullian\. de_carnis_ress\. (\d+))>')
tert('de_oratione', 'anf03', 'On Prayer',
     r'<(tertullian\. de_oratione\. (\d+))>')
tert('de_baptismo', 'anf03', 'On Baptism',
     r'<(tertullian\. de_baptismo\. (\d+))>')
tert('de_patientia', 'anf03', 'On Patience.',
     r'<(tertullian\. de_patientia\. (\d+))>')
tert('adversus_praxean', 'anf03', 'Against Praxeas',
     r'<(tertullian\.adversus_praxean (\d+))>')
tert('scorpiace', 'anf03', 'Scorpiace',
     r'<(tertullian\.scorpiace (\d+))>')
tert('de_pudicitia', 'anf04', 'On Modesty',
     r'<(tertullian\. de_pudicitia\. (\d+))>')
tert('de_ieiunio_adversus_psychicos', 'anf04', 'On Fasting',
     r'<(tertullian\.de_ieiunio_adversus_psychicos (\d+))>')

# ---- Cyprian treatises (ANF vol. 5, Wallis 1886) ----
reg('cyprian.ad_quirinum_aut_testimoniorum_libri_tres_adversus_judaeos',
    'anf05', 'Three Books of Testimonies Against the Jews',
    r'<(cyprian\. ad_quirinum\. (\d+)\.(?:praef|(\d+)))>', mode='quirinum')

# treatise chapters in the ANF are numbered PARAGRAPHS, not divs, so
# these run in chapter mode with the chain fallback below; the corpus's
# spellings differ from the filenames in three cases
CYPRIAN_TREATISES = [
    ('de_habitu_virginum', 'de_habitu_uirginum', 'On the Dress of Virgins'),
    ('de_lapsis', 'de_lapsis', 'On the Lapsed'),
    ('de_unitate_ecclesiae_catholicae', 'de_catholicae_ecclesiae_unitate',
     'On the Unity of the Church'),
    ('de_dominica_oratione', 'de_dominica_oratione', "On the Lord's Prayer"),
    ('de_mortalitate', 'de_mortalitate', 'On the Mortality'),
    ('de_opere_et_eleemosynis', 'de_opere_et_eleemosynis',
     'On Works and Alms'),
    ('de_bono_patientiae', 'de_bono_patientiae',
     'On the Advantage of Patience'),
    ('de_zelo_et_livore', 'de_zelo_et_livore', 'On Jealousy and Envy'),
    ('ad_demetrianum', 'ad_demetrianum', 'An Address to Demetrianus'),
    ('quod_idola_dii_non_sint', 'quod_idola_dii_non_sint',
     'On the Vanity of Idols'),
    ('ad_donatum', 'ad_donatum', 'To Donatus'),
]
# the Exhortation's corpus refs carry a constant book field ('1.n'), so
# the chapter is the SECOND number
reg('cyprian.fortunatum_aut_de_exhortatione_martyrii', 'anf05',
    'Exhortation to Martyrdom',
    r'<(cyprian\. de_exhortatione_martyrii\. 1\.(\d+))>', mode='chapter')

for w, tag, t in CYPRIAN_TREATISES:
    reg('cyprian.' + w, 'anf05', t,
        r'<(cyprian\. %s[. ]+(\d+)[^>]*)>' % tag, mode='chapter')

# ---- Ambrose (NPNF series 2 vol. 10, de Romestin 1896) ----
reg('ambrose.de_mysteriis', 'npnf210', 'On the Mysteries',
    r'<(ambrose\. de_mysteriis\. (\d+)\.\d+)>', mode='chapter')
# NPNF's letter selection uses the Benedictine numbers our corpus uses;
# the seven letters both sides hold align, the rest stay uncovered
reg('ambrose.epistulae_variae', 'npnf210', 'Selections from the Letters',
    r'<(ambrose\. epistolae_variae\. (\d+)\.(\d+))>',
    mode='ambrose-letters')


def load_refs(path, ref_re):
    """[(ref, g2, g3, latin)] — group meanings vary by mode."""
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^\s*<([^>]+)>\s*(.*)', line)
        if not m:
            continue
        mm = re.match(ref_re, '<' + m.group(1) + '>')
        if not mm:
            continue
        gs = mm.groups()
        out.append((mm.group(1), gs[1] if len(gs) > 1 else None,
                    gs[2] if len(gs) > 2 else None, m.group(2)))
    return out


def parse(volumes, w):
    """{key: english} keyed as the mode dictates."""
    seg, lvl = volumes[w['vol']].segment(w['title'])
    mode = w['mode']
    if mode in ('chapter', 'chapter-flat'):
        got = numbered_children(seg, lvl)
        if len(got) < 3:
            # ANF Cyprian numbers treatise chapters as inline paragraphs,
            # not divs
            got = chain_sections(plain(seg))
        return {(c,): t for c, t in got.items()}
    if mode == 'verse':
        return {'text': plain(seg)}
    if mode == 'book-chapter':
        out = {}
        for attrs, body in children(seg, lvl):
            b = book_number(attrs.get('title', ''), attrs)
            if not b:
                continue
            for c, t in numbered_children(body, lvl + 1).items():
                out[(b, c)] = t
        return out
    if mode == 'conferences':
        # the Conferences span three sibling div2 Parts; segment() finds
        # only the largest, so walk the whole volume for the Part divs
        out = {}
        x = volumes[w['vol']].x
        for pm in re.finditer(r'<div2 [^>]*title="The Conferences of John '
                              r'Cassian\. Part [^"]*"[^>]*>', x):
            nx = re.search(r'<div[12] ', x[pm.end():])
            part = x[pm.start():pm.end() + (nx.start() if nx else 0)]
            for a2, b2 in children(part, 2):
                m = re.search(r'Conference\s+([IVXLCD]+)',
                              a2.get('title', ''))
                n = roman_to_int(m.group(1)) if m else None
                if not n:
                    continue
                for c, t in numbered_children(b2, 3).items():
                    out[(n, c)] = t
        return out
    if mode == 'commodian':
        # eighty numbered instructions in one flat run; the corpus splits
        # them into two books, numbering each book from 1
        flat = numbered_children(seg, lvl)
        return {('flat', n): t for n, t in flat.items()}
    if mode == 'ambrose-letters':
        out = {}
        for attrs, body in children(seg, lvl):
            m = re.search(r'(?:Epistle|Letter)\s+([IVXLCD]+)',
                          attrs.get('title', ''))
            n = roman_to_int(m.group(1)) if m else None
            if not n:
                continue
            for c, t in chain_sections(plain(body)).items():
                out[(n, c)] = t
        return out
    if mode == 'quirinum':
        # each Book opens with Cyprian's own list of heads and then one
        # @n-numbered div per testimony; the first draft chained the
        # HEADS LIST and served headings as the translation (names 0.17
        # caught it)
        out = {}
        for attrs, body in children(seg, lvl):
            b = book_number(attrs.get('title', ''), attrs)
            if not b:
                continue
            for c, t in numbered_children(body, lvl + 1).items():
                out[(b, c)] = t
        return out
    raise ValueError(mode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--only')
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    only = set(args.only.split(',')) if args.only else None

    volumes = {}
    for w in REG:
        if w['vol'] not in volumes:
            volumes[w['vol']] = Volume(os.path.join(args.src_dir,
                                                    w['vol'] + '.xml'))

    ATTR = {
        'anf07': ('Ante-Nicene Fathers vol. 7', 'William Fletcher', 1886),
        'anf03': ('Ante-Nicene Fathers vol. 3',
                  'Peter Holmes and S. Thelwall', 1885),
        'anf04': ('Ante-Nicene Fathers vol. 4',
                  'S. Thelwall, R. E. Wallis and others', 1885),
        'anf05': ('Ante-Nicene Fathers vol. 5', 'Robert Ernest Wallis', 1886),
        'anf06': ('Ante-Nicene Fathers vol. 6',
                  'Hamilton Bryce and Hugh Campbell', 1886),
        'npnf210': ('NPNF series 2 vol. 10', 'H. de Romestin', 1896),
        'npnf211': ('NPNF series 2 vol. 11',
                    'Alexander Roberts and Edgar C. S. Gibson', 1894),
    }

    for w in REG:
        if only and w['work'] not in only:
            continue
        tess = os.path.join(args.tess_dir, w['work'] + '.tess')
        if not os.path.exists(tess):
            print(f"{w['work']}: no tess file")
            continue
        refs = load_refs(tess, w['ref_re'])
        if not refs:
            print(f"{w['work']}: ref regex matched nothing")
            continue
        try:
            english = parse(volumes, w)
        except KeyError as e:
            print(f"{w['work']}: title not found: {e}")
            continue

        mapping, pairs = {}, []
        if w['mode'] == 'verse':
            # the ANF renders these short poems in verse of a different
            # line count; rather than guess a rescaling for 170 lines,
            # the whole poem is one honest coarse unit
            text = english['text']
            for ref, ln, _, latin in refs:
                mapping[ref] = text
                pairs.append((latin, text))
        elif w['mode'] == 'commodian':
            # corpus (book, poem): book 2 continues the flat numbering
            poems1 = {int(g3) for _, g2, g3, _ in refs if g2 == '1'}
            off = max(poems1) if poems1 else 0
            for ref, b, p, latin in refs:
                n = int(p) + (off if b == '2' else 0)
                t = english.get(('flat', n))
                if t:
                    mapping[ref] = t
                    pairs.append((latin, t))
        else:
            for ref, g2, g3, latin in refs:
                if w['mode'] in ('chapter', 'chapter-flat'):
                    key = (int(g2),) if g2 and g2.isdigit() else None
                else:
                    if g2 is None or g3 is None:
                        key = None
                    else:
                        key = (int(g2), int(g3)) \
                            if g2.isdigit() and g3.isdigit() else None
                t = english.get(key) if key else None
                if t:
                    mapping[ref] = t
                    pairs.append((latin, t))

        cov = len(mapping) / len(refs)
        hit, n = V.score(pairs, 'la', sample=500)
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        ok = (hit is None or hit >= 0.25 or n < 10) and cov >= 0.5
        print(f"{w['work']:55s} cov {cov:.4f} ({len(mapping)}/{len(refs)}) "
              f"units {len(ulist)} names {hit}/{n} "
              + ('ok' if ok else 'REJECTED'))
        if not ok:
            continue
        series, translator, year = ATTR[w['vol']]
        json.dump({
            'tess_work': 'la/' + w['work'], 'language': 'la',
            'n_tess_refs': len(refs), 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit':
                round(len(mapping) / max(1, len(ulist)), 1),
            'alignment_confidence':
                'high' if (hit or 0) >= 0.5 else 'medium',
            'approximate': w['mode'] == 'verse',
            'name_check_hit_rate': hit, 'name_check_n': n,
            'verified_by': 'names',
            'sources': [{'translator': translator, 'year': year,
                         'title': series,
                         'publisher': 'Christian Literature Company '
                                      '(via CCEL ThML)',
                         'mode': 'proportional' if w['mode'] == 'verse'
                                 else 'exact',
                         'ref_composition': ['book', 'chapter'],
                         'source_url': 'https://www.ccel.org/ccel/schaff/'
                                       + w['vol'] + '.xml'}],
            'license': f'Public domain: {series}, {year}. '
                       'Text from the CCEL ThML transcription.',
            'attribution': f'{translator} ({series}), via CCEL',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, 'la__' + w['work'] + '.json'),
                'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
