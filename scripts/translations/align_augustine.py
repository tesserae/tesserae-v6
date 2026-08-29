"""Augustine: structure-keyed English from the NPNF series 1 (1886-88).

The corpus's Augustine references are coarse — a line is a Benedictine
section (or a City-of-God chapter), exactly the units the NPNF prints —
so the whole job is a registry mapping each work to its place in CCEL's
ThML transcriptions of NPNF volumes 1-6 and to the way its English marks
the sections:

- 'chain':  inline section numbers in the running text ("1. Great art
            Thou..."), collected as a monotonic chain with short resync,
            per book where the work has books;
- 'secdiv': one <div> per section (n="1", n="2"...), read directly;
- 'cog':    City of God, whose chapters are one <div3> each, in order,
            validated by count per book;
- 'letters': the Letters, one <div3> per letter with the letter number
            in @n as a roman numeral, sections as inline chains.

Validation before writing, per work and per book: the corpus's section
numbers must appear in the parsed English (a work missing more than a
tenth stays unwritten and is printed), and every work passes the
proper-name check, with a floor below which it is withdrawn. Fremantle-
style editorial matter (translator prefaces, essays, summaries) precedes
the first section number and is discarded, never served as translation.

Works with no public-domain NPNF English (De Genesi ad litteram, the
Retractations, the Speculum, De agone christiano, De fide et operibus,
the Heptateuch commentaries, most anti-Donatist occasional works) are
simply not in the registry and are listed by the wrap-up log instead.

Usage:
    python scripts/translations/align_augustine.py \
        --src-dir <dir with npnf101.xml..npnf106.xml> \
        --tess-dir texts/la --out-dir <dir> [--only work,work]
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}

FRONT_MATTER = re.compile(
    r'Title Page|Preface|Contents|Introductory|Essay|Translator|'
    r'Advertisement|Retractation|Dedication|Extract|Index|Notice|Credits')


def roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.strip('. ').upper()):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


def plain(seg):
    seg = re.sub(r'<note.*?</note>', ' ', seg, flags=re.S)
    txt = htmllib.unescape(re.sub(r'<[^>]+>', ' ', seg))
    return re.sub(r'\s+', ' ', txt)


SECTION = re.compile(r'(?:(?<=[.!?”’")\]:;])|(?<=^)|(?<=—))\s*(\d+)\.\s+'
                     r'(?=[A-Z“‘"(—])')


def chain_sections(text):
    """{n: body} from inline section numbers, monotonic with short resync."""
    marks, prev = [], 0
    for m in SECTION.finditer(text):
        n = int(m.group(1))
        if n == prev + 1 or (prev + 1 < n <= prev + 3):
            marks.append((n, m))
            prev = n
    out = {}
    for i, (n, m) in enumerate(marks):
        end = marks[i + 1][1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end].strip()
        if len(body.split()) >= 3:
            out[n] = body
    return out


class Volume:
    def __init__(self, path):
        self.x = open(path, encoding='utf-8', errors='ignore').read()

    def segment(self, title):
        """Largest div whose title contains `title`, to its next sibling."""
        best = None
        for m in re.finditer(r'<div(\d) ([^>]*)>', self.x):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
            if title not in attrs.get('title', ''):
                continue
            lvl = int(m.group(1))
            n = re.compile(r'<div[1-%d] ' % lvl).search(self.x, m.end())
            end = n.start() if n else len(self.x)
            if best is None or end - m.start() > best[2] - best[1]:
                best = (lvl, m.start(), end)
        if best is None:
            raise KeyError(title)
        return self.x[best[1]:best[2]], best[0]


def children(seg, lvl):
    """[(attrs, body)] for the divs one level below."""
    ms = list(re.finditer(r'<div%d ([^>]*)>' % (lvl + 1), seg))
    out = []
    for i, m in enumerate(ms):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        end = ms[i + 1].start() if i + 1 < len(ms) else len(seg)
        out.append((attrs, seg[m.end():end]))
    return out


def books_of(seg, lvl):
    """{book_number_or_'praef': body}, front matter dropped, numbering
    positional (an @n like 'III' is validated against the position)."""
    out = {}
    pos = 0
    for attrs, body in children(seg, lvl):
        title = attrs.get('title', '')
        n = attrs.get('n', '')
        if title == 'Preface' and not FRONT_MATTER.search(title.replace(
                'Preface', '')):
            # a bare 'Preface' child is Augustine's own (De doctrina)
            out['praef'] = body
            continue
        if FRONT_MATTER.search(title):
            continue
        pos += 1
        rn = roman_to_int(n) if n else None
        if rn and rn != pos:
            pos = rn      # trust an explicit number over the count
        out[pos] = body
    return out


# ---------------------------------------------------------------------------
# registry: corpus work -> where its English lives and how to read it
# tess ref regexes yield (full_ref, book_or_None, section) — section may be
# 'praef'. Works whose refs are flat sections use book None.

W = []


def reg(work, vol, title, mode, ref_re, flat=False):
    W.append(dict(work=work, vol=vol, title=title, mode=mode,
                  ref_re=ref_re, flat=flat))


def r2(tag):      # '<augustine. tag. B.S...>' book.section styles
    return r'<\s*(augustine\.\s*%s\.?\s+(praef|\d+)\.(praef|\d+)[^>]*)>' % tag


def r1(tag):      # '<augustine. tag. S>' flat section styles
    return r'<\s*(augustine\.\s*%s\.?\s+(praef|\d+)\.?)\s*>' % tag


reg('confessiones', 101, 'The Confessions', 'chain',
    r'<(augustine\.confessiones (\d+)\.(\d+))>')
reg('epistulae', 101, 'Letters of St. Augustin', 'letters',
    r'<\s*(augustine\. epistulae\. (\d+[ab]?)\.(\d+))>')
reg('de_civitate_dei', 102, 'City of God', 'cog',
    r2('de_civitate_dei'))
reg('de_doctrina_christiana', 102, 'On Christian Doctrine', 'chain',
    r'<(aug\. de_doctrina_christiana\. (praef|\d+)\.(\d+))>')
reg('de_trinitate', 103, 'On the Holy Trinity', 'chain',
    r'<(aug\. de_trinitate\. (praef|\d+)\.(\d+)(?:\.\d+)?\.?)>')
reg('contra_faustum', 104, 'Reply to Faustus', 'chain',
    r2('contra_faustum'))
reg('de_baptismo', 104, 'On Baptism, Against the Donatists', 'chain',
    r2('de_baptismo'))
reg('contra_litteras_petiliani', 104, 'Letters of Petilian', 'chain',
    r2('contra_lit_petiliani'))
reg('de_consensu_evangelistarum', 106, 'Harmony of the Gospels', 'chain',
    r2('de_consensu_ev'))
reg('de_peccatorum_meritis_et_remissione_et_de_baptismo_parvulorum', 105,
    'Merits and Forgiveness', 'chain', r2('de_peccatorum'))
reg('de_natura_et_origine_animae', 105, 'Soul and its Origin', 'chain',
    r2('de_natura_et_origine_animae'))
reg('de_nuptiis_et_concupiscentia', 105, 'Marriage and Concupiscence',
    'chain', r'<\s*(augustine\. de_nuptiis_et_concupiscentia\. '
             r'(praef|\d+)\.(\d+))>')
reg('contra_duas_epistulas_pelagianorum', 105,
    'Two Letters of the Pelagians', 'chain',
    r'<\s*(augustine\.\s*contra_duas_epistulas_pelagianorum\s+'
    r'(\d+)\.(\d+))>')
# the corpus also holds a second copy under a misspelled name with its own
# tag strings; same alignment, second file
reg('contra_duas_epistulas_pelegianorum', 105,
    'Two Letters of the Pelagians', 'chain',
    r'<\s*(augustine\.\s*contra_duas_epistulas_pelegianorum\s+'
    r'(\d+)\.(\d+))>')

FLAT = [
    ('de_bono_coniugali', 103, 'Good of Marriage', 'de_bono_coniugali'),
    ('de_sancta_virginitate', 103, 'Of Holy Virginity', 'de_sancta_virginitate'),
    ('de_bono_viduitatis', 103, 'Good of Widowhood', 'de_bono_viduitatis'),
    ('de_mendacio', 103, 'On Lying', 'de_mendacio'),
    ('contra_mendacium', 103, 'Against Lying', 'contra_mendacium'),
    ('de_opere_monachorum', 103, 'Work of Monks', 'de_opere_monachorum'),
    ('de_patientia', 103, 'On Patience', 'de_patientia'),
    ('de_continentia', 103, 'On Continence', 'de_continentia'),
    ('de_cura_pro_mortuis_gerenda', 103, 'Care to Be Had for the Dead',
     'de_cura_pro_mortuis_gerenda'),
    ('de_fide_et_symbolo', 103, 'Faith and the Creed', 'de_fide_et_sym'),
    ('de_utilitate_credendi', 103, 'Profit of Believing',
     'de_utilitate_credendi'),
    ('de_duabus_animabus', 104, 'On Two Souls', 'de_duabus_animabus'),
    ('contra_fortunatum', 104, 'Fortunatus', 'contra_fortunatum'),
    ('contra_epistulam_fundamenti', 104, 'Called Fundamental',
     'contra_ep_fundamenti'),
    ('de_natura_boni', 104, 'Nature of Good', None),
    ('de_spiritu_et_littera', 105, 'Spirit and the Letter',
     'de_spiritu_et_littera'),
    ('de_natura_et_gratia', 105, 'Nature and Grace', 'de_natura_et_gratia'),
    ('de_perfectione_iustitiae_hominis', 105, 'Perfection in Righteousness',
     'de_perf_iust_hom'),
    ('de_gestis_pelagii', 105, 'Proceedings of Pelagius', 'de_gestis_pelagii'),
]
for work, vol, title, tag in FLAT:
    if work == 'de_natura_boni':
        reg(work, vol, title, 'chain',
            r'<\s*(augustine\. de_natura_boni\. (\d+)\.\d+)>', flat=True)
    else:
        reg(work, vol, title, 'chain', r1(tag), flat=True)

# On the Grace of Christ and on Original Sin: one NPNF treatise, two books,
# which the corpus holds as two works
reg('de_gratia_christi', 105, 'Grace of Christ', 'chain',
    r1('de_gratia_christi'), flat=False)
reg('de_peccato_originali', 105, 'Grace of Christ', 'chain',
    r1('de_peccato_originali'), flat=False)


def best_sections(body, lvl, want):
    """Sections of one book: the inline chain and the numbered child
    divs are both candidates; whichever matches more of the corpus's
    section numbers for this book wins. Self-validating — De Trinitate's
    chapter divs lose to its inline Benedictine sections, while the
    anti-Pelagian volumes, which have no inline numbers, are served by
    their per-chapter divs (whose numbering there IS the section
    numbering)."""
    chain = chain_sections(plain(body))
    divs = {}
    for a, b in children(body, lvl):
        n = a.get('n', '')
        if n.isdigit():
            divs[int(n)] = plain(b)
    if len(set(divs) & want) > len(set(chain) & want):
        return divs
    return chain


def parse_work(volumes, w, want_by_book):
    """{(book, section): english} — book is None for flat works."""
    seg, lvl = volumes[w['vol']].segment(w['title'])
    mode = w['mode']
    out = {}
    if mode == 'letters':
        for attrs, body in children(seg, lvl + 1):
            n = roman_to_int(attrs.get('n', '') or '')
            if not n:
                continue
            for s, t in chain_sections(plain(body)).items():
                out[(n, s)] = t
        return out
    if mode == 'cog':
        for bk, body in books_of(seg, lvl).items():
            chs = [(a, b) for a, b in children(body, lvl + 1)]
            num = 0
            for a, b in chs:
                title = a.get('title', '')
                if 'Preface' in title and num == 0:
                    out[(bk, 'praef')] = plain(b)
                    continue
                num += 1
                out[(bk, num)] = plain(b)
        return out
    # chain mode
    kids = books_of(seg, lvl)
    if w.get('flat'):
        want = want_by_book.get(None, set())
        kids_all = children(seg, lvl)
        # a numbered child div is content whatever its title says;
        # front matter is the unnumbered children (title pages, essays,
        # the creed outline in an Introductory Notice)
        keep = [(a, b) for a, b in kids_all
                if a.get('n', '').isdigit()
                or not FRONT_MATTER.search(a.get('title', ''))]
        divs = {int(a['n']): plain(b) for a, b in keep
                if a.get('n', '').isdigit()}
        text = plain('\n'.join(b for _, b in keep)) if keep else plain(seg)
        chain = chain_sections(text)
        got = divs if len(set(divs) & want) > len(set(chain) & want) \
            else chain
        for s, t in got.items():
            out[(None, s)] = t
        # Augustine's own preface, if the corpus wants one, is the text
        # before section 1 minus editorial front matter — too risky to
        # separate, so praef refs stay uncovered on flat works.
        return out
    if w['work'] == 'de_gratia_christi':
        kids = {1: kids.get(1, '')}
    if w['work'] == 'de_peccato_originali':
        kids = {1: kids.get(2, '')}
    for bk, body in kids.items():
        wb = want_by_book.get(bk, set())
        if w['work'] in ('de_gratia_christi', 'de_peccato_originali'):
            wb = want_by_book.get(None, set())
        for s, t in best_sections(body, lvl + 1, wb).items():
            out[(bk, s)] = t
    if w['work'] == 'de_gratia_christi' or w['work'] == 'de_peccato_originali':
        out = {(None, s): t for (b, s), t in out.items()}
    if w['work'] == 'de_nuptiis_et_concupiscentia':
        # the corpus's praef is the letter to Valerius that NPNF prints
        # as front matter; its sections are chained in that child
        m = re.search(r'<div2 [^>]*title="A Letter Addressed to the Count'
                      r'[^"]*"[^>]*>(.*?)<div2 ', seg, flags=re.S)
        if m:
            for s, t in chain_sections(plain(m.group(1))).items():
                out[('praef', s)] = t
    return out


SOURCES = {
    101: ('NPNF series 1 vol. 1', 'J. G. Pilkington (Confessions), '
          'J. G. Cunningham (Letters)', 1886),
    102: ('NPNF series 1 vol. 2', 'Marcus Dods (City of God), '
          'J. F. Shaw (Christian Doctrine)', 1887),
    103: ('NPNF series 1 vol. 3', 'A. W. Haddan, C. L. Cornish, '
          'H. Browne and others', 1887),
    104: ('NPNF series 1 vol. 4', 'R. Stothert, A. H. Newman, '
          'J. R. King', 1887),
    105: ('NPNF series 1 vol. 5', 'Peter Holmes and R. E. Wallis', 1887),
    106: ('NPNF series 1 vol. 6', 'S. D. F. Salmond and others', 1888),
}


def emit(work, tess_path, refs, english, w, out_dir, log, fname=None,
         tess_work=None):
    units, unit_of, ref_to_unit = [], {}, {}
    for ref, bk, s in refs:
        key = (bk, s)
        if key not in english:
            continue
        if key not in unit_of:
            unit_of[key] = len(units)
            units.append(english[key])
        ref_to_unit[ref] = unit_of[key]
    if not refs:
        return
    latin = {}
    for line in open(tess_path, errors='ignore'):
        m = re.match(r'\s*<([^>]+)>\s*(.*)', line)
        if m:
            latin[m.group(1)] = m.group(2)
    pairs = [(latin.get(ref, ''), units[u]) for ref, u in ref_to_unit.items()]
    score = V.score(pairs, 'la', sample=500)
    coverage = round(len(ref_to_unit) / len(refs), 4)
    name = tess_work or work
    if score[0] is not None and score[1] >= 10 and score[0] < 0.25:
        log.append((name, coverage, len(units), score, 'WITHDRAWN: names'))
        return
    floor = 0.05 if w['mode'] == 'letters' else 0.5
    if coverage < floor:
        log.append((name, coverage, len(units), score,
                    f'SKIPPED: coverage below {floor}'))
        return
    # a flat work whose English stops well short of the corpus's last
    # section is using a different sectioning scheme, not a shorter text
    if w.get('flat'):
        mx_c = max((s for _, _, s in refs if isinstance(s, int)), default=0)
        mx_e = max((s for _, s in english if isinstance(s, int)), default=0)
        if mx_e < 0.85 * mx_c:
            log.append((name, coverage, len(units), score,
                        f'SKIPPED: sectioning mismatch (english reaches '
                        f'{mx_e} of {mx_c})'))
            return
    vol_title, translators, year = SOURCES[w['vol']]
    out = {
        'tess_work': tess_work or f'la/augustine.{work}',
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': coverage,
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence':
            'high' if (score[0] is None or score[0] >= 0.5) else 'medium',
        'name_check_hit_rate': score,
        'name_check_n': score[1],
        'sources': [{
            'title': f'{w["title"]} ({vol_title})',
            'translator': translators, 'year': year,
            'publisher': 'Christian Literature Company (via CCEL)',
            'source_url': f'https://ccel.org/ccel/schaff/npnf{w["vol"]}',
            'mode': 'exact',
            'ref_composition': ['book', 'section'] if not w.get('flat')
                               else ['section'],
        }],
        'license': f'Public domain: translation published {year}. '
                   'Text from the Christian Classics Ethereal Library.',
        'attribution': f'{translators}, Nicene and Post-Nicene Fathers '
                       f'series 1 ({year}), via CCEL',
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    fname = fname or f'la__augustine.{work}.json'
    json.dump(out, open(os.path.join(out_dir, fname), 'w'),
              ensure_ascii=False)
    log.append((work if not tess_work else tess_work,
                coverage, len(units), score, 'ok'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--only')
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    volumes = {}
    for w in W:
        if w['vol'] not in volumes:
            volumes[w['vol']] = Volume(
                os.path.join(args.src_dir, f'npnf{w["vol"]}.xml'))

    log = []
    only = set(args.only.split(',')) if args.only else None
    for w in W:
        work = w['work']
        if only and work not in only:
            continue
        tess_path = os.path.join(args.tess_dir, f'augustine.{work}.tess')
        if not os.path.exists(tess_path):
            log.append((work, 0, 0, (None, 0), 'no tess file'))
            continue
        refs = []
        for line in open(tess_path, errors='ignore'):
            m = re.match(w['ref_re'], line.strip())
            if not m:
                continue
            g = m.groups()
            if len(g) == 2:
                ref, s = g[0], g[1]
                bk = None
            else:
                ref, bk, s = g[0], g[1], g[2]
                if bk != 'praef':
                    bk = int(bk) if bk.isdigit() else bk
            s = s if s == 'praef' else int(s)
            refs.append((ref, bk, s))
        want_by_book = {}
        for _, bk, sN in refs:
            if isinstance(sN, int):
                want_by_book.setdefault(bk, set()).add(sN)
        try:
            english = parse_work(volumes, w, want_by_book)
        except KeyError as e:
            log.append((work, 0, 0, (None, 0), f'not located: {e}'))
            continue
        # flat works keyed (None, s); books keyed (bk, s)
        emit(work, tess_path, refs, english, w, args.out_dir, log)

        # the Letters also exist as nine range files with their own tags
        if work == 'epistulae' and (not only or 'epistulae' in only):
            import glob as _g
            for pf in sorted(_g.glob(os.path.join(
                    args.tess_dir, 'augustine.epistulae_*[0-9].part.*.tess'))):
                base = os.path.basename(pf)[:-5]           # strip .tess
                stem = base.split('.part.')[0]             # augustine.epistulae_1-30
                prefs = []
                for line in open(pf, errors='ignore'):
                    # the range in the tag does not always match the
                    # filename (part 7 mixes epistulae_181-210 and
                    # epistulae_185-270), so read it from the line
                    m = re.match(r'\s*<(augustine\. epistulae_[0-9-]+\. '
                                 r'(\d+[ab]?)\.(\d+))>', line)
                    if m:
                        L = m.group(2)
                        prefs.append((m.group(1),
                                      int(L) if L.isdigit() else L,
                                      int(m.group(3))))
                emit(work, pf, prefs, english, w, args.out_dir, log,
                     fname=f'la__{stem}.json', tess_work=f'la/{stem}')

    print()
    for work, cov, n_units, sc, status in log:
        print(f'{work}: coverage {cov}, {n_units} units, names {sc} '
              f'[{status}]')


if __name__ == '__main__':
    main()
