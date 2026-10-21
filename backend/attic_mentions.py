"""Attic matcher: the People & Places mentions for the Attic Inscriptions Online documents (2026-10-20).

The generic documents builder (backend/entity_extras.build_document_mentions) reads a token as a name
when it equals a form of an entity or its stem plus a case ending. On literary Latin and on Roman
inscriptions that was measured good enough. On Attic inscriptions about half of its rows were wrong, for
reasons that belong to Attic texts: a citizen is named with a father's name and a deme (a demotic is an
adjective of a place that reads like a personal name), the year is named by an archon, and the gods are
named in the dative in dedications. This module takes the builder's candidate rows, reads each candidate
at its place in the document and drops the ones these rules reject, and adds the demes and gods that the
builder missed. It never writes a row for any other document.

The rules, in the order they are applied (an occurrence is dropped by the first rule that rejects it):

  name_entity       an entity of type 'name' (a corpus name with no referent) is not a link.
  month             the name of an Attic month (Mounichion, Posideon, Thargelion) is not the harbor, the
                    god or the festival that shares its stem.
  demotic           a demotic (Phrearrios, Sphettios, Paianieus) names a deme. It links to the deme's place
                    entity when the store has one and to nothing else, never to a person.
  athena_or_athens  Athenai (Athens) and Athenas are also the dative of Athena and the genitive of Athena. The
                    accent decides (the circumflex on the eta is the city, on the alpha the goddess). A token
                    with no accent is left unlinked.
  god_name          the name of a god in a dedication (Dios, Asklepiou, Athenai, Apollonos) links to the god's
                    entity, never to a person, a place or a name entity with the same spelling.
  deity_form        a god is linked only by the table of god forms; any other word the generic matcher read as a
                    deity (the personal name Lachesis for Lakhes, Hera for Heras) is not a god.
  archon_date       a name between epi and archontos (or after epi archontos) is the archon of the year. It
                    links to a person entity only when that entity's description names an archonship.
  masculine_name    a masculine personal-name form (-ios, -iou, -iwi, -ion, -ioi, -ias) is not a feminine or
                    neuter place name (Apollonios is not Apollonia). The ethnic of a place (-aios) is kept.
  patronymic        a genitive that follows a name (X Y-ou, X Y-os) is the father (or the son of a place-like
                    name such as Kithairon): unlinked, whatever the entity is.
  name_then_patronymic  a place or a people read as a name that a father's name follows (Eurymedon
                    Hegemachou) is a man.
  person            a person entity is not linked. Nearly every personal name in an Attic inscription is a private
                    citizen, and no rule here can tell which individual of the store a name is (a sample of the
                    curated list persons found Alexander, Glaucus, Lykourgos and Memnon in lists of private names).
                    The exception is the archon of a year whose entity names the archonship.
  adjective_stem    a place linked only by an adjective ending is kept for Athens (Athenaios, Athenaion).
  lower_case        the editions write a proper name with a capital letter: a lower-case word is not a name.
  name_agreement    the token must be a case form of one of the entity's own Greek names (a stem the generic
                    matcher built from a long ending, such as Philokrates for Philoktetes, is not). A people
                    is linked by its stored spellings only.
"""
import unicodedata

from backend import entity_index as ei
from backend import attic_demes
from backend.entity_extras import PRIORITY, match_folded
from backend.entity_mergeback import case_form_of

RULES = ('name_entity', 'month', 'demotic', 'athena_or_athens', 'god_name', 'deity_form', 'archon_date', 'masculine_name',
         'patronymic', 'name_then_patronymic', 'person', 'adjective_stem', 'lower_case', 'name_agreement')

