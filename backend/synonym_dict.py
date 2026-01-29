"""
Tesserae V6 - Latin and Greek Synonym Dictionary

Combines two sources:
1. Tesserae V3's extensive synonym files (23,754 Latin + 30,000+ Greek entries)
   - Derived from Lewis & Short and LSJ lexicon definitions
2. Curated semantic groups for key classical vocabulary
   - Based on poetic substitutions in Vergil, Ovid, Homer, etc.
"""

import os
import unicodedata

_LATIN_LOOKUP = None
_GREEK_LOOKUP = None
_GREEK_LATIN_DICT = None
_GREEK_LATIN_DICT_NORMALIZED = None
_DATA_DIR = os.path.join(os.path.dirname(__file__), 'synonymy')

# Cross-lingual stoplist: common function words that create noise in dictionary matching
# These are high-frequency words that match across languages but carry little semantic weight
# Note: Use final sigma (ς) where needed since _normalize_greek preserves it
_CROSSLINGUAL_STOPLIST_GREEK_RAW = {
    # Particles and conjunctions
    'και', 'τε', 'δε', 'γαρ', 'αλλα', 'αλλ', 'ουν', 'μεν', 'ουδε', 'μηδε', 'ητοι', 'ειτε',
    # Negations
    'ου', 'ουκ', 'ουχ', 'μη', 'μητε', 'ουτε',
    # Articles (with both sigma forms)
    'ο', 'η', 'το', 'τον', 'την', 'του', 'της', 'τησ', 'τω', 'τη', 'τοι', 'ται', 'τους', 'τουσ', 'τας', 'τασ', 'των', 'τοις', 'τοισ', 'ταις', 'ταισ',
    # Pronouns (common forms)
    'εγω', 'συ', 'αυτος', 'αυτοσ', 'αυτη', 'αυτο', 'οδε', 'ηδε', 'τοδε', 'ουτος', 'ουτοσ', 'τουτο',
    'ος', 'οσ', 'τις', 'τισ', 'τι', 'εμος', 'εμοσ', 'σος', 'σοσ', 'ημετερος', 'ημετεροσ',
    # Prepositions
    'εν', 'εις', 'εισ', 'εκ', 'εξ', 'απο', 'προς', 'προσ', 'επι', 'περι', 'κατα', 'μετα', 'δια', 'υπερ', 'υπο', 'παρα', 'προ', 'αμφι', 'ανα', 'αντι', 'συν',
    # Common verbs (copula, etc.)
    'ειμι', 'εστι', 'εστιν', 'ην', 'εσται', 'ειναι',
    # Relative/interrogative
    'πως', 'πωσ', 'ως', 'ωσ', 'οτι', 'οτε', 'ινα', 'ει', 'αν', 'εαν',
    # Common temporal adverbs
    'πω', 'ποτε', 'νυν', 'τοτε', 'αει', 'ετι', 'ηδη', 'παλαι', 'αυθις', 'αυτις',
}
# Normalize all entries to handle sigma variants consistently
CROSSLINGUAL_STOPLIST_GREEK = set()
for word in _CROSSLINGUAL_STOPLIST_GREEK_RAW:
    # Add both sigma forms for each word
    CROSSLINGUAL_STOPLIST_GREEK.add(word)
    CROSSLINGUAL_STOPLIST_GREEK.add(word.replace('ς', 'σ'))
    CROSSLINGUAL_STOPLIST_GREEK.add(word.replace('σ', 'ς'))

