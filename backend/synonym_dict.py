"""
Tesserae V6 - Latin and Greek Synonym Dictionary

Combines two sources:
1. Tesserae V3's extensive synonym files (23,754 Latin + 30,000+ Greek entries)
   - Derived from Lewis & Short and LSJ lexicon definitions
2. Curated semantic groups for key classical vocabulary
   - Based on poetic substitutions in Vergil, Ovid, Homer, etc.
"""

import json
import os
import unicodedata

from backend.logging_config import get_logger

logger = get_logger('synonym_dict')

_LATIN_LOOKUP = None
_GREEK_LOOKUP = None
_GREEK_LATIN_DICT = None
_GREEK_LATIN_DICT_NORMALIZED = None
_GAZETTEER_DICT = None
_LATIN_ENGLISH_DICT = None
_GREEK_ENGLISH_DICT = None
_DATA_DIR = os.path.join(os.path.dirname(__file__), 'synonymy')
_PROPER_NAMES_DIR = os.path.join(os.path.dirname(__file__), 'proper_names')

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
    # Pronouns (all common forms including inflections)
    'εγω', 'εμε', 'εμοι', 'εμου', 'μοι', 'μου', 'με',
    'συ', 'σε', 'σοι', 'σου',
    'αυτος', 'αυτοσ', 'αυτη', 'αυτο', 'αυτον', 'αυτην', 'αυτου', 'αυτησ', 'αυτω', 'αυτοι', 'αυτων', 'αυτοις', 'αυτοισ', 'αυτας', 'αυτασ', 'αυτους', 'αυτουσ',
    'ημεις', 'ημασ', 'ημιν', 'ημων',
    'υμεις', 'υμας', 'υμιν', 'υμων',
    'οδε', 'ηδε', 'τοδε', 'ουτος', 'ουτοσ', 'τουτο', 'ταυτα', 'τουτον', 'τουτου', 'ταυτην', 'τουτω',
    'εκεινος', 'εκεινοσ', 'εκεινη', 'εκεινο', 'εκεινον', 'εκεινου', 'εκεινοι',
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

