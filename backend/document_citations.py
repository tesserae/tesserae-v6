"""Document-citation recogniser: references in scholarly prose to inscriptions,
papyri, ostraca and coins ("CIL VI 1234", "AE 1976, 123", "IG II² 1234",
"P.Oxy. XII 1453", "RIC I² 207"), normalised to a key and, where the documents
collection stores a matching edition reference, linked to a document id.

This sits beside backend/citations (literary citations such as "Aen. 1.1") and
does not change how those are resolved. backend.citations.extract_documents()
is the entry point.

A recognised reference is a dict:
    family      'CIL' 'ILS' 'AE' 'IG' 'SEG' 'ILLRP' 'CLE' 'RIB' 'CIG' 'SIG'
                'PAP' (papyri, ostraca, tablets) 'RIC' 'RRC' 'BMC' 'RPC'
    series      the corpus abbreviation as normalised ('P.Oxy', 'BGU', 'AE')
    volume      string or None. Arabic digits. For AE the year; for IG and
                RPC a part is appended with a dot ('12.5' for IG XII 5)
    edition     2 or 3 for a second or third edition (IG I³, CIL I², RIC I²)
    number      int or None
    number_end  int, for a range ("RIB 1234-1236")
    sub         letter or sub-number ('a' in AE 1975, 422a; '1' in RRC 335/1)
    surface, start, end   what was matched and where
    key         'family:series:volume:number:sub' with '^2'/'^3' after volume

Linking (DocumentEditionIndex) reads the `principal_edition` column of the
documents collection's metadata.db, runs the SAME recogniser over each stored
string, and maps (series, volume, number) to document ids. A citation without a
sub-letter matches every lettered document ("AE 1975, 422" -> 422a..422g); one
with a letter matches that letter and the unlettered document. A citation
without a volume matches only when the stored references for that number share
one volume.
"""
import json
import os
import re
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))

_ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def _roman(s):
    """Value of a well-formed Roman numeral, else None (rejects 'IIII', 'VX',
    'IC' so that stray capitals are not read as volumes)."""
    s = s.upper()
    if not s or not re.fullmatch(r'M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})', s):
        return None
    t = prev = 0
    for ch in reversed(s):
        v = _ROMAN[ch]
        t += v if v >= prev else -v
        prev = max(prev, v)
    return t or None


def _vol(tok):
    """Volume token (Roman or Arabic) -> int, else None."""
    if tok is None:
        return None
    if tok.isdigit():
        return int(tok)
    return _roman(tok)


def _load_series():
    try:
        with open(os.path.join(_HERE, 'citations', 'papyri_series.json'), encoding='utf-8') as f:
            names = set(json.load(f))
    except (OSError, ValueError):
        names = set()
    # Hand additions: tablets, and series too rare in the collection to list.
    names |= {'T.Vindol', 'T.Albertini', 'T.Sulpicii', 'T.Mom', 'T.Vindon', 'P.Oxy', 'P.Mich',
              'P.Tebt', 'P.Lond', 'P.Ryl', 'P.Hib', 'P.Amh', 'P.Fay', 'P.Flor', 'P.Giss',
              'P.Petr', 'P.Col', 'P.Princ', 'P.Yale', 'P.Dura', 'P.Berl', 'P.Cair', 'P.Wisc',
              'P.Turner', 'P.Ant', 'P.Corn', 'P.Grenf', 'P.Mert', 'P.Rain', 'P.Sakaon',
              'P.Vindob', 'P.Zen', 'O.Wilck', 'O.Claud', 'O.Did', 'O.Bodl', 'O.Mich'}
    return names


_SERIES = _load_series()
# Latin abbreviations that look like "P.Xxx." but are praenomen + name.
_NOT_SERIES = {'P.Vergil', 'P.Verg', 'P.Ovid', 'P.Terent', 'P.Cornel', 'P.Corn', 'P.Sest',
               'P.Clodius', 'P.Cic', 'P.Scip', 'P.Sull', 'P.Syr', 'P.Quinct', 'P.Sulp'}
# 'P.Corn' is a real papyrus series (Cornell); keep it known, block the rest.
_NOT_SERIES.discard('P.Corn')

_SUBSERIES = {'Zen', 'Louvre', 'Taxes', 'Wagner', 'GPW', 'Shelt', 'Mus', 'Masp', 'Georg',
              'Zill', 'Vogl', 'Epiph', 'Copt', 'Inst', 'Preis', 'Sakaon', 'Mich'}

