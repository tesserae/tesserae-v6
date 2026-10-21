"""The demes of Attica and their demotics, for the Attic matcher (backend/attic_mentions.py).

An Athenian citizen is named with his father's name and the name of his deme in the genitive or
adjective form: Phrearrios, Sphettios, Paianieus. A demotic names a deme (a place), never a
person, so a demotic token links to the deme's place entity and to nothing else.

Source. The deme names are the Kleisthenic demes as listed in J. S. Traill, Demos and Trittys (1986)
and M. H. Hansen and T. H. Nielsen, An Inventory of Archaic and Classical Poleis (2004), pp. 624-644
(the Attic demes), with the demotic of each as the inscriptions write it (the lists are summarized
in the Pleiades names of the demes, https://pleiades.stoa.org). The table is checked against the
inscriptions themselves by scripts/entities/add_aio_mentions.py, which reports each demotic that
occurs in the Attic Inscriptions Online documents and each one that does not. A demotic is given
here by its folded stem and one of the declension families below, so an accent or a breathing
written differently on the stone does not matter.

Families (folded endings): 'eus' -eus -ews -ei -ea -eis -ewn -eusi(n) -eas, 'es' -es -ou -h -hn -ai
-wn -ais -as (Aithalides, Deiradiotes), 'os' -os -ou -w -on -oi -wn -ois -ous (Sphettios,
Marathonios), 'then' the single form in -hqen (Alopekethen), 'on' -wn -wnos -wni -wna (Xypetaion).
"""
from backend.entity_index import fold

FAMILIES = {
    'eus': ('ευσ', 'εωσ', 'ει', 'εα', 'εισ', 'εων', 'ευσι', 'ευσιν', 'εασ'),
    'es': ('ησ', 'ου', 'η', 'ην', 'αι', 'ων', 'αισ', 'ασ', 'α'),
    'os': ('οσ', 'ου', 'ω', 'ον', 'οι', 'ων', 'οισ', 'ουσ'),
    'then': ('ηθεν',),
    'on': ('ων', 'ωνοσ', 'ωνι', 'ωνα'),
}