# Deme (attic_demes name) -> entity id of the store's place entity. Only the demes whose entity is the deme.
# Left out because the entity is another place or cannot be told: Icaria (the island), Oinoe, Pallene
# (the peninsula), Prasia, Steiris (Phocis), Pteleum (Phthiotis), Azenia (Arcadia), Euonymus (an island),
# Kerameikos (the district), Arafea.
DEME_ENTITIES = {
    'Acharnai': 'pn:αχαρν2', 'Alopeke': 'pn:alope', 'Anaphlystos': 'pn:anafl', 'Aphidna': 'pn:afidn',
    'Cholargos': 'pn:khola', 'Dekeleia': 'pn:dekel', 'Eleusis': 'pn:eleus', 'Erchia': 'pn:erkhi',
    'Halimous': 'pn:alimo', 'Kydathenaion': 'pn:kudat', 'Lamptrai': 'pn:lampt', 'Marathon': 'pl:580021',
    'Myrrhinous': 'pn:μυρρινουσ', 'Phaleron': 'ln:E1448', 'Piraeus': 'ln:E1129', 'Rhamnous': 'pn:ramno',
    'Sounion': 'pn:souni', 'Thorikos': 'pn:torik', 'Thria': 'pn:trias', 'Xypete': 'pn:ksupe',
}

# A god's name in the cases a dedication uses (folded). Entity id -> forms. The nominative is left out of
# every god whose name was also a personal name (Hermes, Apollon, Isis, Artemis, Aphrodite, Asklepios,
# Dionysos, Herakles, Sarapis, Poseidon): in a list of names it is a man or a woman, in a dedication the
# god is in the dative. Entity id -> forms. Asclepius, Hermes, Nemesis, Pan and
# Serapis are the gods, though the store types their list entities 'person'; Hercules is the promoted deity.
GOD_FORMS = {
    'ln:E0582': ('ζευσ', 'διοσ', 'διι', 'δια', 'ζηνα'),                                         # Zeus
    'ln:E0051': ('αθηνα', 'αθηναιασ', 'αθηναια', 'αθηναιαι', 'αθηνη', 'αθηνησ', 'αθηνην', 'αθηνασ', 'αθηναι'),
    'ln:E0278': ('απολλωνοσ', 'απολλωνι', 'απολλωνα', 'απολλον'),
    'ln:E0327': ('αρτεμιδοσ', 'αρτεμιδι', 'αρτεμιδα', 'αρτεμιν'),
    'ln:E1199': ('ποσειδωνοσ', 'ποσειδωνι', 'ποσειδωνα'),
    'ln:E0475': ('διονυσου', 'διονυσω', 'διονυσον'),
    'ln:E0622': ('ηφαιστου', 'ηφαιστω', 'ηφαιστον'),
    'ln:E0611': ('ηρα', 'ηραι', 'ηραν'),
    'ln:E0364': ('αφροδιτησ', 'αφροδιτην'),
    'ln:E0300': ('αρησ', 'αρεωσ', 'αρει', 'αρη'),
    'ln:E0463': ('δημητηρ', 'δημητροσ', 'δημητρι', 'δημητερα'),
    'ln:E0335': ('ασκληπιου', 'ασκληπιω', 'ασκληπιον'),
    'ln:E0531': ('ερμου', 'ερμη', 'ερμην'),
    'ln:E1008': ('νεμεσισ', 'νεμεσεωσ', 'νεμεσει', 'νεμεσιν'),
    'ln:E1102': ('πανοσ', 'πανι', 'πανα'),
    'ln:E1152': ('φερσεφονη', 'φερσεφονησ', 'φερσεφονην'),
    'pn:herku': ('ηρακλεουσ', 'ηρακλει', 'ηρακλεα'),
    'pn:isis': ('ισιδοσ', 'ισιδι', 'ισιν'),
    'pn:sarap': ('σαραπιδοσ', 'σαραπιδι', 'σαραπιν'),
    'pn:temid': ('θεμισ', 'θεμιδοσ', 'θεμιδι'),
    'pn:laton': ('λητω', 'λητουσ', 'λητοι'),
    'pn:ekate': ('εκατη', 'εκατησ', 'εκατην'),
}
# The tokens that name Athens in cases the generic matcher does not reach (the locative -esin, -aze).
ATHENS = 'ln:E0052'
ATHENS_FORMS = ('αθηνων', 'αθηναισ', 'αθηνησι', 'αθηνησιν', 'αθηναζε', 'αθηναι', 'αθηνασ')
ATHENA_ACCENT = ('αθηναι', 'αθηνασ')