# ---------------------------------------------------------------- building blocks
ROM = r'[IVXLC]{1,6}'
ARA = r'\d{1,3}'
VOL = rf'(?:{ROM}|{ARA})'
SEP = r'(?:\s*[,.:]\s*|\s+)'
NO = r'(?:(?:n[or]?|nos?)\.?\s*)?'
NUM = r'(?P<num>\d{1,6})(?P<sub>[a-z])?(?![A-Za-z0-9])(?:\s?[-–]\s?(?P<end>\d{1,6})(?![A-Za-z0-9]))?'
ED = r'(?P<ed>[²³]|\(?\^?[23]\)?(?=\s|,|\.))?'

_HOMOGLYPH = {0x399: 'I', 0x3a7: 'X'}


def _c(p, flags=0):
    return re.compile(p, flags)


_CIL = _c(
    rf'(?<![A-Za-z])(?:C\.\s?I\.\s?L\.|CIL)[,.]?\s*(?:vol(?:ume)?\.?\s*|t(?:om)?\.\s*)?'
    rf'(?:(?P<vol>{VOL})(?P<ed>[²³]|(?<=[IVX])[23](?=\s|,|\.))?'
    rf'(?:\s*\((?P<ed2>[23])\s*\.?\s*(?:Aufl\.|ed\.?|edn\.?|[e\u00e9]d\.?)\s*\))?'
    rf'(?P<supp>\s*,?\s*(?:suppl?\.|add\.|S\.)(?=\s*\d))?{SEP}(?:{NO})?'
    rf'|(?=\d{{3,6}}(?![\d])))'
    rf'(?P<n1>\d{{1,6}})(?P<sub>[a-z])?(?![A-Za-z0-9])'
    rf'(?:\s*,\s*(?P<n2>\d{{2,6}})(?![A-Za-z0-9])(?!\s*[-–]\s*\d)|(?:\s?[-–]\s?(?P<end>\d{{1,6}})(?![A-Za-z0-9])))?')
_ILS = _c(
    rf'(?<![A-Za-z])(?:ILS|I\.\s?L\.\s?S\.)\s*(?:(?P<vol>I{{1,3}})[,.]?\s+(?:\d\s*,\s*)?(?=\d))?{NO}{NUM}')
_AE = _c(
    r"(?<![A-Za-z])(?:AE|A\.\s?E\.|L['’]Ann[eé]e [eé]pigraphique|Ann\.\s?[EÉ]p\.)\s*"
    r"(?P<vol>(?:1[89]\d\d|20[0-3]\d)(?:/\d{2,4})?)\s*(?:[,.:]\s*|\s+)" + NO + r"(?P<num>\d{1,4})(?P<sub>[a-z]{1,3}\d?)?(?![A-Za-z0-9])"
    r"(?:\s?[-–]\s?(?P<end>\d{1,4})(?![A-Za-z0-9]))?")
_IG = _c(
    rf'(?<![A-Za-z])(?:IG|I\.\s?G\.)\s*(?:vol\.?\s*)?(?P<vol>{ROM}|\d{{1,2}})'
    rf'(?:\s?[,./]\s?(?P<part>\d{{1,2}}))?(?P<ed>[²³]|(?<=[IVX\d])[23](?=\s|,|\.))?'
    rf'(?P<supp>\s*,?\s*suppl?\.(?=\s*\d))?{SEP}{NO}'
    rf'(?P<n1>\d{{1,5}})(?P<sub>[a-z])?(?![A-Za-z0-9])'
    rf'(?:\s*,\s*(?P<n2>\d{{1,5}})(?![A-Za-z0-9])|(?:\s?[-–]\s?(?P<end>\d{{1,5}})(?![A-Za-z0-9])))?')
_SEG = _c(
    rf'(?<![A-Za-z])SEG\s*(?P<vol>{ROM}|\d{{1,2}})(?:\s*\((?:1[89]|20)\d\d\))?{SEP}{NO}'
    r'(?P<num>\d{1,4})(?P<sub>[a-z]{1,3})?(?![A-Za-z0-9])(?:\s?[-–]\s?(?P<end>\d{1,4})(?![A-Za-z0-9]))?')
