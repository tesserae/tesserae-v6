"""
Tesserae V6 - Metrical Scanner
Scans Latin poetry for metrical patterns.
Uses pre-computed MQDQ (Musisque Deoque) scansions from Pede Certo when available,
falling back to CLTK for texts not in the MQDQ database.

Supports multiple meters:
- Dactylic hexameter (epic: Vergil, Lucan, Statius Thebaid)
- Hendecasyllable (Catullus, Martial, Statius Silvae)
- Elegiac couplet (Ovid, Tibullus, Propertius)

MQDQ Credits: 
- Pede Certo (https://www.pedecerto.eu) - University of Udine
- Licensed under CC-BY-NC-ND 4.0
"""
import json
import os
import re

# CLTK is optional - only used as fallback when MQDQ scansions are not available
_CLTK_AVAILABLE = False
HexameterScanner = None
HendecasyllableScanner = None
PentameterScanner = None

try:
    from cltk.prosody.lat.hexameter_scanner import HexameterScanner
    from cltk.prosody.lat.hendecasyllable_scanner import HendecasyllableScanner
    from cltk.prosody.lat.pentameter_scanner import PentameterScanner
    _CLTK_AVAILABLE = True
except ImportError:
    pass

_hexameter_scanner = None
_hendecasyllable_scanner = None
_pentameter_scanner = None
_mqdq_scansions = None

def get_mqdq_scansions():
    """Load pre-computed MQDQ scansion database"""
    global _mqdq_scansions
    if _mqdq_scansions is None:
        scansion_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'scansion', 'mqdq_scansions.json')
        if os.path.exists(scansion_path):
            try:
                with open(scansion_path, 'r', encoding='utf-8') as f:
                    _mqdq_scansions = json.load(f)
            except Exception as e:
                print(f"Error loading MQDQ scansions: {e}")
                _mqdq_scansions = {}
        else:
            _mqdq_scansions = {}
    return _mqdq_scansions

TESS_TO_MQDQ_MAP = {
    'verg': 'vergilius',
    'vergil': 'vergilius',
    'vergilius': 'vergilius',
    'luc': 'lucanus',
    'lucan': 'lucanus',
    'lucanus': 'lucanus',
    'ov': 'ouidius',
    'ovid': 'ouidius',
    'ouidius': 'ouidius',
    'hor': 'horatius',
    'horace': 'horatius',
    'horatius': 'horatius',
    'stat': 'statius',
    'statius': 'statius',
    'lucr': 'lucretius',
    'lucretius': 'lucretius',
    'cat': 'catullus',
    'catu': 'catullus',
    'catullus': 'catullus',
    'tib': 'tibullus',
    'tibullus': 'tibullus',
    'prop': 'propertius',
    'propertius': 'propertius',
    'juv': 'iuuenalis',
    'juvenal': 'iuuenalis',
    'iuuenalis': 'iuuenalis',
    'sil': 'silius_italicus',
    'silius': 'silius_italicus',
    'silius_italicus': 'silius_italicus',
    'val': 'valerius_flaccus',
    'mart': 'martialis',
    'martial': 'martialis',
    'martialis': 'martialis',
    'valerius': 'valerius_flaccus',
    'valerius_flaccus': 'valerius_flaccus',
    'sen': 'seneca',
    'seneca': 'seneca',
    'pers': 'persius',
    'persius': 'persius',
    'claud': 'claudianus',
    'claudian': 'claudianus',
    'claudianus': 'claudianus',
    'manil': 'manilius',
    'manilius': 'manilius',
    'calp': 'calpurnius_siculus',
    'calpurnius': 'calpurnius_siculus',
    'calpurnius_siculus': 'calpurnius_siculus',
    'petron': 'petronius',
    'petronius': 'petronius',
    'col': 'columella',
    'columella': 'columella',
    'iuuenc': 'iuuencus',
    'juvencus': 'iuuencus',
    'iuuencus': 'iuuencus',
}