# Masculine personal-name endings (folded). -aios is the ethnic of a place (Athenaios) and is kept apart.
MASCULINE_ENDINGS = ('ιοσ', 'ιου', 'ιωι', 'ιω', 'ιον', 'ιοι', 'ιουσ', 'ιασ', 'ιαν')
MONTH_STEMS = ('εκατομβαι', 'μεταγειτνι', 'βοηδρομι', 'πυανοψι', 'πυανεψι', 'μαιμακτηρι', 'ποσιδε', 'ποσειδε', 'γαμηλι',
               'ανθεστηρι', 'ελαφηβολι', 'μουνιχι', 'θαργηλι', 'σκιροφορι')
MONTH_ENDINGS = ('ων', 'ωνοσ', 'ωνι', 'ωνα', 'εων', 'εωνοσ', 'εωνι', 'εωνα', 'ιων', 'ιωνοσ', 'ιωνι', 'ιωνα')
TITLE_WORDS = frozenset(('επι', 'εφ', 'επ'))
PATRONYMIC_ENDINGS = ('ου', 'ουσ', 'ωνοσ', 'ονοσ', 'ιδοσ', 'αδοσ', 'ντοσ', 'εωσ', 'ατοσ')
NOT_NAME = frozenset(('του', 'τησ', 'των', 'ο', 'η', 'το', 'τον', 'την', 'και', 'δε', 'τε', 'επι', 'εφ', 'επ', 'εκ', 'εξ', 'απο', 'εν',
                      'εισ', 'προσ', 'υπο', 'παρα', 'περι', 'ανεθηκεν', 'ανεθηκε', 'εποιησεν', 'εποιησε'))

_FAMILY = {}


def words(content):
    """The Greek words of a document's text as (surface, folded, line) with the stone line of each. Lines
    are separated by ' / ' in the stored text."""
    out = []
    text = unicodedata.normalize('NFC', content or '')
    for n, part in enumerate(text.split(' / ')):
        for w in part.replace('’', ' ').replace("'", ' ').split():
            w = w.strip('.,;:·⋮∶·()[]{}|<>?!-–—"“”‘`“…⸮')
            if not w or not any(c.isalpha() for c in w):
                continue
            f = ei.fold(w)
            if f:
                out.append((w, f, n))
    return out


def capitalized(surface):
    for c in surface:
        if c.isalpha():
            return c.upper() == c and c.lower() != c
    return False


def athena_or_athens(surface):
    """'athena', 'athens' or None, read from the accent of Athenai/Athenas."""
    nfd = unicodedata.normalize('NFD', surface)
    marks = {}
    base = ''
    for c in nfd:
        if unicodedata.combining(c):
            marks.setdefault(len(base) - 1, set()).add(c)
        else:
            base += c.lower()
    for pos, ms in marks.items():
        ch = base[pos]
        if ch == 'η' and ms & {'́', '͂', '̀'}:
            return 'athens'
        if ch == 'α' and ms & {'͂', '́', '̀'} and pos >= 1:
            return 'athena'
    return None


def archon_context(ws, i):
    """True when word i stands inside an archon date: epi X archontos (X within three words) or epi archontos X."""
    f = [w[1] for w in ws]
    n = len(f)
    for j in range(i + 1, min(n, i + 4)):
        if f[j] == 'αρχοντοσ':
            if any(f[k] in TITLE_WORDS for k in range(max(0, i - 3), i)):
                return True
            break
    if i >= 1 and f[i - 1] == 'αρχοντοσ' and i >= 2 and f[i - 2] in TITLE_WORDS:
        return True
    if i >= 2 and f[i - 2] == 'αρχοντοσ' and i >= 3 and f[i - 3] in TITLE_WORDS:
        return True
    return False