_ILLRP = _c(r'(?<![A-Za-z])ILLRP\s*' + NO + NUM)
_CLE = _c(r'(?<![A-Za-z])CLE\s*' + NO + NUM + r'(?!\.\d)')
_RIB = _c(
    r'(?<![A-Za-z])RIB\s*(?:(?P<vol>I{1,3})(?P<ed>[²³])?[,.\s]\s*)?' + NO +
    r'(?P<num>\d{1,4})(?:\.(?P<subn>\d{1,3}))?(?P<sub>[a-z])?(?![A-Za-z0-9])'
    r'(?:\s?[-–]\s?(?P<end>\d{1,4})(?![A-Za-z0-9]))?')
_CIG = _c(r'(?<![A-Za-z])(?:C\.\s?I\.\s?Gr?\.|CIG)[.,]?\s*(?:(?P<sept>Sept(?:entr)?\.?)\s*)?(?P<vol>[ivxIVX]{1,4})?[,.]?\s*'
          + NO + r'(?P<num>\d{1,5})(?P<sub>[a-z])?(?![A-Za-z0-9])')
_SIG = _c(rf'(?<![A-Za-z])(?:SIG|Syll\.|Sylloge)(?P<ed>[23])?\s*(?:\((?P<ed2>[23])(?:nd|rd)? ?ed\.?\)\s*)?{NO}(?P<num>\d{{1,4}})(?![A-Za-z0-9])')

_RIC = _c(
    rf'(?<![A-Za-z])RIC\s*(?:(?P<vol>[IVX]{{1,4}})(?:\.(?P<part>\d))?(?P<ed>[²³]|(?<=[IVX])[23](?=\s|,|\.))?'
    rf'(?:\s*\((?P<ed2>[23])(?:nd|rd)?\s*ed\.?\))?{SEP})?{NO}'
    r'(?P<num>\d{1,4})(?P<sub>[a-z])?(?![A-Za-z0-9])')
_RRC = _c(r'(?<![A-Za-z])(?:RRC|Crawford)(?:,?\s*RRC)?\s*(?:no\.?\s*)?(?P<num>\d{1,3})(?:/(?P<subn>\d{1,3})(?P<sub>[a-z])?)?(?![A-Za-z0-9/])')
_BMC = _c(
    rf'(?<![A-Za-z])(?P<fam>BMCRE|BMCRR|BMCEmp\.?)\s*(?P<vol>{VOL})?(?:\s*[,.]\s*|\s+)'
    r'(?:pp?\.\s*\d+\s*,?\s*(?=nos?\.))?(?:nos?\.?\s*)?(?P<num>\d{1,5})(?![A-Za-z0-9])')
_RPC = _c(
    rf'(?<![A-Za-z])RPC\s*(?P<vol>{VOL})(?:\s?[.,]\s?(?P<part>\d))?(?P<supp>\s*(?:suppl?\.|S)\s*\d?)?'
    rf'{SEP}(?:temp\.\s*)?{NO}(?P<num>\d{{1,5}})(?![A-Za-z0-9])')

# Series-keyed volumes: abbreviation, then [volume] number.
_VOLSERIES = _c(
    r'(?<![A-Za-z.])(?P<ser>BGU|SPP|CPR|PSI|UPZ|ChLA|SB|PUG|CPL|CPJ|FIRA|MChr|WChr|SPP)\s*'
    rf'(?:(?P<rv>{ROM}[AB]?)(?:[\s,.]+|(?<=[IVXLC])(?=\d{{2}}))(?P<rn>\d{{1,6}})(?![A-Za-z0-9])|(?P<a>\d{{1,6}})(?:(?P<sep>[\s.,]+)(?P<b>\d{{1,6}}))?(?![A-Za-z0-9]))')
_PAPSER = _c(
    r'(?<![A-Za-z.])(?P<ser>[POT]\.\s?[A-Z][A-Za-zÀ-ÿ]*\.?)'
    r'(?P<sub1>(?:\s?(?![IVXLC]+\b)[A-Z][A-Za-z]{1,12}\.?){0,2})\s*'
    rf'(?:vol\.?\s*)?(?:(?P<rv>{ROM})(?![A-Za-z])(?:[\s,.]+|(?<=[IVXLC])(?=\d{{2}}))(?P<rn>\d{{1,6}})(?![A-Za-z0-9])|(?P<a>\d{{1,6}})(?:(?P<sep>[\s.,]+)(?P<b>\d{{1,6}}))?(?![A-Za-z0-9]))')