TESS_WORK_TO_MQDQ = {
    'aene': 'Aeneis',
    'aen': 'Aeneis',
    'aeneid': 'Aeneis',
    'ecl': 'eclogae',
    'eclo': 'eclogae',
    'eclogues': 'eclogae',
    'georg': 'georgicon',
    'geo': 'georgicon',
    'georgics': 'georgicon',
    'phar': 'Pharsalia',
    'bellum_civile': 'Pharsalia',
    'bellum': 'Pharsalia',
    'pharsalia': 'Pharsalia',
    'civil_war': 'Pharsalia',
    'meta': 'metamorphoses',
    'met': 'metamorphoses',
    'metamorphoses': 'metamorphoses',
    'amor': 'amores',
    'am': 'amores',
    'amores': 'amores',
    'ars': 'ars',
    'ars_amatoria': 'ars',
    'fast': 'fasti',
    'fasti': 'fasti',
    'trist': 'tristia',
    'tristia': 'tristia',
    'pont': 'ex_Ponto',
    'ex_ponto': 'ex_Ponto',
    'her': 'epistulae_heroides',
    'heroides': 'epistulae_heroides',
    'ibis': 'Ibis',
    'rem': 'remedia_amoris',
    'remedia': 'remedia_amoris',
    'sat': 'saturae',
    'serm': 'saturae',
    'satires': 'saturae',
    'sermones': 'saturae',
    'carm': 'carmina',
    'carmina': 'carmina',
    'odes': 'carmina',
    'epist': 'epistulae',
    'epistles': 'epistulae',
    'epistulae': 'epistulae',
    'epod': 'epodi',
    'epodes': 'epodi',
    'theb': 'Thebais',
    'thebaid': 'Thebais',
    'achil': 'Achilleis',
    'achilleid': 'Achilleis',
    'silv': 'siluae',
    'silvae': 'siluae',
    'pun': 'Punica',
    'punica': 'Punica',
    'argo': 'Argonautica',
    'argonautica': 'Argonautica',
    'rer': 'de_rerum_natura',
    'de_rerum_natura': 'de_rerum_natura',
    'astr': 'astronomica',
    'astronomica': 'astronomica',
    'epig': 'epigrammata',
    'epigrammata': 'epigrammata',
    'epigrams': 'epigrammata',
    'spect': 'de_spectaculis',
    'spectacula': 'de_spectaculis',
    'med': 'Medea',
    'medea': 'Medea',
    'oed': 'Oedipus',
    'oedipus': 'Oedipus',
    'apoc': 'apocolocyntosis',
    'rapt': 'de_raptu_Proserpinae',
    'ruf': 'in_Rufinum',
    'eutr': 'in_Eutropium',
    'stil': 'de_consulatu_Stilichonis',
    'evang': 'euangeliorum_libri',
    'eleg': 'elegiae',
    'elegies': 'elegiae',
}

ELEGIAC_BOOK_WORKS = {
    'am': 'amores',
    'amores': 'amores',
    'trist': 'tristia',
    'tristia': 'tristia',
    'pont': 'ex_Ponto',
    'ex_ponto': 'ex_Ponto',
}

# Works with book-specific MQDQ keys (author.work_N format)
BOOK_SPECIFIC_WORKS = {
    'silv': 'siluae',
    'silvae': 'siluae',
    'siluae': 'siluae',
}

def expand_mqdq_pattern(pattern, meter_code):
    """
    Expand MQDQ shorthand pattern codes to full scansion marks.
    
    MQDQ pattern codes:
    - D = dactyl (–∪∪)
    - S = spondee (––)
    - - = anceps/long (–)
    - | = caesura (pentameter diaeresis)
    - = = long syllable (–)
    
    Latin pentameter structure: –∪∪/–– + –∪∪/–– + – | –∪∪ + –∪∪ + –
    (First hemistich: 2 variable feet + half-foot, then caesura, then 2 fixed dactyls + final anceps)
    
    Latin hexameter structure: 6 feet, but MQDQ only encodes feet 1-4 (variable feet).
    Foot 5 is almost always a dactyl (–∪∪), foot 6 is always –× (adonic ending).
    """
    if not pattern:
        return None
    
    expanded = ''
    for char in pattern:
        if char == 'D':
            expanded += '–∪∪'
        elif char == 'S':
            expanded += '––'
        elif char == '-' or char == '=':
            expanded += '–'
        elif char == '|':
            expanded += '|'  # Keep caesura marker
        elif char == 'U' or char == 'u':
            expanded += '∪'
        elif char == 'X' or char == 'x':
            expanded += '×'  # Anceps
        # Ignore other characters
    
    # For hexameters, MQDQ patterns only encode feet 1-4
    # Add the 5th foot (dactyl –∪∪) and 6th foot (–×) to complete the adonic ending
    if meter_code == 'H':
        # Check if we only have 4 feet (11 chars for DDDD or similar)
        # Full hexameter should be ~16 chars: 4 variable feet + dactyl + anceps
        clean_expanded = expanded.replace('|', '')
        if len(clean_expanded) <= 12 and not expanded.endswith('×'):
            # Add 5th dactyl and 6th anceps (adonic ending: –∪∪–×)
            expanded += '–∪∪–×'
        elif not expanded.endswith('×'):
            # Just add final anceps if pattern is longer but missing it
            expanded += '×'
    
    return expanded