CROSSLINGUAL_STOPLIST_LATIN = {
    # Conjunctions and particles
    'et', 'atque', 'ac', 'que', 'sed', 'at', 'autem', 'aut', 'vel', 'nec', 'neque', 'nam', 'enim', 'igitur', 'ergo', 'tamen', 'quoque', 'quidem',
    # Negations
    'non', 'nec', 'neque', 'ne', 'haud',
    # Pronouns
    'ego', 'tu', 'nos', 'vos', 'is', 'ea', 'id', 'hic', 'haec', 'hoc', 'ille', 'illa', 'illud', 'ipse', 'qui', 'quae', 'quod', 'quis', 'quid',
    'meus', 'tuus', 'suus', 'noster', 'vester', 'se', 'sui', 'sibi',
    # Prepositions
    'in', 'ex', 'e', 'de', 'ab', 'a', 'ad', 'per', 'cum', 'sub', 'super', 'pro', 'inter', 'ante', 'post', 'trans', 'ob', 'propter', 'sine', 'praeter',
    # Common verbs (copula, etc.)
    'sum', 'est', 'sunt', 'esse', 'erat', 'erit', 'fuit',
    # Relative/interrogative/indefinite
    'ut', 'si', 'ubi', 'cum', 'quod', 'quia', 'quam', 'quando', 'quot',
    # Common temporal adverbs
    'olim', 'nunc', 'tunc', 'tum', 'iam', 'semper', 'umquam', 'numquam', 'adhuc', 'mox', 'tandem',
    # Common adverbs/particles
    'sic', 'ita', 'tam', 'quam', 'magis', 'minus', 'bene', 'male', 'valde', 'nimis',
}