def _mk(family, series, vol, num, m, edition=None, sub=None, end=None, **extra):
    d = {'family': family, 'series': series,
         'volume': None if vol is None else str(vol),
         'edition': edition, 'number': num, 'number_end': end, 'sub': sub,
         'surface': m.group(0).strip(), 'start': m.start(), 'end': m.start() + len(m.group(0).rstrip())}
    d.update(extra)
    d['key'] = make_key(d)
    return d


def make_key(d):
    v = d['volume'] if d['volume'] is not None else ''
    if d.get('edition'):
        v += '^%d' % d['edition']
    return '%s:%s:%s:%s:%s' % (d['family'], d['series'], v, '' if d['number'] is None else d['number'], d['sub'] or '')


def _ed(g):
    if not g:
        return None
    g = re.sub(r'[^\d²³]', '', g)
    return {'²': 2, '³': 3, '2': 2, '3': 3}.get(g)


def _int(s):
    return int(s) if s is not None else None


# ---------------------------------------------------------------- family handlers
def _h_cil(m):
    vol = _vol(m.group('vol')) if m.group('vol') else None
    if m.group('vol') and not vol:
        return None
    if vol is not None and not 1 <= vol <= 18:
        return None
    n1, n2 = _int(m.group('n1')), _int(m.group('n2'))
    part = None
    num, sub = n1, m.group('sub')
    if (vol is not None and n2 is not None and m.group('sub') is None
            and ((n1 <= 8 and len(m.group('n2')) >= 3) or (m.group('ed2') and n1 <= 14))):
        part, num = n1, n2          # CIL VI 4, 1234 (pars 4); CIL II (2. Aufl.) 14, 236
    elif n2 is not None:
        pass                        # "CIL III 14206, 3 ..." the tail is a sub-reference, ignored
    ed = _ed(m.group('ed') or m.group('ed2')) if (m.group('ed') and vol == 1) or m.group('ed2') else None
    if vol is None and (num is None or num < 100):
        return None
    d = _mk('CIL', 'CIL', vol if not part else '%d.%d' % (vol, part), num, m, edition=ed, sub=sub,
            end=_int(m.group('end')))
    if m.group('supp'):
        d['supplement'] = True
    if part:
        d['part'] = part
    return d


def _h_simple(family, series, valid=None):
    def h(m):
        num = _int(m.group('num'))
        if valid and not valid(num):
            return None
        return _mk(family, series, None, num, m, sub=m.group('sub'), end=_int(m.groupdict().get('end')))
    return h


def _h_ils(m):
    num = _int(m.group('num'))
    if not 1 <= num <= 9999:
        return None
    return _mk('ILS', 'ILS', None, num, m, sub=m.group('sub'), end=_int(m.group('end')))


def _h_ae(m):
    return _mk('AE', 'AE', m.group('vol'), int(m.group('num')), m, sub=m.group('sub'), end=_int(m.group('end')))


# IG volumes that are issued in parts (fascicles) cited as "XII 5, 123".
_IG_PARTED = {4, 5, 7, 9, 10, 11, 12, 14}


def _h_ig(m):
    vol = _vol(m.group('vol'))
    if vol is None or not 1 <= vol <= 14:
        return None
    n1, n2 = _int(m.group('n1')), _int(m.group('n2'))
    part = _int(m.group('part'))
    num, sub = n1, m.group('sub')
    if part is None and n2 is not None and vol in _IG_PARTED and n1 <= 14 and sub is None:
        part, num = n1, n2
    elif part is not None and n2 is not None and n1 <= 14 and len(m.group('n2')) >= 2 and sub is None:
        num = n2
    volume = str(vol) if part is None else '%d.%d' % (vol, part)
    d = _mk('IG', 'IG', volume, num, m, edition=_ed(m.group('ed')), sub=sub, end=_int(m.group('end')))
    d['volume'] = volume
    d['key'] = make_key(d)
    if m.group('supp'):
        d['supplement'] = True
    return d


def _h_seg(m):
    vol = _vol(m.group('vol'))
    if vol is None or not 1 <= vol <= 80:
        return None
    return _mk('SEG', 'SEG', vol, int(m.group('num')), m, sub=m.group('sub'), end=_int(m.group('end')))