CROSSLINGUAL_STOPLIST_ENGLISH = {
    # Articles and determiners
    'the', 'a', 'an', 'this', 'that', 'these', 'those',
    # Pronouns
    'i', 'me', 'my', 'we', 'us', 'our', 'you', 'your', 'he', 'him', 'his',
    'she', 'her', 'it', 'its', 'they', 'them', 'their', 'who', 'whom', 'what', 'which',
    'myself', 'himself', 'herself', 'itself', 'themselves', 'oneself',
    # Prepositions
    'in', 'on', 'at', 'to', 'for', 'with', 'from', 'by', 'of', 'about',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
    'out', 'off', 'over', 'under', 'up', 'down', 'against', 'among', 'upon',
    # Conjunctions
    'and', 'or', 'but', 'if', 'when', 'while', 'because', 'although', 'though',
    'as', 'than', 'whether', 'so', 'yet', 'nor', 'neither', 'either',
    # Common verbs (copula, auxiliaries)
    'be', 'is', 'am', 'are', 'was', 'were', 'been', 'being',
    'have', 'has', 'had', 'having',
    'do', 'does', 'did', 'done',
    'will', 'would', 'shall', 'should', 'may', 'might', 'can', 'could', 'must',
    # Negation
    'not', 'no', 'never',
    # Common adverbs/particles
    'very', 'also', 'too', 'just', 'now', 'then', 'here', 'there',
    'still', 'even', 'only', 'already', 'ever', 'how', 'where', 'why',
    # Archaic forms (Shakespeare, Milton, KJV)
    'thou', 'thee', 'thy', 'thine', 'ye', 'art', 'doth', 'hath', 'dost',
    'hast', 'wilt', 'shalt', 'wouldst', 'shouldst', 'canst', 'didst',
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
    # Divine epithets and cult names
    "φοιβοσ": ["phoebus", "apollo", "apollinis"],
    # Muses and poetic invocation
    "μουσα": ["musa", "musae", "camena", "camenae"],
    "καλλιοπη": ["calliope", "calliopes"],
    "κλειω": ["clio"],
    # Patronymics and mythological periphrases
    "πηληιαδησ": ["pelides", "pelidae"],
    "αιακιδησ": ["aeacides", "aeaciden"],
    "ατρειδησ": ["atrides", "atridae"],
    "τυδειδησ": ["tydides", "tydidae"],
    "λαερτιαδησ": ["laertiades"],
    "κρονιδησ": ["saturnius"],
    "κρονιων": ["saturnius"],
    # Epic vocabulary
    "ηρωσ": ["heros", "herois", "heroum"],
    "αοιδη": ["carmen", "carminis", "cantus"],
    "αοιδοσ": ["vates", "vatis", "poeta"],
    # Verbs of singing/telling (proem invocations)
    "ενεπω": ["cano", "dico", "narro", "refero"],
    "μελπω": ["cano", "canto"],
    # Body and person
    "δακρυ": ["lacrima", "lacrimae", "fletus"],
    "δακρυον": ["lacrima", "lacrimae", "fletus"],
    "οσσε": ["oculus", "oculi", "lumen", "lumina"],
    "οφθαλμοσ": ["oculus", "oculi", "lumen"],
    "κομη": ["coma", "comae", "capillus", "crinis"],
    "γενοσ": ["genus", "generis", "gens", "gentis", "stirps"],
    "γενεη": ["genus", "generis", "gens", "stirps"],
    "παρθενοσ": ["virgo", "virginis", "puella"],
    "κορη": ["virgo", "puella", "nata"],
    "νεκυσ": ["corpus", "corporis", "cadaver"],
    "νεκροσ": ["corpus", "corporis", "cadaver", "mortuus"],
    # Warfare and equipment
    "τειχοσ": ["murus", "moenia", "moene"],
    "πυργοσ": ["turris", "turrium"],
    "πυλη": ["porta", "portae", "ianua"],
    "θυρα": ["porta", "ianua", "foris", "ostium", "limen"],
    "δεσμοσ": ["vinculum", "nodus", "catena"],
    "χαλκεοσ": ["aeneus", "aereus", "aeratus"],
    "χαλκοσ": ["aes", "aeris", "ferrum"],
    "σακοσ": ["clipeus", "scutum"],
    # Ships and sea
    "ιστιον": ["velum", "veli", "carbasus"],
    "πρυμνα": ["puppis", "puppis"],
    "πρωρα": ["prora", "prorae"],
    # Nature and weather
    "ανεμοσ": ["ventus", "venti", "aura", "flatus"],
    "λαιλαψ": ["procella", "tempestas", "turbo"],
    "κορυφη": ["vertex", "verticis", "cacumen", "culmen", "arx"],
    "αμβροσιοσ": ["ambrosius", "ambrosia", "divinus"],
    # Food and sacrifice
    "σπλαγχνον": ["viscus", "viscera", "exta"],
    "οβελοσ": ["veru", "verubus"],
    # Toil and suffering
    "πονοσ": ["labor", "laboris", "opera"],
    "αχοσ": ["dolor", "doloris", "luctus", "maeror"],
    "πενθοσ": ["luctus", "dolor", "maeror"],
    # Dwelling
    "δωμα": ["domus", "tecta", "aedes", "regia"],
    "μεγαρον": ["domus", "regia", "aula", "atrium"],
    # Vehicles
    "οχοσ": ["currus", "currus"],
    "διφροσ": ["currus", "currus", "sella"],
    # Mind and spirit
    "φρην": ["mens", "mentis", "pectus", "animus", "cor"],
    "νοοσ": ["mens", "mentis", "animus", "consilium"],
    # Appearance and recognition
    "ειδωλον": ["imago", "imaginis", "simulacrum", "umbra"],
    # Time
    "ενιαυτοσ": ["annus", "anni"],
    "ημαρ": ["dies", "diei", "lux"],
    # Speech
    "αυδη": ["vox", "vocis", "sonus"],
    "κλαγγη": ["clamor", "clamoris", "strepitus", "sonitus"],
    # Seeing and looking
    "εισοραω": ["conspicio", "video", "aspicio", "cerno"],
    "καθοραω": ["despicio", "prospicio", "video"],
    # Weeping
    "γοοσ": ["fletus", "planctus", "luctus", "gemitus"],
    "κλαιω": ["fleo", "flevi", "ploro", "lacrimo"],
    "στεναχω": ["gemo", "gemui", "suspiro", "ingemisco"],
    # Movement
    "βαινω": ["eo", "gradior", "incedo"],
    "ικνεομαι": ["advenio", "pervenio", "accedo"],
    # Family
    "κασιγνητοσ": ["frater", "fratris", "germanus"],
    "κασιγνητη": ["soror", "sororis", "germana"],
    "αλοχοσ": ["uxor", "uxoris", "coniunx", "coniugis"],
    "παρακοιτισ": ["coniunx", "uxor", "consors"],
    "δαμαρ": ["uxor", "coniunx", "marita"],
    # Emotion verbs
    "μειδιαω": ["subrideo", "rideo", "arrideo"],
    "μειδαω": ["subrideo", "rideo"],
    "ορμαινω": ["volvo", "voluto", "agito", "meditor"],
    "χολοομαι": ["irascor", "indignor", "doleo"],
    # Physical actions
    "ορεγω": ["tendo", "porrigo", "extendo"],
    "κτεινω": ["occido", "interficio", "neco", "caedo"],
    "ολλυμι": ["perdo", "perimo", "deleo"],
    "αλισκομαι": ["capio", "corripio"],
    # Body parts
    "καρδια": ["cor", "cordis", "pectus"],
    "κραδιη": ["cor", "cordis", "pectus"],
    "στηθοσ": ["pectus", "pectoris"],
    "γονυ": ["genu", "genus"],
    "παλαμη": ["palma", "palmae", "manus"],
    # Water
    "ρεεθρον": ["unda", "undae", "fluctus", "flumen"],
    "ροοσ": ["flumen", "fluvius", "cursus"],
    # Starry sky
    "αστερεοσ": ["sidereus", "stellatus"],
    "αστερεισ": ["sidereus", "stellatus"],
    # Smiling/joy
    "γελαω": ["rideo", "ridere"],
    # Ruling
    "ανασσω": ["regno", "regnare", "dominor", "impero"],
    "κρειων": ["rex", "regis", "dominus"],
    # Sacrifice and feasting
    "δαισ": ["daps", "dapis", "epulae", "convivium"],
    "οινοσ": ["vinum", "vini", "bacchus"],
}