def lookup_mqdq_scansion(locus):
    """
    Look up a scansion from the MQDQ database.
    Handles tess format loci like "verg. aen. 1.1" or "vergilius.Aeneis.1.1"
    Also handles Martial's format: "mart. 1.2.3" (book.poem.line, no work name)
    And elegiac works with book-specific MQDQ keys: "ov. am. 1.1.1" -> ouidius.amores_1
    Returns scansion dict or None if not found.
    """
    scansions = get_mqdq_scansions()
    if not scansions:
        return None
    
    locus_clean = locus.strip('<>').replace(' ', '').lower()
    
    parts = locus_clean.split('.')
    if len(parts) < 3:
        return None
    
    author_short = parts[0]
    author_key = TESS_TO_MQDQ_MAP.get(author_short, author_short)
    
    # Special handling for Martial
    # Format 1: mart.BOOK.POEM.LINE (no work name) - parts[1].isdigit()
    # Format 2: martial.epigrams.BOOK.POEM.LINE - from feature extractor
    if author_key == 'martialis':
        book_num = None
        line_ref = None
        
        if len(parts) >= 4 and parts[1].isdigit():
            # Format: mart.9.84.10 -> book=9, line_ref=84.10
            book_num = parts[1]
            line_ref = f"{parts[2]}.{parts[3]}"
        elif len(parts) >= 5 and parts[1] in ('epigrams', 'epigrammata') and parts[2].isdigit():
            # Format: martial.epigrams.9.84.10 -> book=9, line_ref=84.10
            book_num = parts[2]
            line_ref = f"{parts[3]}.{parts[4]}"
        
        if book_num and line_ref:
            mqdq_key = f"martialis.epigrammata_{book_num}"
            
            if mqdq_key in scansions:
                work_data = scansions[mqdq_key]
                if line_ref in work_data.get('lines', {}):
                    line_data = work_data['lines'][line_ref]
                    meter_code = line_data.get('meter', '')
                    pattern_code = line_data.get('pattern', '')
                    
                    # Prefer expanding pattern code over using truncated scansion
                    if pattern_code:
                        expanded = expand_mqdq_pattern(pattern_code, meter_code)
                        if expanded:
                            display_pattern = expanded.replace('|', '')
                            spaced_scansion = ' '.join(list(display_pattern))
                            meter_name = 'hexameter' if meter_code == 'H' else ('pentameter' if meter_code == 'P' else 'hendecasyllable')
                            return {
                                'pattern': display_pattern,
                                'raw': spaced_scansion,
                                'valid': True,
                                'meter': meter_name,
                                'source': 'mqdq'
                            }
                    
                    # Fallback to stored scansion if pattern expansion fails
                    raw_scansion = line_data.get('scansion', '')
                    if not raw_scansion:
                        return None
                    spaced_scansion = ' '.join(list(raw_scansion)) if raw_scansion else ''
                    meter_name = 'hexameter' if meter_code == 'H' else ('pentameter' if meter_code in ('D', 'P') else 'hendecasyllable')
                    return {
                        'pattern': raw_scansion,
                        'raw': spaced_scansion,
                        'valid': True,
                        'meter': meter_name,
                        'source': 'mqdq'
                    }
            return None
    
    work_short = parts[1] if len(parts) > 1 else ''
    
    # Special handling for Ovid elegiac works with book-specific MQDQ keys
    # Format: "ov.am.1.1.1" (author.work.book.poem.line) -> ouidius.amores_1, key "1.1"
    if author_key == 'ouidius' and work_short in ELEGIAC_BOOK_WORKS and len(parts) >= 5:
        work_name = ELEGIAC_BOOK_WORKS[work_short]
        book_num = parts[2]
        mqdq_key = f"ouidius.{work_name}_{book_num}"
        line_ref = f"{parts[3]}.{parts[4]}"  # poem.line within book
        
        if mqdq_key in scansions:
            work_data = scansions[mqdq_key]
            if line_ref in work_data.get('lines', {}):
                line_data = work_data['lines'][line_ref]
                meter_code = line_data.get('meter', '')
                pattern_code = line_data.get('pattern', '')
                
                # Prefer expanding pattern code over using truncated scansion
                if pattern_code:
                    expanded = expand_mqdq_pattern(pattern_code, meter_code)
                    if expanded:
                        display_pattern = expanded.replace('|', '')
                        spaced_scansion = ' '.join(list(display_pattern))
                        meter_name = 'hexameter' if meter_code == 'H' else 'pentameter'
                        return {
                            'pattern': display_pattern,
                            'raw': spaced_scansion,
                            'valid': True,
                            'meter': meter_name,
                            'source': 'mqdq'
                        }
                
                # Fallback to stored scansion
                raw_scansion = line_data.get('scansion', '')
                if not raw_scansion:
                    return None
                spaced_scansion = ' '.join(list(raw_scansion)) if raw_scansion else ''
                meter = 'hexameter' if meter_code == 'H' else 'pentameter'
                return {
                    'pattern': raw_scansion,
                    'raw': spaced_scansion,
                    'valid': True,
                    'meter': meter,
                    'source': 'mqdq'
                }
        return None
    
    # Special handling for Statius Silvae with book-specific MQDQ keys
    # Format: "stat.silv.1.1.1" (author.work.book.poem.line) -> statius.siluae_1, key "1.1"
    if author_key == 'statius' and work_short in BOOK_SPECIFIC_WORKS and len(parts) >= 5:
        work_name = BOOK_SPECIFIC_WORKS[work_short]
        book_num = parts[2]
        mqdq_key = f"statius.{work_name}_{book_num}"
        line_ref = f"{parts[3]}.{parts[4]}"  # poem.line within book
        
        if mqdq_key in scansions:
            work_data = scansions[mqdq_key]
            if line_ref in work_data.get('lines', {}):
                line_data = work_data['lines'][line_ref]
                meter_code = line_data.get('meter', '')
                pattern_code = line_data.get('pattern', '')
                
                if pattern_code:
                    expanded = expand_mqdq_pattern(pattern_code, meter_code)
                    if expanded:
                        display_pattern = expanded.replace('|', '')
                        spaced_scansion = ' '.join(list(display_pattern))
                        meter_name = 'hexameter' if meter_code == 'H' else 'hendecasyllable'
                        return {
                            'pattern': display_pattern,
                            'raw': spaced_scansion,
                            'valid': True,
                            'meter': meter_name,
                            'source': 'mqdq'
                        }
                
                raw_scansion = line_data.get('scansion', '')
                if not raw_scansion:
                    return None
                spaced_scansion = ' '.join(list(raw_scansion)) if raw_scansion else ''
                meter_name = 'hexameter' if meter_code == 'H' else 'hendecasyllable'
                return {
                    'pattern': raw_scansion,
                    'raw': spaced_scansion,
                    'valid': True,
                    'meter': meter_name,
                    'source': 'mqdq'
                }
        return None
    
    work_key = None
    for tess_work, mqdq_work in TESS_WORK_TO_MQDQ.items():
        if work_short.startswith(tess_work):
            work_key = mqdq_work
            break
    
    if not work_key:
        work_key = work_short
    
    mqdq_key = f"{author_key}.{work_key}".lower()
    
    # Build line reference - be strict to avoid matching wrong lines
    line_refs_to_try = []
    if len(parts) >= 5:
        line_refs_to_try.append(f"{parts[3]}.{parts[4]}")  # poem.line
    if len(parts) >= 4:
        line_refs_to_try.append(f"{parts[2]}.{parts[3]}")
    
    for stored_key, work_data in scansions.items():
        if stored_key.lower() == mqdq_key:
            for line_ref in line_refs_to_try:
                if line_ref in work_data.get('lines', {}):
                    line_data = work_data['lines'][line_ref]
                    meter_code = line_data.get('meter', '')
                    pattern_code = line_data.get('pattern', '')
                    
                    # Prefer expanding pattern code over using truncated scansion
                    if pattern_code:
                        expanded = expand_mqdq_pattern(pattern_code, meter_code)
                        if expanded:
                            display_pattern = expanded.replace('|', '')
                            spaced_scansion = ' '.join(list(display_pattern))
                            meter_name = 'hexameter' if meter_code == 'H' else ('pentameter' if meter_code == 'P' else 'elegiac')
                            return {
                                'pattern': display_pattern,
                                'raw': spaced_scansion,
                                'valid': True,
                                'meter': meter_name,
                                'source': 'mqdq'
                            }
                    
                    # Fallback to stored scansion
                    raw_scansion = line_data.get('scansion', '')
                    if not raw_scansion:
                        continue
                    spaced_scansion = ' '.join(list(raw_scansion)) if raw_scansion else ''
                    meter_name = 'hexameter' if meter_code == 'H' else ('pentameter' if meter_code == 'P' else 'elegiac')
                    return {
                        'pattern': raw_scansion,
                        'raw': spaced_scansion,
                        'valid': True,
                        'meter': meter_name,
                        'source': 'mqdq'
                    }
    
    return None