def _h_rib(m):
    vol = _vol(m.group('vol')) if m.group('vol') else None
    if m.group('vol') and (vol is None or vol > 3):
        return None
    sub = m.group('subn') or m.group('sub')
    ed = _ed(m.group('ed')) if m.group('ed') else None
    return _mk('RIB', 'RIB', vol, int(m.group('num')), m, edition=ed, sub=sub, end=_int(m.group('end')))


def _h_cig(m):
    return _mk('CIG', 'CIG', _vol(m.group('vol')) if m.group('vol') else None, int(m.group('num')), m,
               sub=m.group('sub'), sept=bool(m.group('sept')))


def _h_sig(m):
    ed = _ed(m.group('ed') or m.group('ed2'))
    return _mk('SIG', 'SIG', None, int(m.group('num')), m, edition=ed)


def _h_ric(m):
    vol = _vol(m.group('vol')) if m.group('vol') else None
    if m.group('vol') and (vol is None or vol > 10):
        return None
    ed = _ed(m.group('ed') or m.group('ed2'))
    if vol is None and not re.search(r'(?:no|nr?)\.', m.group(0)) and ed is None and False:
        return None
    volume = None if vol is None else (str(vol) if not m.group('part') else '%d.%s' % (vol, m.group('part')))
    d = _mk('RIC', 'RIC', volume, int(m.group('num')), m, edition=ed, sub=m.group('sub'))
    return d


def _h_rrc(m):
    return _mk('RRC', 'RRC', None, int(m.group('num')), m, sub=m.group('subn') and (m.group('subn') + (m.group('sub') or '')))


def _h_bmc(m):
    fam = m.group('fam').rstrip('.')
    vol = _vol(m.group('vol')) if m.group('vol') else None
    if m.group('vol') and vol is None:
        return None
    return _mk('BMC', fam, vol, int(m.group('num')), m)


def _h_rpc(m):
    vol = _vol(m.group('vol'))
    if vol is None or vol > 12:
        return None
    volume = str(vol) if not m.group('part') else '%d.%s' % (vol, m.group('part'))
    d = _mk('RPC', 'RPC', volume, int(m.group('num')), m)
    if m.group('supp'):
        d['supplement'] = True
    return d


def _pap(m, ser, rv, rn, a, sep, b):
    vol = num = None
    if rv is not None:
        v = _roman(rv[:-1]) if rv[-1:] in 'AB' and len(rv) > 1 else _roman(rv)
        if v is None:
            return None
        vol, num = v, int(rn)
    else:
        a_i = int(a)
        if b is not None and a_i <= 120 and (',' not in sep or len(b) >= 3) and len(a) <= 3:
            vol, num = a_i, int(b)
        else:
            num = a_i
    if num == 0:
        return None
    # "P.Mich. IV,2 S. XII": a small number followed by a page marker is a page
    # of the volume's front matter, not an item.
    used_end = m.end('b') if (b is not None and vol is not None and rv is None) else (
        m.end('rn') if rv is not None else m.end('a'))
    if num < 20 and re.match(r'\s*,?\s*(?:S|pp?|Anm|Kol)\.', m.string[used_end:used_end + 8]):
        return None
    return vol, num


def _canon_ser(raw):
    return re.sub(r'\s+', '', raw).rstrip('.')


def _h_volser(m):
    ser = m.group('ser')
    r = _pap(m, ser, m.group('rv'), m.group('rn'), m.group('a'), m.group('sep') or '', m.group('b'))
    if r is None:
        return None
    vol, num = r
    if ser == 'SB':
        # Bare "SB 12" is rarely Sammelbuch: a volume needs a number after it,
        # and a bare number must look like an item number, not a small count or a year.
        if vol is None and (num < 100 or 1900 <= num <= 2030):
            return None
        if vol is not None and vol > 40:
            return None
    if ser in ('BGU', 'CPR', 'SPP', 'PSI', 'UPZ') and vol is not None and vol > 60:
        return None
    return _mk('PAP', ser, vol, num, m)