# Load V6 additions from CSV and merge into CURATED_GREEK_LATIN
_V6_ADDITIONS_PATH = os.path.join(_DATA_DIR, 'v6_additions', 'greek_latin_v6_additions.csv')
if os.path.exists(_V6_ADDITIONS_PATH):
    _v6_count = 0
    with open(_V6_ADDITIONS_PATH, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#'):
                continue
            _parts = [p.strip() for p in _line.split(',') if p.strip()]
            if len(_parts) < 2:
                continue
            _greek_word = _parts[0]
            _greek_norm = _normalize_greek(_greek_word).replace('ς', 'σ')  # medial sigma to match existing keys
            _latin_words = [w.lower() for w in _parts[1:]]
            if _greek_norm in CURATED_GREEK_LATIN:
                _existing = set(CURATED_GREEK_LATIN[_greek_norm])
                _existing.update(_latin_words)
                CURATED_GREEK_LATIN[_greek_norm] = list(_existing)
            else:
                CURATED_GREEK_LATIN[_greek_norm] = _latin_words
            _v6_count += 1
    logger.info(f"Loaded {_v6_count} V6 Greek-Latin additions into CURATED_GREEK_LATIN (total: {len(CURATED_GREEK_LATIN)} entries)")

# Load Perseus Dynamic Lexicon additions (3,001 novel Greek-Latin pairs)
_PERSEUS_ADDITIONS_PATH = os.path.join(_DATA_DIR, 'v6_additions', 'perseus_greek_latin_v6_additions.csv')
if os.path.exists(_PERSEUS_ADDITIONS_PATH):
    _perseus_count = 0
    with open(_PERSEUS_ADDITIONS_PATH, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#'):
                continue
            _parts = [p.strip() for p in _line.split(',') if p.strip()]
            if len(_parts) < 2:
                continue
            _greek_word = _parts[0]
            _greek_norm = _normalize_greek(_greek_word).replace('ς', 'σ')
            _latin_words = [w.lower() for w in _parts[1:]]
            if _greek_norm in CURATED_GREEK_LATIN:
                _existing = set(CURATED_GREEK_LATIN[_greek_norm])
                _existing.update(_latin_words)
                CURATED_GREEK_LATIN[_greek_norm] = list(_existing)
            else:
                CURATED_GREEK_LATIN[_greek_norm] = _latin_words
            _perseus_count += 1
    logger.info(f"Loaded {_perseus_count} Perseus Greek-Latin additions into CURATED_GREEK_LATIN (total: {len(CURATED_GREEK_LATIN)} entries)")


def load_accepted_review_entries():
    """Load accepted entries from the dictionary_review DB table into CURATED_GREEK_LATIN.

    Called at startup and on-demand when admin clicks 'Reload dictionary'.
    Safe to call multiple times — merges without duplicating.
    """
    try:
        from backend.db import get_db_cursor
        count = 0
        with get_db_cursor(commit=False) as cur:
            cur.execute(
                "SELECT greek_lemma, latin_lemma FROM dictionary_review WHERE status = 'accepted'"
            )
            for row in cur.fetchall():
                greek_raw, latin_raw = row[0], row[1]
                greek_norm = _normalize_greek(greek_raw).replace('ς', 'σ')
                latin_word = latin_raw.strip().lower().replace('v', 'u')
                if greek_norm in CURATED_GREEK_LATIN:
                    if latin_word not in CURATED_GREEK_LATIN[greek_norm]:
                        CURATED_GREEK_LATIN[greek_norm].append(latin_word)
                else:
                    CURATED_GREEK_LATIN[greek_norm] = [latin_word]
                count += 1
        logger.info(f"Loaded {count} accepted review entries into CURATED_GREEK_LATIN (total: {len(CURATED_GREEK_LATIN)} entries)")
        return count
    except Exception as e:
        logger.warning(f"Could not load accepted review entries: {e}")
        return 0


# Load accepted entries from DB at startup
load_accepted_review_entries()


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
        # U/V normalization: the V3 dictionary uses v-forms (validus, via)
        # while the UD lemmatizer produces u-forms (ualidus, uia).  Group
        # all spelling variants under a canonical (u-normalized) form and
        # merge their synonym sets so lookups work regardless of spelling.
        def _uv_canonical(word):
            return word.replace('v', 'u')
        canonical_groups = {}
        for key in _LATIN_LOOKUP:
            canon = _uv_canonical(key)
            canonical_groups.setdefault(canon, []).append(key)
        for canon, variants in canonical_groups.items():
            if len(variants) > 1:
                merged_syns = set()
                for v in variants:
                    merged_syns |= _LATIN_LOOKUP[v]
                for v in variants:
                    _LATIN_LOOKUP[v] = merged_syns
        logger.info(f"Loaded {len(_LATIN_LOOKUP)} Latin synonym entries (V3 + curated, u/v merged)")
    return _LATIN_LOOKUP

_COPTIC_LOOKUP = None

def get_coptic_lookup():
    """Load Coptic-Coptic synonym lookup from Coptic Wordnet (Slaughter et al. 2019).

    Returns a dict mapping each Coptic lemma to its set of CWN synonyms.
    Synsets larger than 30 lemmas were skipped during extraction (those are
    broad-concept buckets that generate too much noise; see
    coptic_coptic_wordnet.csv build script).
    """
    global _COPTIC_LOOKUP
    if _COPTIC_LOOKUP is not None:
        return _COPTIC_LOOKUP

    _COPTIC_LOOKUP = {}
    csv_path = os.path.join(
        os.path.dirname(__file__), 'synonymy', 'coptic_coptic_wordnet.csv'
    )
    if not os.path.exists(csv_path):
        logger.warning(f"Coptic Wordnet CSV not found at {csv_path}")
        return _COPTIC_LOOKUP

    import csv
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            src, tgt = row[0].strip().lower(), row[1].strip().lower()
            if not src or not tgt or src == tgt:
                continue
            _COPTIC_LOOKUP.setdefault(src, set()).add(tgt)

    logger.info(f"Loaded {len(_COPTIC_LOOKUP)} Coptic synonym entries from Coptic Wordnet")
    return _COPTIC_LOOKUP


def get_greek_lookup():
    global _GREEK_LOOKUP
    if _GREEK_LOOKUP is None:
        curated = _build_curated_lookup(CURATED_GREEK)
        v3_path = os.path.join(_DATA_DIR, 'fixed_greek_syn.csv')
        v3 = _load_v3_synonym_file(v3_path)
        merged = _merge_lookups(curated, v3)
        # Normalize keys and values to strip diacritics — Greek lemmas from
        # text processing are diacritic-free, so the lookup must match.
        _GREEK_LOOKUP = {}
        for key, synonyms in merged.items():
            norm_key = _normalize_greek(key)
            norm_syns = {_normalize_greek(s) for s in synonyms}
            if norm_key in _GREEK_LOOKUP:
                _GREEK_LOOKUP[norm_key] = _GREEK_LOOKUP[norm_key].union(norm_syns)
            else:
                _GREEK_LOOKUP[norm_key] = norm_syns
        logger.info(f"Loaded {len(_GREEK_LOOKUP)} Greek synonym entries (V3 + curated, diacritic-normalized)")
    return _GREEK_LOOKUP

def find_synonyms(lemma: str, language: str) -> set:
    """Find synonyms for a given lemma."""
    lemma_lower = lemma.lower()
    if language == 'la':
        return get_latin_lookup().get(lemma_lower, set())
    elif language == 'grc':
        return get_greek_lookup().get(lemma_lower, set())
    elif language == 'cop':
        return get_coptic_lookup().get(lemma_lower, set())
    return set()

def are_synonyms(lemma1: str, lemma2: str, language: str) -> bool:
    """Check if two lemmas are synonyms."""
    if lemma1.lower() == lemma2.lower():
        return True
    synonyms1 = find_synonyms(lemma1, language)
    return lemma2.lower() in synonyms1 if synonyms1 else False

def find_synonym_pairs_in_passages(source_lemmas: list, target_lemmas: list, 
                                    language: str, include_lemma_matches: bool = False) -> list:
    """Find synonym pairs between source and target lemma lists.
    
    When include_lemma_matches=False (default): only synonym pairs (different words, same meaning).
    When include_lemma_matches=True: also count same-lemma pairs (e.g. hasta/hastam) for full recall.
    """
    pairs = []
    seen = set()
    
    if language == 'la':
        lookup = get_latin_lookup()
    elif language == 'grc':
        lookup = get_greek_lookup()
    elif language == 'cop':
        lookup = get_coptic_lookup()
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
            if not include_lemma_matches and src_lower == tgt_lower:
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
            logger.info(f"Loaded {len(_GREEK_LATIN_DICT)} Greek-Latin dictionary entries from V3")
        else:
            logger.warning(f"Greek-Latin dictionary not found at {filepath}")
    return _GREEK_LATIN_DICT, _GREEK_LATIN_DICT_NORMALIZED


def _load_english_dict(filepath):
    """Load a classical→English dictionary from Perseus-derived CSV.
    Format: classical_word,english_word (one pair per line).
    Returns dict mapping classical_word → set of English words.
    """
    result = {}
    if not os.path.exists(filepath):
        return result
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip().lower() for p in line.split(',') if p.strip()]
            if len(parts) >= 2:
                classical = parts[0]
                english = parts[1]
                if classical not in result:
                    result[classical] = set()
                result[classical].add(english)
    return result


def get_latin_english_dict():
    """Load the Latin-English cross-lingual dictionary (Perseus Dynamic Lexicon).
    Returns dict mapping Latin lemma → set of English words.
    """
    global _LATIN_ENGLISH_DICT
    if _LATIN_ENGLISH_DICT is None:
        _LATIN_ENGLISH_DICT = {}
        # Primary: Perseus extracted pairs
        filepath = os.path.join(os.path.dirname(__file__), '..', 'data',
                                'perseus_lexicon', 'extracted', 'perseus_latin_english_dict.csv')
        if os.path.exists(filepath):
            _LATIN_ENGLISH_DICT = _load_english_dict(filepath)
            logger.info(f"Loaded {len(_LATIN_ENGLISH_DICT)} Latin-English dictionary entries (Perseus)")
        else:
            logger.warning(f"Latin-English dictionary not found at {filepath}")
        # V6 curated additions (optional)
        additions_path = os.path.join(_DATA_DIR, 'v6_additions', 'latin_english_v6_additions.csv')
        if os.path.exists(additions_path):
            additions = _load_english_dict(additions_path)
            for k, v in additions.items():
                _LATIN_ENGLISH_DICT.setdefault(k, set()).update(v)
            logger.info(f"  + {len(additions)} curated Latin-English additions")
    return _LATIN_ENGLISH_DICT


def get_greek_english_dict():
    """Load the Greek-English cross-lingual dictionary (Perseus Dynamic Lexicon).
    Returns dict mapping normalized Greek lemma → set of English words.
    Greek keys are accent-stripped and sigma-normalized.
    """
    global _GREEK_ENGLISH_DICT
    if _GREEK_ENGLISH_DICT is None:
        _GREEK_ENGLISH_DICT = {}
        filepath = os.path.join(os.path.dirname(__file__), '..', 'data',
                                'perseus_lexicon', 'extracted', 'perseus_greek_english_dict.csv')
        if os.path.exists(filepath):
            raw = _load_english_dict(filepath)
            # Normalize Greek keys: strip accents + sigma normalization
            for greek_key, english_set in raw.items():
                norm = _normalize_greek(greek_key).replace('ς', 'σ')
                _GREEK_ENGLISH_DICT.setdefault(norm, set()).update(english_set)
            logger.info(f"Loaded {len(_GREEK_ENGLISH_DICT)} Greek-English dictionary entries (Perseus)")
        else:
            logger.warning(f"Greek-English dictionary not found at {filepath}")
        # V6 curated additions (optional)
        additions_path = os.path.join(_DATA_DIR, 'v6_additions', 'greek_english_v6_additions.csv')
        if os.path.exists(additions_path):
            raw_add = _load_english_dict(additions_path)
            for greek_key, english_set in raw_add.items():
                norm = _normalize_greek(greek_key).replace('ς', 'σ')
                _GREEK_ENGLISH_DICT.setdefault(norm, set()).update(english_set)
            logger.info(f"  + {len(raw_add)} curated Greek-English additions")
        # Blocklist: drop specific wrong Perseus glosses that produce noisy
        # cross-language hits. The Perseus lexicon file is not in git, so these
        # corrections travel here (normalized Greek key -> english gloss to drop).
        # κράτος = "power/strength", never "storm"; λέγω = "say", never "mean".
        for norm_key, bad_gloss in _GREEK_ENGLISH_BLOCKLIST:
            if norm_key in _GREEK_ENGLISH_DICT:
                _GREEK_ENGLISH_DICT[norm_key].discard(bad_gloss)
                if not _GREEK_ENGLISH_DICT[norm_key]:
                    del _GREEK_ENGLISH_DICT[norm_key]
    return _GREEK_ENGLISH_DICT


# Wrong Perseus Greek->English glosses to drop at load time. Keys are the
# accent-stripped, sigma-normalized Greek form; glosses are lowercased.
_GREEK_ENGLISH_BLOCKLIST = [
    ('κρατοσ', 'storm'),   # κράτος = power/strength, not storm (that is χειμών)
    ('λεγω', 'mean'),      # λέγω = say/speak, not "mean"
]


def find_latin_english_matches(latin_lemmas: list, english_lemmas: list,
                                use_stoplist: bool = True) -> list:
    """Find Latin-English word matches using Perseus dictionary.

    Args:
        latin_lemmas: List of Latin lemma strings
        english_lemmas: List of English lemma strings
        use_stoplist: Whether to filter stopwords

    Returns:
        List of match dicts with source/target indices and matched words
    """
    le_dict = get_latin_english_dict()
    matches = []
    seen = set()

    english_lower_list = [l.lower() for l in english_lemmas]

    for lat_idx, lat_lemma in enumerate(latin_lemmas):
        lat_lower = lat_lemma.lower()

        if use_stoplist and lat_lower in CROSSLINGUAL_STOPLIST_LATIN:
            continue

        # v→u normalization for lookup
        lat_lookup = lat_lower.replace('v', 'u')
        translations = le_dict.get(lat_lookup, set()) | le_dict.get(lat_lower, set())

        for en_word in translations:
            if use_stoplist and en_word in CROSSLINGUAL_STOPLIST_ENGLISH:
                continue

            pair_key = (lat_lower, en_word)
            if pair_key in seen:
                continue

            en_indices = [i for i, l in enumerate(english_lower_list) if l == en_word]
            if en_indices:
                seen.add(pair_key)
                lat_indices = [i for i, l in enumerate(latin_lemmas) if l.lower() == lat_lower]
                matches.append({
                    'source_lemma': lat_lemma,
                    'target_lemma': en_word,
                    'source_indices': lat_indices,
                    'target_indices': en_indices,
                    'type': 'dictionary',
                })

    return matches


def find_greek_english_matches(greek_lemmas: list, english_lemmas: list,
                                use_stoplist: bool = True) -> list:
    """Find Greek-English word matches using Perseus dictionary.

    Args:
        greek_lemmas: List of Greek lemma strings
        english_lemmas: List of English lemma strings
        use_stoplist: Whether to filter stopwords

    Returns:
        List of match dicts with source/target indices and matched words
    """
    ge_dict = get_greek_english_dict()
    matches = []
    seen = set()

    english_lower_list = [l.lower() for l in english_lemmas]

    for grc_idx, grc_lemma in enumerate(greek_lemmas):
        grc_norm = _normalize_greek(grc_lemma).replace('ς', 'σ')

        if use_stoplist and grc_norm in CROSSLINGUAL_STOPLIST_GREEK:
            continue

        translations = ge_dict.get(grc_norm, set())

        for en_word in translations:
            if use_stoplist and en_word in CROSSLINGUAL_STOPLIST_ENGLISH:
                continue

            pair_key = (grc_norm, en_word)
            if pair_key in seen:
                continue

            en_indices = [i for i, l in enumerate(english_lower_list) if l == en_word]
            if en_indices:
                seen.add(pair_key)
                # grc_norm was constructed with ".replace('ς', 'σ')" (final
                # sigma normalized to medial sigma). The per-lemma
                # comparison must apply the same replacement; otherwise
                # masculine nouns ending in final sigma (most Greek -ος
                # forms: λόγος, θεός, ἄνθρωπος, etc.) emit empty
                # source_indices, silently breaking downstream highlighting
                # and any scorer that uses the indices.
                grc_indices = [i for i, l in enumerate(greek_lemmas)
                               if _normalize_greek(l).replace('ς', 'σ') == grc_norm]
                matches.append({
                    'source_lemma': grc_lemma,
                    'target_lemma': en_word,
                    'source_indices': grc_indices,
                    'target_indices': en_indices,
                    'type': 'dictionary',
                })

    return matches


def _get_gazetteer_dict():
    """Load the proper name gazetteer (Wikidata + Pleiades + manual).
    Maps diacritics-stripped Greek names to sets of Latin forms.
    Loaded lazily on first use.
    """
    global _GAZETTEER_DICT
    if _GAZETTEER_DICT is None:
        _GAZETTEER_DICT = {}
        filepath = os.path.join(_PROPER_NAMES_DIR, 'cross_lingual_pairs.json')
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for greek_key, entry in data.items():
                _GAZETTEER_DICT[greek_key] = set(entry['latin'])
            logger.info(f"Loaded {len(_GAZETTEER_DICT)} proper name gazetteer entries (Wikidata + Pleiades + manual)")
        else:
            logger.warning(f"Proper name gazetteer not found at {filepath}")
    return _GAZETTEER_DICT


# Greek-to-Latin transliteration for cognate matching
# Maps normalized (accent-stripped) Greek characters to their most common Latin equivalents
# Multiple variants handled: κ→c/k, υ→u/y, αι→ae, οι→oe, ου→u, ει→i
_GREEK_DIGRAPH_MAP = {
    'αι': 'ae', 'ει': 'i', 'οι': 'oe', 'ου': 'u',
    'φι': 'phi', 'χι': 'chi',
}
_GREEK_CHAR_MAP = {
    'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e',
    'ζ': 'z', 'η': 'e', 'θ': 'th', 'ι': 'i', 'κ': 'c',
    'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'x', 'ο': 'o',
    'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't',
    'υ': 'u', 'φ': 'ph', 'χ': 'ch', 'ψ': 'ps', 'ω': 'o',
}

def _transliterate_greek(greek_text):
    """Transliterate normalized Greek text to Latin characters.
    Returns a set of variant transliterations to handle κ→c/k, υ→u/y, etc.
    """
    norm = _normalize_greek(greek_text)
    if not norm:
        return set()

    # Build primary transliteration, handling digraphs first
    result = []
    i = 0
    while i < len(norm):
        if i + 1 < len(norm):
            digraph = norm[i:i+2]
            if digraph in _GREEK_DIGRAPH_MAP:
                result.append(_GREEK_DIGRAPH_MAP[digraph])
                i += 2
                continue
        char = norm[i]
        result.append(_GREEK_CHAR_MAP.get(char, char))
        i += 1
    primary = ''.join(result)

    # Generate common variants: κ→k, υ→y, c→k
    variants = {primary}
    if 'c' in primary:
        variants.add(primary.replace('c', 'k'))
    if 'u' in primary:
        variants.add(primary.replace('u', 'y'))
    # Handle -os/-us ending (Greek -ος → Latin -us)
    if primary.endswith('os'):
        variants.add(primary[:-2] + 'us')
    # Handle -on/-um ending (Greek -ον → Latin -um)
    if primary.endswith('on'):
        variants.add(primary[:-2] + 'um')
    # Handle -e/-a ending (Greek -η → Latin -a in first declension)
    if primary.endswith('e') and len(primary) > 3:
        variants.add(primary[:-1] + 'a')

    return variants


def _is_cognate_match(greek_norm, latin_lower):
    """Check if a Greek lemma and Latin lemma are cognates via transliteration.
    Conservative: requires exact transliteration match or very close match
    to avoid false positives. Only matches words of 4+ characters.
    """
    if len(greek_norm) < 3 or len(latin_lower) < 4:
        return False

    transliterations = _transliterate_greek(greek_norm)

    for trans in transliterations:
        if len(trans) < 4:
            continue
        # Exact match
        if trans == latin_lower:
            return True
        # One is a prefix of the other (for inflected forms)
        # e.g., achille- matches achilles, achillem, etc.
        shorter, longer = (trans, latin_lower) if len(trans) <= len(latin_lower) else (latin_lower, trans)
        if len(shorter) >= 4 and longer.startswith(shorter) and len(longer) - len(shorter) <= 3:
            return True
        # Same stem (both 5+ chars, share first 4+ chars, differ by ≤ 2 at end)
        if len(trans) >= 5 and len(latin_lower) >= 5:
            # Find common prefix length
            common = 0
            for a, b in zip(trans, latin_lower):
                if a == b:
                    common += 1
                else:
                    break
            # At least 4 shared prefix chars and remaining differs by ≤ 2 chars
            if common >= 4 and max(len(trans), len(latin_lower)) - common <= 2:
                return True

    return False


def find_greek_latin_matches(greek_lemmas: list, latin_lemmas: list, use_stoplist: bool = True) -> list:
    """Find Greek-Latin word matches using curated vocabulary + V3 dictionary + gazetteer + cognate matching.
    Uses accent-normalized Greek for matching.

    Four matching layers:
    1. Curated Greek-Latin pairs (highest confidence, ~76 key entries)
    2. V3 dictionary (34,535 entries from Lewis & Short / LSJ)
    3. Proper name gazetteer (~1,500 entries from Wikidata + Pleiades + manual)
    4. Cognate matching via transliteration (borrowed vocabulary, remaining proper nouns)

    Args:
        greek_lemmas: List of Greek lemmas from source text
        latin_lemmas: List of Latin lemmas from target text
        use_stoplist: If True, skip common function words (default True)

    Returns:
        List of match dicts with source/target indices and matched words
    """
    _, gl_dict_norm = get_greek_latin_dict()
    gazetteer = _get_gazetteer_dict()

    matches = []
    seen = set()

    latin_lower_set = {l.lower() for l in latin_lemmas}
    latin_lower_list = [l.lower() for l in latin_lemmas]

    for grc_idx, grc_lemma in enumerate(greek_lemmas):
        grc_norm = _normalize_greek(grc_lemma)

        # Skip Greek stopwords
        if use_stoplist and grc_norm in CROSSLINGUAL_STOPLIST_GREEK:
            continue

        grc_lookup = grc_norm.replace('ς', 'σ')  # medial sigma to match dict keys
        # Normalize v→u so every layer of the Greek-Latin dictionary matches
        # what the UD lemmatizer emits on the target side. The V3 dictionary
        # (~34,500 entries) stores Latin glosses with v-forms (vasto, venio,
        # vulnero) while the text processor produces u-forms (uasto, uenio,
        # uulnero). Only the curated layer was previously normalized, so any
        # V3 or gazetteer entry whose Latin gloss contains a 'v' could never
        # intersect the target text's lemma set. Apply the same replacement
        # to all three sources so they share a single canonical lookup space.
        curated_translations = {w.replace('v', 'u') for w in CURATED_GREEK_LATIN.get(grc_lookup, [])}
        v3_translations = {w.replace('v', 'u') for w in (gl_dict_norm.get(grc_norm, set()) if gl_dict_norm else set())}
        gazetteer_translations = {w.replace('v', 'u') for w in gazetteer.get(grc_norm, set())}
        latin_translations = curated_translations.union(v3_translations).union(gazetteer_translations)

        if latin_translations:
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

    # Layer 3: Cognate matching via transliteration for unmatched Greek lemmas
    # This catches proper nouns, borrowed vocabulary, and shared roots
    matched_greek_norms = {pair_key[0] for pair_key in seen}

    for grc_idx, grc_lemma in enumerate(greek_lemmas):
        grc_norm = _normalize_greek(grc_lemma)

        # Skip if already matched by dictionary or if stopword
        if grc_norm in matched_greek_norms:
            continue
        if use_stoplist and grc_norm in CROSSLINGUAL_STOPLIST_GREEK:
            continue
        if len(grc_norm) < 3:
            continue

        for lat_lower in latin_lower_set:
            if use_stoplist and lat_lower in CROSSLINGUAL_STOPLIST_LATIN:
                continue

            pair_key = (grc_norm, lat_lower)
            if pair_key in seen:
                continue

            if _is_cognate_match(grc_norm, lat_lower):
                seen.add(pair_key)
                matched_greek_norms.add(grc_norm)

                lat_indices = [i for i, l in enumerate(latin_lower_list) if l == lat_lower]
                grc_indices = [i for i, l in enumerate(greek_lemmas) if _normalize_greek(l) == grc_norm]

                matches.append({
                    'greek_lemma': grc_lemma,
                    'latin_lemma': latin_lemmas[lat_indices[0]] if lat_indices else lat_lower,
                    'greek_indices': grc_indices,
                    'latin_indices': lat_indices,
                    'type': 'cognate'
                })
                break  # One cognate match per Greek lemma to avoid noise

    return matches