def get_scansion_for_line(text_id, line_number, text=None):
    """
    Get scansion for a line, trying MQDQ database first, then CLTK.
    text_id: work identifier (e.g., "verg. aen.")
    line_number: line reference (e.g., "1.1")
    text: the actual line text (for CLTK fallback)
    """
    locus = f"{text_id}.{line_number}".strip()
    
    mqdq_result = lookup_mqdq_scansion(locus)
    if mqdq_result:
        return mqdq_result
    
    if text:
        meter_type = detect_meter_type(text_id)
        return scan_latin_verse(text, meter_type)
    
    return None

def get_hexameter_scanner():
    """Lazy-load the Latin hexameter scanner"""
    global _hexameter_scanner
    if _hexameter_scanner is None and _CLTK_AVAILABLE and HexameterScanner:
        _hexameter_scanner = HexameterScanner()
    return _hexameter_scanner

def get_hendecasyllable_scanner():
    """Lazy-load the Latin hendecasyllable scanner"""
    global _hendecasyllable_scanner
    if _hendecasyllable_scanner is None and _CLTK_AVAILABLE and HendecasyllableScanner:
        _hendecasyllable_scanner = HendecasyllableScanner()
    return _hendecasyllable_scanner

def get_pentameter_scanner():
    """Lazy-load the Latin pentameter scanner"""
    global _pentameter_scanner
    if _pentameter_scanner is None and _CLTK_AVAILABLE and PentameterScanner:
        _pentameter_scanner = PentameterScanner()
    return _pentameter_scanner