def _normalize_greek(text):
    """Strip diacritics/accents from Greek text for matching.
    Converts polytonic Greek to base letters for comparison.
    """
    nfkd = unicodedata.normalize('NFKD', text.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


CURATED_GREEK_LATIN = {
    "αχιλλευσ": ["achilles", "achillis", "achillem", "achilli"],
    "αχιλευσ": ["achilles", "achillis", "achillem", "achilli"],
    "εκτωρ": ["hector", "hectoris", "hectorem", "hectori"],
    "πριαμοσ": ["priamus", "priami", "priamum", "priamo"],
    "αγαμεμνων": ["agamemnon", "agamemnonis"],
    "οδυσσευσ": ["ulixes", "ulixis", "odysseus"],
    "αινειασ": ["aeneas", "aeneae", "aenean"],
    "πατροκλοσ": ["patroclus", "patrocli"],
    "ελενη": ["helena", "helenae", "helene"],
    "ανδρομαχη": ["andromache", "andromaches"],
    "τροια": ["troia", "troiae", "troiam", "ilium", "ilion"],
    "ιλιον": ["ilium", "ilion", "troia"],
    "θεοσ": ["deus", "dei", "deo", "deum", "divus", "numen"],
    "θεα": ["dea", "deae", "deam", "diva"],
    "ανηρ": ["vir", "viri", "virum", "viro", "homo"],
    "γυνη": ["mulier", "femina", "uxor"],
    "πατηρ": ["pater", "patris", "patrem", "patri", "genitor"],
    "μητηρ": ["mater", "matris", "matrem", "matri", "genetrix"],
    "υιοσ": ["filius", "filii", "filium", "filio", "natus"],
    "παισ": ["puer", "pueri", "puerum", "filius", "natus"],
    "βασιλευσ": ["rex", "regis", "regem", "regi", "tyrannus"],
    "αναξ": ["rex", "regis", "dominus"],
    "πολισ": ["urbs", "urbis", "urbem", "civitas", "oppidum"],
    "ναυσ": ["navis", "navis", "navem", "navi", "puppis", "carina"],
    "θαλασσα": ["mare", "maris", "pontus", "pelagus", "aequor"],
    "πολεμοσ": ["bellum", "belli", "bellum", "bello", "proelium", "pugna"],
    "μαχη": ["pugna", "proelium", "bellum", "certamen"],
    "οπλα": ["arma", "armorum", "tela"],
    "ξιφοσ": ["gladius", "ensis", "ferrum", "mucro"],
    "δορυ": ["hasta", "hastae", "telum", "lancea"],
    "ασπισ": ["clipeus", "scutum"],
    "ιπποσ": ["equus", "equi", "equum", "equo", "sonipes"],
    "θανατοσ": ["mors", "mortis", "mortem", "morte", "letum", "fatum"],
    "ψυχη": ["anima", "animae", "animus", "mens", "spiritus"],
    "θυμοσ": ["animus", "animi", "furor", "ira", "spiritus"],
    "μηνισ": ["ira", "irae", "furor"],
    "χολοσ": ["ira", "bilis", "furor"],
    "ερωσ": ["amor", "amoris", "amorem", "cupido"],
    "φιλια": ["amor", "amicitia", "caritas"],
    "κλεοσ": ["gloria", "gloriae", "fama", "laus", "honor"],
    "τιμη": ["honor", "honoris", "honorem", "decus"],
    "αρετη": ["virtus", "virtutis"],
    "νικη": ["victoria", "victoriae"],
    "πυρ": ["ignis", "ignis", "flamma"],
    "υδωρ": ["aqua", "aquae", "unda", "lympha"],
    "γη": ["terra", "terrae", "tellus", "humus"],
    "γαια": ["terra", "tellus"],
    "ουρανοσ": ["caelum", "caeli", "polus", "aether"],
    "ηλιοσ": ["sol", "solis", "phoebus"],
    "σεληνη": ["luna", "lunae", "phoebe"],
    "αστηρ": ["astrum", "stella", "sidus"],
    "νυξ": ["nox", "noctis", "noctem"],
    "ημερα": ["dies", "diei", "lux"],
    "χρονοσ": ["tempus", "temporis", "aetas"],
    "αιων": ["aevum", "aetas", "saeculum"],
    "λογοσ": ["verbum", "verbi", "sermo", "vox", "oratio"],
    "μυθοσ": ["fabula", "fabulae", "narratio"],
    "επoσ": ["verbum", "carmen", "vox"],
    "οικοσ": ["domus", "domus", "domum", "domo", "aedes", "tecta"],
    "δομοσ": ["domus", "tecta", "aedes"],
    "ναοσ": ["templum", "templi", "fanum", "delubrum"],
    "βωμοσ": ["ara", "arae", "altare"],
    "ζευσ": ["iuppiter", "iovis", "iovem", "iove"],
    "ηρα": ["iuno", "iunonis"],
    "αθηνη": ["minerva", "minervae", "pallas"],
    "αφροδιτη": ["venus", "veneris"],
    "αρησ": ["mars", "martis", "martem"],
    "απολλων": ["apollo", "apollinis", "phoebus"],
    "ποσειδων": ["neptunus", "neptuni"],
    "ερμησ": ["mercurius", "mercurii"],
    "διονυσοσ": ["bacchus", "bacchi", "liber"],
    "αιδησ": ["pluto", "plutonis", "dis", "orcus"],
    "μοιρα": ["fatum", "fati", "sors", "parca"],
    "κηρ": ["mors", "fatum", "letum"],
}

CURATED_LATIN = {
    "bellum": ["bellum", "proelium", "pugna", "certamen", "acies"],
    "rex": ["rex", "tyrannus", "dominus", "princeps", "imperator"],
    "deus": ["deus", "numen", "divus", "caelestis", "superus"],
    "mors": ["mors", "fatum", "letum", "nex", "obitus", "finis"],
    "amor": ["amor", "caritas", "pietas", "studium", "cupido"],
    "pater": ["pater", "genitor", "parens", "sator"],
    "mater": ["mater", "genetrix", "parens"],
    "filius": ["filius", "natus", "proles", "progenies", "soboles"],
    "urbs": ["urbs", "civitas", "oppidum", "moenia"],
    "mare": ["mare", "pontus", "pelagus", "aequor", "fretum", "salum"],
    "navis": ["navis", "puppis", "carina", "ratis", "cymba"],
    "terra": ["terra", "tellus", "humus", "solum", "orbis"],
    "caelum": ["caelum", "polus", "aether", "olympus"],
    "ignis": ["ignis", "flamma", "focus", "rogus"],
    "aqua": ["aqua", "unda", "lympha", "latex", "fons", "flumen", "amnis"],
    "ventus": ["ventus", "aura", "flatus", "spiritus", "procella"],
    "gladius": ["gladius", "ensis", "ferrum", "mucro", "telum", "hasta"],
    "arma": ["arma", "tela", "ferrum", "clipeus", "scutum"],
    "equus": ["equus", "sonipes", "cabellus"],
    "vir": ["vir", "homo", "mas", "heros"],
    "femina": ["femina", "mulier", "matrona", "virgo", "puella"],
    "corpus": ["corpus", "membra", "artus"],
    "animus": ["animus", "mens", "pectus", "cor", "spiritus"],
    "ira": ["ira", "furor", "rabies", "indignatio"],
    "metus": ["metus", "timor", "pavor", "terror", "formido"],
    "lacrima": ["lacrima", "fletus", "luctus", "planctus"],
    "gaudium": ["gaudium", "laetitia", "voluptas"],
    "dolor": ["dolor", "luctus", "maeror", "tristitia"],
    "virtus": ["virtus", "valor", "fortitudo", "pietas"],
    "honos": ["honos", "honor", "decus", "gloria", "fama", "laus"],
    "tempus": ["tempus", "hora", "dies", "aetas", "saeculum"],
    "nox": ["nox", "tenebrae", "umbra", "caligo"],
    "lux": ["lux", "lumen", "iubar", "splendor", "nitor"],
    "sol": ["sol", "phoebus", "titan", "apollo"],
    "luna": ["luna", "phoebe", "diana", "cynthia"],
    "somnus": ["somnus", "sopor", "quies"],
    "sanguis": ["sanguis", "cruor"],
    "hostis": ["hostis", "inimicus", "adversarius"],
    "amicus": ["amicus", "socius", "sodalis", "comes"],
    "fortuna": ["fortuna", "fatum", "sors", "casus"],
    "victoria": ["victoria", "triumphus", "palma"],
    "iter": ["iter", "via", "cursus", "callis"],
    "silva": ["silva", "nemus", "lucus", "saltus"],
    "mons": ["mons", "rupes", "saxum", "scopulus"],
    "flumen": ["flumen", "fluvius", "amnis", "rivus", "torrens"],
    "saxum": ["saxum", "lapis", "silex", "rupes", "cautes"],
    "aurum": ["aurum", "opes", "divitiae", "pecunia"],
    "vulnus": ["vulnus", "plaga", "ictus"],
    "vox": ["vox", "sonus", "clamor", "sonitus"],
    "verbum": ["verbum", "dictum", "vox", "sermo"],
    "domus": ["domus", "aedes", "tecta", "lares", "penates"],
    "regnum": ["regnum", "imperium", "dominatio", "potestas"],
    "caedes": ["caedes", "strages", "clades", "nex"],
    "ager": ["ager", "arvum", "campus", "rus"],
    "murus": ["murus", "moenia", "vallum"],
    "porta": ["porta", "ianua", "limen", "ostium"],
    "unda": ["unda", "fluctus", "gurges"],
    "classis": ["classis", "agmen", "turma", "cohors"],
    "copia": ["copia", "agmen", "exercitus", "legio"],
    "dux": ["dux", "imperator", "rector"],
    "miles": ["miles", "bellator", "pugnator"],
    "lex": ["lex", "ius", "fas", "mos"],
    "culpa": ["culpa", "crimen", "scelus", "peccatum", "nefas"],
    "poena": ["poena", "supplicium", "ultio", "vindicta"],
    "numen": ["numen", "deus", "divus"],
    "templum": ["templum", "fanum", "delubrum", "sacellum"],
    "ara": ["ara", "altare", "focus"],
    "carmen": ["carmen", "cantus", "melos"],
    "poeta": ["poeta", "vates"],
    "fama": ["fama", "rumor", "nuntius"],
}

CURATED_GREEK = {
    "πόλεμος": ["πόλεμος", "μάχη", "ἀγών", "πτόλεμος"],
    "βασιλεύς": ["βασιλεύς", "ἄναξ", "τύραννος", "κοίρανος"],
    "θεός": ["θεός", "δαίμων", "θεά"],
    "θάνατος": ["θάνατος", "μόρος", "κήρ", "πότμος", "ὄλεθρος"],
    "ἔρως": ["ἔρως", "φιλία", "στοργή", "πόθος"],
    "πατήρ": ["πατήρ", "γενέτωρ", "τοκεύς"],
    "μήτηρ": ["μήτηρ", "τεκοῦσα"],
    "υἱός": ["υἱός", "παῖς", "τέκνον", "γόνος"],
    "πόλις": ["πόλις", "ἄστυ", "πτόλις"],
    "θάλασσα": ["θάλασσα", "πόντος", "πέλαγος", "ἅλς"],
    "ναῦς": ["ναῦς", "πλοῖον", "σκάφος", "νηῦς"],
    "γῆ": ["γῆ", "γαῖα", "χθών", "αἶα"],
    "οὐρανός": ["οὐρανός", "αἰθήρ", "πόλος"],
    "πῦρ": ["πῦρ", "φλόξ", "πυρά"],
    "ὕδωρ": ["ὕδωρ", "νᾶμα", "ῥεῦμα", "ποταμός"],
    "ἄνεμος": ["ἄνεμος", "πνοή", "αὔρα"],
    "ξίφος": ["ξίφος", "φάσγανον", "ἄορ", "μάχαιρα"],
    "ἀνήρ": ["ἀνήρ", "ἄνθρωπος", "ἥρως", "φώς"],
    "γυνή": ["γυνή", "κούρη", "παρθένος"],
    "σῶμα": ["σῶμα", "δέμας", "χρώς"],
    "ψυχή": ["ψυχή", "θυμός", "νόος", "φρήν", "κῆρ"],
    "ὀργή": ["ὀργή", "θυμός", "χόλος", "μῆνις", "κότος"],
    "φόβος": ["φόβος", "δέος", "τρόμος"],
    "δάκρυ": ["δάκρυ", "δάκρυον", "γόος"],
    "χαρά": ["χαρά", "εὐφροσύνη", "τέρψις"],
    "ἄλγος": ["ἄλγος", "πένθος", "ἄχος", "λύπη"],
    "ἀρετή": ["ἀρετή", "ἀνδρεία"],
    "τιμή": ["τιμή", "κλέος", "δόξα", "κῦδος"],
    "χρόνος": ["χρόνος", "αἰών", "ὥρα", "καιρός"],
    "νύξ": ["νύξ", "σκότος", "ἔρεβος"],
    "φῶς": ["φῶς", "φέγγος", "αὐγή", "σέλας"],
    "ἥλιος": ["ἥλιος", "ἠέλιος", "φοῖβος"],
    "σελήνη": ["σελήνη", "μήνη"],
    "αἷμα": ["αἷμα", "φόνος"],
    "ἐχθρός": ["ἐχθρός", "πολέμιος", "δυσμενής"],
    "φίλος": ["φίλος", "ἑταῖρος", "ξένος"],
    "οἶκος": ["οἶκος", "δόμος", "δῶμα", "μέγαρον"],
    "ὁδός": ["ὁδός", "κέλευθος", "ἀτραπός"],
    "ὄρος": ["ὄρος", "πέτρα", "σκόπελος"],
    "ποταμός": ["ποταμός", "ῥέεθρον", "νᾶμα"],
    "φωνή": ["φωνή", "αὐδή", "ὄψ", "κλαγγή"],
    "ἔπος": ["ἔπος", "λόγος", "μῦθος", "ῥῆμα"],
    "στρατός": ["στρατός", "λαός", "πληθύς"],
    "ἡγεμών": ["ἡγεμών", "ἄρχων", "βασιλεύς"],
    "νόμος": ["νόμος", "θέμις", "δίκη"],
    "ναός": ["ναός", "ἱερόν", "τέμενος"],
    "βωμός": ["βωμός", "ἐσχάρα"],
    "ᾠδή": ["ᾠδή", "ἀοιδή", "μέλος", "ὕμνος"],
    "ἀοιδός": ["ἀοιδός", "ῥαψῳδός"],
}

def _build_curated_lookup(groups):
    """Build lookup from curated semantic groups."""
    lookup = {}
    for canonical, synonyms in groups.items():
        syn_set = set(s.lower() for s in synonyms)
        for word in synonyms:
            word_lower = word.lower()
            if word_lower in lookup:
                lookup[word_lower] = lookup[word_lower].union(syn_set)
            else:
                lookup[word_lower] = set(syn_set)
    return lookup

def _load_v3_synonym_file(filepath):
    """Load V3 synonym file and build lookup table."""
    lookup = {}
    if not os.path.exists(filepath):
        return lookup
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            words = [w.strip().lower() for w in line.split(',') if w.strip()]
            if len(words) < 2:
                continue
            syn_set = set(words)
            for word in words:
                if word in lookup:
                    lookup[word] = lookup[word].union(syn_set)
                else:
                    lookup[word] = set(syn_set)
    return lookup

def _merge_lookups(curated, v3):
    """Merge curated semantic groups with V3 data, preferring curated for overlaps."""
    merged = dict(v3)
    for word, synonyms in curated.items():
        if word in merged:
            merged[word] = merged[word].union(synonyms)
        else:
            merged[word] = set(synonyms)
    return merged

def get_latin_lookup():
    global _LATIN_LOOKUP
    if _LATIN_LOOKUP is None:
        curated = _build_curated_lookup(CURATED_LATIN)
        v3_path = os.path.join(_DATA_DIR, 'fixed_latin_syn.csv')
        v3 = _load_v3_synonym_file(v3_path)
        _LATIN_LOOKUP = _merge_lookups(curated, v3)
        print(f"Loaded {len(_LATIN_LOOKUP)} Latin synonym entries (V3 + curated)")
    return _LATIN_LOOKUP

def get_greek_lookup():
    global _GREEK_LOOKUP
    if _GREEK_LOOKUP is None:
        curated = _build_curated_lookup(CURATED_GREEK)
        v3_path = os.path.join(_DATA_DIR, 'fixed_greek_syn.csv')
        v3 = _load_v3_synonym_file(v3_path)
        _GREEK_LOOKUP = _merge_lookups(curated, v3)
        print(f"Loaded {len(_GREEK_LOOKUP)} Greek synonym entries (V3 + curated)")
    return _GREEK_LOOKUP

def find_synonyms(lemma: str, language: str) -> set:
    """Find synonyms for a given lemma."""
    lemma_lower = lemma.lower()
    if language == 'la':
        return get_latin_lookup().get(lemma_lower, set())
    elif language == 'grc':
        return get_greek_lookup().get(lemma_lower, set())
    return set()

def are_synonyms(lemma1: str, lemma2: str, language: str) -> bool:
    """Check if two lemmas are synonyms."""
    if lemma1.lower() == lemma2.lower():
        return True
    synonyms1 = find_synonyms(lemma1, language)
    return lemma2.lower() in synonyms1 if synonyms1 else False

def find_synonym_pairs_in_passages(source_lemmas: list, target_lemmas: list, 
                                    language: str) -> list:
    """Find synonym pairs between source and target lemma lists."""
    pairs = []
    seen = set()
    
    if language == 'la':
        lookup = get_latin_lookup()
    elif language == 'grc':
        lookup = get_greek_lookup()
    else:
        return pairs
    
    target_lower_set = {l.lower() for l in target_lemmas}
    target_lower_list = [l.lower() for l in target_lemmas]
    
    for src_idx, src_lemma in enumerate(source_lemmas):
        src_lower = src_lemma.lower()
        src_synonyms = lookup.get(src_lower, set())
        
        if not src_synonyms:
            continue
        
        matching_targets = src_synonyms.intersection(target_lower_set)
        
        for tgt_lower in matching_targets:
            if src_lower == tgt_lower:
                continue
            
            pair_key = tuple(sorted([src_lower, tgt_lower]))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            
            tgt_indices = [i for i, l in enumerate(target_lower_list) if l == tgt_lower]
            
            pairs.append({
                'source_lemma': src_lemma,
                'target_lemma': target_lemmas[tgt_indices[0]] if tgt_indices else tgt_lower,
                'source_indices': [i for i, l in enumerate(source_lemmas) if l.lower() == src_lower],
                'target_indices': tgt_indices,
                'type': 'synonym'
            })
    
    return pairs


def get_greek_latin_dict():
    """Load the Greek-Latin cross-lingual dictionary from V3.
    Maps Greek lemmas to their Latin equivalents (34,535 entries).
    Returns tuple: (original_dict, normalized_dict)
    normalized_dict maps accent-stripped Greek to Latin for fuzzy matching.
    """
    global _GREEK_LATIN_DICT, _GREEK_LATIN_DICT_NORMALIZED
    if _GREEK_LATIN_DICT is None:
        _GREEK_LATIN_DICT = {}
        _GREEK_LATIN_DICT_NORMALIZED = {}
        filepath = os.path.join(_DATA_DIR, 'greek_latin_dict.csv')
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = [p.strip().lower() for p in line.split(',') if p.strip()]
                    if len(parts) >= 2:
                        greek_word = parts[0]
                        greek_norm = _normalize_greek(greek_word)
                        latin_words = set(parts[1:])
                        if greek_word in _GREEK_LATIN_DICT:
                            _GREEK_LATIN_DICT[greek_word].update(latin_words)
                        else:
                            _GREEK_LATIN_DICT[greek_word] = latin_words
                        if greek_norm in _GREEK_LATIN_DICT_NORMALIZED:
                            _GREEK_LATIN_DICT_NORMALIZED[greek_norm].update(latin_words)
                        else:
                            _GREEK_LATIN_DICT_NORMALIZED[greek_norm] = set(latin_words)
            print(f"Loaded {len(_GREEK_LATIN_DICT)} Greek-Latin dictionary entries from V3")
        else:
            print(f"Greek-Latin dictionary not found at {filepath}")
    return _GREEK_LATIN_DICT, _GREEK_LATIN_DICT_NORMALIZED


def find_greek_latin_matches(greek_lemmas: list, latin_lemmas: list, use_stoplist: bool = True) -> list:
    """Find Greek-Latin word matches using curated vocabulary + V3 dictionary.
    Uses accent-normalized Greek for matching.
    
    Args:
        greek_lemmas: List of Greek lemmas from source text
        latin_lemmas: List of Latin lemmas from target text
        use_stoplist: If True, skip common function words (default True)
        
    Returns:
        List of match dicts with source/target indices and matched words
    """
    _, gl_dict_norm = get_greek_latin_dict()
    
    matches = []
    seen = set()
    
    latin_lower_set = {l.lower() for l in latin_lemmas}
    latin_lower_list = [l.lower() for l in latin_lemmas]
    
    for grc_idx, grc_lemma in enumerate(greek_lemmas):
        grc_norm = _normalize_greek(grc_lemma)
        
        # Skip Greek stopwords
        if use_stoplist and grc_norm in CROSSLINGUAL_STOPLIST_GREEK:
            continue
        
        curated_translations = set(CURATED_GREEK_LATIN.get(grc_norm, []))
        v3_translations = gl_dict_norm.get(grc_norm, set()) if gl_dict_norm else set()
        latin_translations = curated_translations.union(v3_translations)
        
        if not latin_translations:
            continue
        
        matching_latins = latin_translations.intersection(latin_lower_set)
        
        for lat_lower in matching_latins:
            # Skip Latin stopwords
            if use_stoplist and lat_lower in CROSSLINGUAL_STOPLIST_LATIN:
                continue
                
            pair_key = (grc_norm, lat_lower)
            if pair_key in seen:
                continue
            seen.add(pair_key)
            
            lat_indices = [i for i, l in enumerate(latin_lower_list) if l == lat_lower]
            grc_indices = [i for i, l in enumerate(greek_lemmas) if _normalize_greek(l) == grc_norm]
            
            matches.append({
                'greek_lemma': grc_lemma,
                'latin_lemma': latin_lemmas[lat_indices[0]] if lat_indices else lat_lower,
                'greek_indices': grc_indices,
                'latin_indices': lat_indices,
                'type': 'cross_lingual'
            })
    
    return matches