def _h_papser(m):
    raw = m.group('ser')
    sub1 = (m.group('sub1') or '').strip()
    first = _canon_ser(raw)
    prefix_space = re.match(r'[POT]\.\s', raw) is not None
    ends_dot = raw.endswith('.')
    known = first in _SERIES
    if first in _NOT_SERIES:
        return None
    # An unlisted series needs the compact dotted form and a real word: "O.T.", "O.C.", "P.V.",
    # "P.L." are Sophocles, Aeschylus, Milton in the literary commentaries.
    if not known and (prefix_space or not ends_dot or len(first) < 6):
        return None
    if first.endswith('.') or not first[2:3].isupper():
        return None
    series = first
    if sub1:
        if not known:
            return None
        toks = [t.rstrip('.') for t in re.findall(r'[A-Z][A-Za-z]*\.?', sub1)]
        series = '.'.join([first] + toks)
    r = _pap(m, series, m.group('rv'), m.group('rn'), m.group('a'), m.group('sep') or '', m.group('b'))
    if r is None:
        return None
    vol, num = r
    return _mk('PAP', series, vol, num, m, known=known)


_FAMILIES = [
    (_CIL, _h_cil), (_ILS, _h_ils), (_AE, _h_ae), (_IG, _h_ig), (_SEG, _h_seg),
    (_ILLRP, _h_simple('ILLRP', 'ILLRP', lambda n: 1 <= n <= 1400)),
    (_CLE, _h_simple('CLE', 'CLE', lambda n: 1 <= n <= 2200)),
    (_RIB, _h_rib), (_CIG, _h_cig), (_SIG, _h_sig),
    (_VOLSERIES, _h_volser), (_PAPSER, _h_papser),
    (_RIC, _h_ric), (_RRC, _h_rrc), (_BMC, _h_bmc), (_RPC, _h_rpc),
]


def find_document_citations(text):
    """Recognised document references in `text`, in order, non-overlapping."""
    if not text:
        return []
    # NBSP, and Greek capitals typed for Latin ones (Iota in IG): same length, so offsets hold.
    text = text.replace('\u00a0', ' ').translate(_HOMOGLYPH)
    found = []
    for rx, handler in _FAMILIES:
        for m in rx.finditer(text):
            d = handler(m)
            if d is not None:
                found.append(d)
    found.sort(key=lambda d: (d['start'], -(d['end'] - d['start'])))
    out, last = [], -1
    for d in found:
        if d['start'] >= last:
            out.append(d)
            last = d['end']
    return out


# ---------------------------------------------------------------- linking
# Volume-less stored references from a source whose volume is fixed by place.
_SOURCE_DEFAULT_VOL = {('isicily', 'CIL'): '10', ('isicily', 'IG'): '14'}


class DocumentEditionIndex:
    """(family, series, volume, number) -> document ids, built from stored
    principal_edition strings with the same recogniser."""

    def __init__(self):
        self.by_num = {}      # (family, series, number) -> {volume: [(doc_id, sub, edition)]}
        self.docs_with = {}   # family -> set(doc_id)
        self.n_docs = 0
        self.n_with_edition = 0

    def add(self, doc_id, source, text):
        self.n_docs += 1
        if not text:
            return
        self.n_with_edition += 1
        for c in find_document_citations(text):
            vol = c['volume']
            if vol is None:
                vol = _SOURCE_DEFAULT_VOL.get((source, c['family']))
            self.by_num.setdefault((c['family'], c['series'], c['number']), {}).setdefault(vol, []).append(
                (doc_id, c['sub'], c['edition']))
            self.docs_with.setdefault(c['family'], set()).add(doc_id)

    @classmethod
    def from_rows(cls, rows):
        idx = cls()
        for doc_id, source, text in rows:
            idx.add(doc_id, source, text)
        return idx

    @classmethod
    def from_metadata_db(cls, path):
        conn = sqlite3.connect('file:%s?mode=ro&immutable=1' % path, uri=True)
        try:
            return cls.from_rows(conn.execute('SELECT id, source, principal_edition FROM documents'))
        finally:
            conn.close()

    def link(self, cit):
        """Document ids holding this citation as an edition reference ([] if none)."""
        vols = self.by_num.get((cit['family'], cit['series'], cit['number']))
        if not vols:
            return []
        if cit['volume'] is not None:
            entries = vols.get(cit['volume'], [])
        elif len(vols) == 1:
            entries = next(iter(vols.values()))
        else:
            entries = []
        out = []
        for doc_id, sub, ed in entries:
            if cit['edition'] and ed and cit['edition'] != ed:
                continue
            if cit['sub'] and sub and cit['sub'] != sub:
                continue
            out.append(doc_id)
        return sorted(set(out))


def link_documents(cits, index):
    """Attach 'doc_ids' to each citation using a DocumentEditionIndex."""
    for c in cits:
        c['doc_ids'] = index.link(c)
    return cits