METER_TYPES = {
    'hexameter': ['vergil.', 'verg.', 'vergilius.', 'aeneid', 'aeneis', 'eclogues', 'eclogae', 'georgics', 'georgicon',
                  'ovid.metamorphoses', 'ouidius.metamorphoses', 'metamorphoses',
                  'lucan.', 'luc.', 'lucanus.', 'bellum_civile', 'pharsalia',
                  'statius.thebaid', 'statius.achilleid', 'thebaid', 'thebais', 'achilleid', 'achilleis',
                  'silius.', 'silius_italicus.', 'punica', 'valerius', 'valerius_flaccus.', 'argonautica',
                  'lucretius.', 'lucr.', 'de_rerum_natura',
                  'juvenal.', 'juv.', 'iuuenalis.', 'saturae',
                  'seneca.hercules', 'seneca.medea', 'seneca.troades', 'seneca.phaedra',
                  'seneca.oedipus', 'seneca.agamemnon', 'seneca.thyestes',
                  'horace.sermones', 'horace.epistulae', 'horace.ars', 'horatius.saturae', 'horatius.epistulae',
                  'manilius.', 'astronomica', 'claudianus.', 'iuuencus.', 'petronius.'],
    'hendecasyllable': ['catullus.', 'cat.', 'catu.', 'martial.', 'mart.', 'martialis.',
                        'statius.silvae', 'statius.siluae', 'silvae', 'siluae'],
    'elegiac': ['ovid.amores', 'ovid.ars_amatoria', 'ovid.fasti', 'ovid.tristia', 
                'ovid.epistulae_ex_ponto', 'ovid.heroides',
                'ouidius.amores', 'ouidius.ars', 'ouidius.fasti', 'ouidius.tristia',
                'ouidius.ex_ponto', 'ouidius.epistulae_heroides', 'ouid.',
                'tibullus.', 'tib.', 'propertius.', 'prop.', 'elegiae']
}

def detect_meter_type(text_id):
    """Detect which meter type a text uses based on its ID"""
    text_lower = text_id.lower()
    
    for meter_type, markers in METER_TYPES.items():
        for marker in markers:
            if marker in text_lower:
                return meter_type
    
    return 'hexameter'