def is_patronymic(ws, i):
    """A genitive in -ou or -ous written with a capital after another capitalized name (or after that
    name and the article): the father's name."""
    surface, f, _line = ws[i]
    if not (capitalized(surface) and f.endswith(PATRONYMIC_ENDINGS)):
        return False
    j = i - 1
    if j >= 0 and ws[j][1] in ('του', 'τησ'):
        j -= 1
    return j >= 0 and ws[j][2] == ws[i][2] and capitalized(ws[j][0]) and ws[j][1] not in NOT_NAME


def is_month(f):
    return any(f.startswith(st) and f[len(st):] in MONTH_ENDINGS for st in MONTH_STEMS)


def patronymic_follows(ws, i):
    """True when the next word on the same stone line is a capitalized genitive (a father's name)."""
    if i + 1 >= len(ws) or ws[i + 1][2] != ws[i][2]:
        return False
    nxt = ws[i + 1]
    return capitalized(nxt[0]) and nxt[1].endswith(PATRONYMIC_ENDINGS) and nxt[1] not in NOT_NAME


def masculine_name_form(f):
    """A masculine personal-name ending. The ethnic of Athens (Athenaios) is not one."""
    if f.startswith('αθηναι'):
        return False
    return f.endswith(MASCULINE_ENDINGS + ('αιοσ', 'αιου', 'αιωι', 'αιον', 'αιοι'))


def feminine_or_neuter_place(label, grc_forms):
    """True when the place's name is feminine or neuter, from its Greek forms when it has them, else from
    the Latin or English label (-a, -ae, -um, -on, -is, -e)."""
    for g in grc_forms:
        if g.endswith(('α', 'η', 'αι', 'ον', 'ισ', 'ια', 'αισ', 'α')):
            return True
        if g.endswith(('οσ', 'ευσ', 'ησ', 'ων', 'ουσ')):
            return False
    t = ei.fold(label)
    t = t.split('/')[0].split('(')[0].strip()
    return t.endswith(('a', 'ae', 'um', 'on', 'is', 'e', 'ai', 'ia'))