# (English name, the Greek name of the deme as a place (folded stems, any number), demotic stem, family)
# The place stems are what the place entity is looked up by (a label or a spelling that starts with one).
DEMES = [
    ('Acharnai', ['αχαρν'], 'αχαρν', 'eus'),
    ('Agryle', ['αγρυλ'], 'αγρυλ', 'then'),
    ('Aigilia', ['αιγιλ'], 'αιγιλι', 'eus'),
    ('Aithalidai', ['αιθαλιδ'], 'αιθαλιδ', 'es'),
    ('Aixone', ['αιξων'], 'αιξων', 'eus'),
    ('Alopeke', ['αλωπεκ'], 'αλωπεκ', 'then'),
    ('Amphitrope', ['αμφιτροπ'], 'αμφιτροπ', 'then'),
    ('Anagyrous', ['αναγυρ'], 'αναγυρασι', 'os'),
    ('Anaphlystos', ['αναφλυστ'], 'αναφλυστι', 'os'),
    ('Anakaia', ['ανακαι'], 'ανακαι', 'eus'),
    ('Ankyle', ['αγκυλ'], 'αγκυλ', 'then'),
    ('Aphidna', ['αφιδν'], 'αφιδναι', 'os'),
    ('Araphen', ['αραφην'], 'αραφηνι', 'os'),
    ('Atene', ['ατην'], 'ατην', 'eus'),
    ('Azenia', ['αζην'], 'αζηνι', 'eus'),
    ('Bate', ['βατ'], 'βατ', 'then'),
    ('Berenikidai', ['βερενικιδ'], 'βερενικιδ', 'es'),
    ('Besa', ['βησ'], 'βησαι', 'eus'),
    ('Cholargos', ['χολαργ'], 'χολαργ', 'eus'),
    ('Cholleidai', ['χολλειδ'], 'χολλειδ', 'es'),
    ('Daidalidai', ['δαιδαλιδ'], 'δαιδαλιδ', 'es'),
    ('Deiradiotai', ['δειραδιωτ'], 'δειραδιωτ', 'es'),
    ('Dekeleia', ['δεκελει', 'δεκελε'], 'δεκελε', 'eus'),
    ('Diomeia', ['διομει'], 'διομε', 'eus'),
    ('Eiresidai', ['ειρεσιδ'], 'ειρεσιδ', 'es'),
    ('Eitea', ['ιτε'], 'ιτεαι', 'os'),
    ('Eleusis', ['ελευσ'], 'ελευσινι', 'os'),
    ('Epikephisia', ['επικηφισ'], 'επικηφισι', 'os'),
    ('Erchia', ['ερχι'], 'ερχι', 'eus'),
    ('Erikeia', ['ερικει'], 'ερικε', 'eus'),
    ('Eroiadai', ['εροιαδ'], 'εροιαδ', 'es'),
    ('Eupyridai', ['ευπυριδ'], 'ευπυριδ', 'es'),
    ('Euonymon', ['ευωνυμ'], 'ευωνυμ', 'eus'),
    ('Gargettos', ['γαργηττ'], 'γαργηττι', 'os'),
    ('Hagnous', ['αγνου'], 'αγνουσι', 'os'),
    ('Halai Aixonides', ['αλαι', 'αλαιαι'], 'αλαι', 'eus'),
    ('Halimous', ['αλιμου'], 'αλιμουσι', 'os'),
    ('Hekale', ['εκαλ'], 'εκαλ', 'then'),
    ('Hermos', ['ερμοσ'], 'ερμει', 'os'),
    ('Hybadai', ['υβαδ'], 'υβαδ', 'es'),
    ('Ikarion', ['ικαρ'], 'ικαρι', 'eus'),
    ('Ionidai', ['ιωνιδ'], 'ιωνιδ', 'es'),
    ('Iphistiadai', ['ιφιστιαδ'], 'ιφιστιαδ', 'es'),
    ('Kedoi', ['κηδοι'], 'κηδοιδ', 'es'),
    ('Kephale', ['κεφαλ'], 'κεφαλ', 'then'),
    ('Kephisia', ['κηφισι'], 'κηφισι', 'eus'),
    ('Kerameis', ['κεραμ'], 'κεραμ', 'eus'),
    ('Kettos', ['κηττ'], 'κηττι', 'os'),
    ('Kikynna', ['κικυν'], 'κικυνν', 'eus'),
    ('Kolonai', ['κολων'], 'κολων', 'then'),
    ('Kollytos', ['κολλυτ'], 'κολλυτ', 'eus'),
    ('Konthyle', ['κονθυλ'], 'κονθυλ', 'then'),
    ('Kothokidai', ['κοθωκιδ'], 'κοθωκιδ', 'es'),
    ('Kropidai', ['κροπιδ'], 'κροπιδ', 'es'),
    ('Kydantidai', ['κυδαντιδ'], 'κυδαντιδ', 'es'),
    ('Kydathenaion', ['κυδαθην'], 'κυδαθηναι', 'eus'),
    ('Kytherros', ['κυθηρρ'], 'κυθηρρι', 'os'),
    ('Lakiadai', ['λακιαδ'], 'λακιαδ', 'es'),
    ('Lamptrai', ['λαμπτρ'], 'λαμπτρ', 'eus'),
    ('Leukonoion', ['λευκονο'], 'λευκονο', 'eus'),
    ('Lousia', ['λουσι'], 'λουσι', 'eus'),
    ('Marathon', ['μαραθων'], 'μαραθωνι', 'os'),
    ('Melite', ['μελιτ'], 'μελιτ', 'eus'),
    ('Myrrhinous', ['μυρρινου'], 'μυρρινουσι', 'os'),
    ('Oa', ['οα'], 'οαι', 'os'),
    ('Oion (Dekeleikon)', ['οι'], 'ο', 'then'),
    ('Oion (Kerameikon)', ['οι'], 'οι', 'then'),
    ('Oinoe', ['οινο'], 'οιναι', 'os'),
    ('Paiania', ['παιανι'], 'παιανι', 'eus'),
    ('Pallene', ['παλλην'], 'παλλην', 'eus'),
    ('Perithoidai', ['περιθοιδ'], 'περιθοιδ', 'es'),
    ('Pergase', ['περγασ'], 'περγασ', 'then'),
    ('Phaleron', ['φαληρ'], 'φαληρ', 'eus'),
    ('Phegous', ['φηγου'], 'φηγουσι', 'os'),
    ('Phlya', ['φλυ'], 'φλυ', 'eus'),
    ('Phrearrhioi', ['φρεαρρ'], 'φρεαρρι', 'os'),
    ('Phyle', ['φυλ'], 'φυλασι', 'os'),
    ('Piraeus', ['πειραι'], 'πειραι', 'eus'),
    ('Pithos', ['πιθ'], 'πιθ', 'eus'),
    ('Plotheia', ['πλωθει'], 'πλωθει', 'eus'),
    ('Prasiai', ['πρασι'], 'πρασι', 'eus'),
    ('Probalinthos', ['προβαλισ'], 'προβαλισι', 'os'),
    ('Prospalta', ['προσπαλτ'], 'προσπαλτι', 'os'),
    ('Ptelea', ['πτελε'], 'πτελεασι', 'os'),
    ('Rhamnous', ['ραμνου'], 'ραμνουσι', 'os'),
    ('Semachidai', ['σημαχιδ'], 'σημαχιδ', 'es'),
    ('Skambonidai', ['σκαμβωνιδ'], 'σκαμβωνιδ', 'es'),
    ('Sounion', ['σουνι'], 'σουνι', 'eus'),
    ('Sphettos', ['σφηττ'], 'σφηττι', 'os'),
    ('Steiria', ['στειρι'], 'στειρι', 'eus'),
    ('Sybridai', ['συβριδ'], 'συβριδ', 'es'),
    ('Sypalettos', ['συπαλητ'], 'συπαλητι', 'os'),
    ('Teithras', ['τειθρασ'], 'τειθρασι', 'os'),
    ('Thorai', ['θορα'], 'θωραι', 'eus'),
    ('Thorikos', ['θορικ'], 'θορικι', 'os'),
    ('Thria', ['θρια'], 'θριασι', 'os'),
    ('Thymaitadai', ['θυμαιταδ'], 'θυμαιταδ', 'es'),
    ('Trinemeia', ['τρινεμει'], 'τρινεμε', 'eus'),
    ('Tyrmeidai', ['τυρμειδ'], 'τυρμειδ', 'es'),
    ('Xypete', ['ξυπετ'], 'ξυπεται', 'on'),
]


def demotic_forms(stem, family):
    return {fold(stem + e) for e in FAMILIES[family]}


def demotic_table():
    """{folded demotic form: English name of the deme}. A form that two demes share (the stem
    plus an ending) is kept for the first and reported by demotic_clashes()."""
    out = {}
    for name, _places, stem, fam in DEMES:
        for f in demotic_forms(stem, fam):
            out.setdefault(f, name)
    return out


def demotic_clashes():
    seen, clash = {}, []
    for name, _places, stem, fam in DEMES:
        for f in demotic_forms(stem, fam):
            if f in seen and seen[f] != name:
                clash.append((f, seen[f], name))
            seen.setdefault(f, name)
    return clash