def scan_latin_verse(text, meter_type='hexameter'):
    """
    Scan a Latin verse and return the scansion pattern.
    Supports hexameter, hendecasyllable, and elegiac (pentameter) meters.
    Returns a dict with:
    - pattern: string of '-' (long) and 'u' (short) syllables
    - raw: formatted scansion for display
    - valid: whether the scanner considers it valid
    - meter: the meter type used
    
    Only returns scansion if scanner marks it as valid to avoid incorrect displays.
    """
    try:
        if meter_type == 'hendecasyllable':
            scanner = get_hendecasyllable_scanner()
        elif meter_type == 'elegiac':
            scanner = get_pentameter_scanner()
        else:
            scanner = get_hexameter_scanner()
        
        result = scanner.scan(text)
        
        if hasattr(result, 'scansion') and result.scansion:
            is_valid = getattr(result, 'valid', False)
            raw_scansion = result.scansion.strip()
            pattern = raw_scansion.replace(' ', '').replace('U', 'u')
            
            formatted = format_scansion_for_display(pattern)
            
            return {
                'pattern': pattern,
                'raw': formatted if is_valid else None,
                'valid': is_valid,
                'meter': meter_type
            }
    except Exception as e:
        print(f"Error scanning verse ({meter_type}): {e}")
    
    return None

def format_scansion_for_display(pattern):
    """
    Format a scansion pattern for display with proper symbols.
    Only formats if pattern looks valid.
    """
    if not pattern:
        return None
    
    clean = pattern.replace(' ', '').upper()
    
    if len(clean) < 5:
        return None
    
    formatted = []
    for char in clean:
        if char == '-':
            formatted.append('–')
        elif char == 'U':
            formatted.append('∪')
        else:
            formatted.append(' ')
    
    return ' '.join(formatted)

def calculate_metrical_similarity(pattern1, pattern2):
    """
    Calculate similarity between two metrical patterns.
    Returns a score 0.0-1.0 based on matching positions.
    """
    if not pattern1 or not pattern2:
        return 0.0
    
    p1 = pattern1.replace(' ', '').lower()
    p2 = pattern2.replace(' ', '').lower()
    
    if not p1 or not p2:
        return 0.0
    
    min_len = min(len(p1), len(p2))
    max_len = max(len(p1), len(p2))
    
    if max_len == 0:
        return 0.0
    
    matches = sum(1 for i in range(min_len) if p1[i] == p2[i])
    
    length_penalty = min_len / max_len
    position_score = matches / min_len if min_len > 0 else 0
    
    return position_score * length_penalty

def format_scansion_display(text, pattern):
    """
    Format a line of text with scansion marks above/below.
    Returns HTML-safe display string.
    """
    if not pattern:
        return text
    
    marks = []
    for char in pattern:
        if char == '-':
            marks.append('–')
        elif char.lower() == 'u':
            marks.append('∪')
        else:
            marks.append(' ')
    
    scansion_line = ''.join(marks)
    
    return {
        'text': text,
        'scansion': scansion_line,
        'pattern': pattern
    }