class AtticMatcher:
    """Reads the store once (entities, Greek names, descriptions) and answers for a document."""

    def __init__(self, ents, exact, stems, labels, skip=frozenset()):
        self.skip = skip
        self.ents = ents
        self.exact, self.stems = exact, stems
        self.by_id = {e['id']: e for e in ents.values()}
        self.desc = {eid: (d or '') for eid, d in labels.items()}
        self.grc = {eid: {ei.fold(f) for f in e['forms'].get('grc', ()) if ei.fold(f)} for eid, e in ents.items()}
        self.demotics = attic_demes.demotic_table()
        self.deme_eid = {name: self.by_id[eid]['eid'] for name, eid in DEME_ENTITIES.items() if eid in self.by_id}
        self.god_eid = {}
        for gid, forms in GOD_FORMS.items():
            if gid in self.by_id:
                for f in forms:
                    self.god_eid.setdefault(f, set()).add(self.by_id[gid]['eid'])
        self.athens = self.by_id[ATHENS]['eid'] if ATHENS in self.by_id else None
        self.athena = self.by_id['ln:E0051']['eid'] if 'ln:E0051' in self.by_id else None
        self.gods = {self.by_id[g]['eid'] for g in GOD_FORMS if g in self.by_id}

    # ---- one occurrence against the rules
    def _rule_for(self, e, kind, adj, ws, i, ctx):
        surface, f, _line = ws[i]
        typ, src = e['type'], e['source']
        if typ == 'name':
            return 'name_entity'
        if is_month(f):
            return 'month'
        if ctx['demotic']:
            return None if e['eid'] in ctx['demotic_ok'] else 'demotic'
        if ctx['athena_athens'] == 'unresolved':
            return 'athena_or_athens'
        if ctx['god_eids']:
            return None if e['eid'] in ctx['god_eids'] else 'god_name'
        if typ == 'deity':
            return 'deity_form'
        archon_person = False
        if ctx['archon']:
            if typ == 'person' and self._archon_entity(e):
                archon_person = True
            else:
                return 'archon_date'
        if typ == 'place' and masculine_name_form(f) and feminine_or_neuter_place(e['label'], self.grc.get(e['eid'], ())):
            return 'masculine_name'
        if ctx['patronymic']:
            return 'patronymic'
        if typ in ('place', 'people') and patronymic_follows(ws, i):
            return 'name_then_patronymic'
        if typ == 'person' and not archon_person:
            return 'person'
        if kind == 'adjective_stem' and not (e['eid'] == self.athens and f.startswith('αθηναι')):
            return 'adjective_stem'
        if not ctx['capital']:
            return 'lower_case'
        heads = [g for g in self.grc.get(e['eid'], ()) if g]
        if typ == 'people' and heads:
            if f not in heads or len(f) < 6:
                return 'name_agreement'           # a people: its stored spellings only, and not a short form (Lakon, Kares)
        elif typ in ('person', 'place', 'deity') and kind != 'adjective_stem' and heads:
            if f not in heads and case_form_of(f, heads) is None:
                return 'name_agreement'
        return None

    def _archon_entity(self, e):
        return 'archon' in self.desc.get(e['eid'], '').lower()

    def read_document(self, content):
        """[(eid, kind, adjective, folded form, word index, dropped_by or None, added)] for every occurrence
        of a name in a document, plus the number of archon names with a candidate left unlinked."""
        ws = words(content)
        out = []
        archon_unlinked = 0
        for i, (surface, f, _line) in enumerate(ws):
            ctx = {'demotic': False, 'demotic_ok': set(), 'athena_athens': None, 'god_eids': set(),
                   'archon': archon_context(ws, i), 'patronymic': is_patronymic(ws, i),
                   'capital': capitalized(surface)}
            adds = []
            deme = self.demotics.get(f)
            if deme:
                ctx['demotic'] = True
                eid = self.deme_eid.get(deme)
                if eid:
                    ctx['demotic_ok'].add(eid)
                    adds.append((eid, 'form', False))
            elif f in ATHENA_ACCENT:
                which = athena_or_athens(surface)
                if which == 'athens' and self.athens:
                    adds.append((self.athens, 'form', False))
                    ctx['athena_athens'] = 'athens'
                    ctx['god_eids'] = {self.athens}
                elif which == 'athena' and self.athena:
                    adds.append((self.athena, 'form', False))
                    ctx['athena_athens'] = 'athena'
                    ctx['god_eids'] = {self.athena}
                else:
                    ctx['athena_athens'] = 'unresolved'
            else:
                gods = self.god_eid.get(f)
                if gods:
                    ctx['god_eids'] = set(gods)
                    adds += [(g, 'form', False) for g in sorted(gods)]
                elif f in ATHENS_FORMS and self.athens:
                    ctx['god_eids'] = {self.athens}
                    adds.append((self.athens, 'form', False))
            cands = [] if f in self.skip else match_folded(f, self.exact['grc'], self.stems['grc'], 'grc')
            seen = set()
            blocked = False
            for eid, kind, adj in cands:
                e = self.ents[eid]
                why = self._rule_for(e, kind, adj, ws, i, ctx)
                if why == 'archon_date':
                    blocked = True
                out.append((eid, kind, adj, f, i, why, False))
                seen.add(eid)
            if blocked and ctx['archon']:
                archon_unlinked += 1
            for eid, kind, adj in adds:
                if eid in seen:
                    continue
                e = self.ents[eid]
                why = None
                if not ctx['capital']:
                    why = 'lower_case'
                if ctx['archon'] and not self._archon_entity(e):
                    why = 'archon_date'
                out.append((eid, kind, adj, f, i, why, True))
        return out, archon_unlinked


def aggregate(occurrences):
    """Per (eid): the surviving occurrence of the best kind, as (eid, form, kind, adjective), or None, and the
    index in RULES of the last rule that dropped each occurrence (len(RULES) for none)."""
    kept = {}
    drops = {}
    for eid, kind, adj, f, i, why, added in occurrences:
        drops.setdefault(eid, []).append(RULES.index(why) if why else len(RULES))
        if why is None:
            old = kept.get(eid)
            if old is None or PRIORITY[kind] < PRIORITY[old[2]]:
                kept[eid] = (eid, f, kind, 1 if adj else 0, i)
    return kept, drops