POETRY_WORKS = {
    'la': [
        # Hexameter epics with verified MQDQ scansion data
        'vergil.', 'verg.', 'aeneid', 'aen.', 'eclogues', 'ecl.', 'georgics', 'georg.',
        'lucan.', 'luc.', 'bellum_civile', 'pharsalia',
        'statius.', 'stat.', 'statius.thebaid', 'statius.achilleid', 'statius.silvae',
        'thebaid', 'theb.', 'achilleid', 'silvae',
        'silius.', 'sil.', 'punica',
        'valerius_flaccus', 'val.flac', 'argonautica',
        'lucretius.', 'lucr.', 'de_rerum_natura',
        'ovid.metamorphoses', 'ovidius.metamorphoses',
        # Martial - line numbering aligns correctly with MQDQ data
        'martial.', 'mart.', 'martialis.', 'epigrammata',
        # Elegiac poetry - uses CLTK fallback when MQDQ doesn't match
        'ovid.amores', 'ovid.ars', 'ovid.fasti', 'ovid.tristia', 'ovid.heroides',
        'ov.am', 'ov.ars', 'ov.fast', 'ov.trist', 'ov.her',
        'amores', 'ars_amatoria', 'fasti', 'tristia', 'heroides',
        'catullus.', 'cat.', 'catu.', 'tibullus.', 'tib.', 'propertius.', 'prop.',
        # Late Antique poets
        'claudian', 'claud.', 'claudianus',
        'prudentius', 'prud.',
        'ausonius', 'auson.',
        'dracontius', 'drac.',
        'avianus', 'avian.',
        'paulinus', 'paul.nol',
        'sidonius', 'sidon.',
        'venantius', 'ven.fort', 'fortunatus',
        'corippus', 'corip.',
        'ennodius', 'ennod.',
        'arator',
        'sedulius', 'sedul.',
        'juvencus', 'juven.',
        'avitus', 'alcim',
        # Medieval poets
        'hrabanus', 'hraban', 'rabanus',
        'hildebert', 'hildeb.',
        'marbod', 'marbod.',
        'alan', 'alanus', 'alan.lille',
        'walter', 'gualterus', 'walt.chatillon',
        'bernard', 'bern.silv', 'bernardus.silvestris',
        'matthew', 'mattheus', 'matth.vindoc',
        'godfrey', 'godefridus',
        'nigel', 'nigellus',
        'josephus', 'joseph.iscanus',
        # Horace and other classical poets
        'horace', 'horat.', 'hor.', 'horatius',
        'persius', 'pers.',
        'juvenal', 'juv.', 'iuvenal',
        'phaedrus', 'phaedr.',
        'manilius', 'manil.',
        'seneca.tragediae', 'sen.trag', 'seneca.hercules', 'seneca.medea', 'seneca.troades', 'seneca.phaedra', 'seneca.oedipus', 'seneca.agamemnon', 'seneca.thyestes', 'seneca.phoenissae', 'seneca.octavia',
        'plautus', 'plaut.',
        'terence', 'ter.', 'terentius',
        'ennius', 'enn.',
    ],
    'grc': [
        # Epic poetry
        'homer', 'hom.', 'iliad', 'il.', 'odyssey', 'od.',
        'hesiod', 'hes.', 'theogony', 'theog.', 'works_and_days', 'wd.',
        'apollonius', 'apoll.', 'argonautica',
        # Tragedy
        'aeschylus', 'aesch.', 'agamemnon', 'ag.', 'choephoroe', 'cho.', 'eumenides', 'eum.',
        'persae', 'pers.', 'prometheus', 'prom.', 'seven', 'sept.', 'suppliants', 'supp.',
        'sophocles', 'soph.', 'ajax', 'aj.', 'antigone', 'ant.', 'electra', 'el.',
        'oedipus', 'ot.', 'oc.', 'philoctetes', 'phil.', 'trachiniae', 'trach.',
        'euripides', 'eur.', 'alcestis', 'alc.', 'andromache', 'andr.', 'bacchae', 'ba.',
        'cyclops', 'cycl.', 'hecuba', 'hec.', 'helen', 'hel.', 'heraclidae', 'heracl.',
        'heracles', 'hf.', 'hippolytus', 'hipp.', 'ion', 'iphigenia', 'ia.', 'it.',
        'medea', 'med.', 'orestes', 'or.', 'phoenissae', 'phoen.', 'rhesus', 'rhes.', 'troades', 'tro.',
        # Comedy
        'aristophanes', 'ar.', 'acharnians', 'ach.', 'birds', 'clouds', 'frogs', 'knights',
        'lysistrata', 'peace', 'wasps', 'women', 'plutus', 'menander', 'men.',
        # Lyric and other poetry
        'pindar', 'pind.', 'olympian', 'pythian', 'nemean', 'isthmian',
        'sappho', 'sapph.', 'alcaeus', 'alc.', 'anacreon', 'anacr.',
        'theocritus', 'theoc.', 'idylls', 'id.',
        'callimachus', 'callim.', 'hymns', 'aetia',
        'aratus', 'arat.', 'phaenomena',
        'nonnus', 'nonn.', 'dionysiaca',
        'quintus', 'quint.smyrn', 'posthomerica',
    ],
    'en': [
        # Shakespeare poetry/drama (verse plays)
        'shakespeare', 'shak.', 'hamlet', 'macbeth', 'othello', 'lear', 'tempest',
        'midsummer', 'romeo', 'juliet', 'merchant', 'twelfth', 'comedy',
        'sonnets', 'venus', 'adonis', 'lucrece',
        # Epic poetry
        'milton', 'paradise_lost', 'paradise_regained', 'samson',
        'spenser', 'faerie', 'queene',
        # Romantic poets
        'wordsworth', 'coleridge', 'keats', 'shelley', 'byron',
        'prelude', 'lyrical', 'ballads', 'rime', 'mariner',
        # Other major poets
        'chaucer', 'canterbury', 'pope', 'dryden', 'tennyson',
        'browning', 'cowper', 'task', 'blake', 'donne', 'herbert',
        'marvell', 'jonson', 'sidney', 'astrophil', 'stella',
    ]
}

PROSE_WORKS = {
    'la': [
        'cicero', 'cic.', 'caesar', 'caes.', 'livy', 'liv.', 'sallust', 'sall.',
        'tacitus', 'tac.', 'suetonius', 'suet.', 'nepos', 'nep.', 'quintilian', 'quint.',
        'pliny', 'plin.', 'apuleius', 'apul.', 'petronius', 'petron.',
        'augustine', 'aug.', 'jerome', 'hier.', 'ambrose', 'ambr.', 'seneca_prose',
        'de_officiis', 'de_oratore', 'de_finibus', 'de_natura', 'tusculan',
        'epistulae', 'letters', 'bellum_gallicum',
        'historiae', 'annales', 'agricola', 'germania', 'dialogus',
        'satyricon', 'confessions', 'de_civitate'
    ],
    'grc': [
        'plato', 'plat.', 'aristotle', 'arist.', 'thucydides', 'thuc.',
        'herodotus', 'hdt.', 'xenophon', 'xen.', 'demosthenes', 'dem.',
        'lysias', 'lys.', 'isocrates', 'isoc.', 'plutarch', 'plut.',
        'diodorus', 'diod.', 'polybius', 'polyb.', 'strabo', 'strab.',
        'republic', 'symposium', 'phaedo', 'apology', 'laws', 'politics',
        'ethics', 'rhetoric', 'poetics', 'histories', 'anabasis',
        'hellenica', 'memorabilia', 'lives', 'moralia',
        'achilles_tatius', 'leucippe', 'aelian', 'varia_historia',
        'aelius_aristides', 'orationes', 'aeschines', 'against_',
        'aesop', 'fabulae', 'apollodorus', 'epitome', 'archimedes', 'archimède',
        'lucian', 'longus', 'daphnis', 'dio_chrysostom', 'epictetus',
        'marcus_aurelius', 'meditations', 'pausanias', 'athenaeus',
        'diogenes_laertius', 'josephus', 'philo', 'galen', 'hippocrates',
        'epistulae', 'progymnasmata', 'ars_rhetorica'
    ],
    'en': [
        # Prose fiction
        'defoe', 'robinson', 'crusoe', 'moll', 'flanders',
        'richardson', 'pamela', 'clarissa',
        'fielding', 'tom_jones', 'joseph_andrews',
        'austen', 'pride', 'prejudice', 'sense', 'sensibility', 'emma', 'mansfield',
        'dickens', 'oliver', 'twist', 'expectations', 'copperfield', 'tale_two',
        # Essays and philosophy
        'bacon', 'essays', 'locke', 'hume', 'mill', 'liberty',
        'addison', 'steele', 'spectator', 'johnson', 'rambler',
        # Historical and political prose
        'gibbon', 'decline', 'fall', 'macaulay', 'carlyle',
        'burke', 'paine', 'wollstonecraft',
    ]
}

def is_prose_text(text_id, language='la'):
    """
    Determine if a text is prose (not suitable for metrical analysis).
    Returns True if prose, False if poetry.
    Checks prose markers first to handle naming conflicts (e.g., Apuleius's Metamorphoses vs Ovid's).
    Defaults to True (prose) for unknown texts to avoid false positives.
    """
    text_lower = text_id.lower()
    
    prose_markers = PROSE_WORKS.get(language, [])
    for marker in prose_markers:
        if marker in text_lower:
            return True
    
    poetry_markers = POETRY_WORKS.get(language, [])
    for marker in poetry_markers:
        if marker in text_lower:
            return False
    
    return True

def is_suitable_for_meter(source_id, target_id, language='la'):
    """
    Check if both source and target texts are suitable for metrical analysis.
    Returns True only if both are Latin poetry (Greek scanning not yet implemented).
    """
    if language != 'la':
        return False
    
    source_prose = is_prose_text(source_id, language)
    target_prose = is_prose_text(target_id, language)
    
    return not source_prose and not target_prose
