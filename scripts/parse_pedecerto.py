#!/usr/bin/env python3
"""
Parse Pede Certo MQDQ XML files and extract text with scansion.
Converts to .tess format and creates scansion lookup table.
"""
import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import re

DATA_DIR = "data/pedecerto"
OUTPUT_TESS_DIR = "texts/la_mqdq"
OUTPUT_SCANSION_DIR = "data/scansion"

AUTHOR_NAME_MAP = {
    "Vergilius": "Vergil",
    "Lucanus": "Lucan",
    "Ouidius": "Ovid",
    "Horatius": "Horace",
    "Statius": "Statius",
    "Lucretius": "Lucretius",
    "Catullus": "Catullus",
    "Tibullus": "Tibullus",
    "Propertius": "Propertius",
    "Iuuenalis": "Juvenal",
    "Silius_Italicus": "Silius Italicus",
    "Valerius_Flaccus": "Valerius Flaccus",
    "Martialis": "Martial",
    "Seneca": "Seneca",
    "Persius": "Persius",
    "Claudianus": "Claudian",
    "Manilius": "Manilius",
    "Calpurnius_Siculus": "Calpurnius Siculus",
    "Petronius": "Petronius",
    "Columella": "Columella",
    "Iuuencus": "Juvencus",
}

WORK_NAME_MAP = {
    "Aeneis": "Aeneid",
    "eclogae": "Eclogues",
    "georgicon": "Georgics",
    "Pharsalia": "Pharsalia",
    "carminum_fragmenta": "Fragments",
    "metamorphoses": "Metamorphoses",
    "amores_1": "Amores 1",
    "amores_2": "Amores 2",
    "amores_3": "Amores 3",
    "ars": "Ars Amatoria",
    "epistulae_heroides": "Heroides",
    "fasti": "Fasti",
    "tristia_1": "Tristia 1",
    "tristia_2": "Tristia 2",
    "tristia_3": "Tristia 3",
    "tristia_4": "Tristia 4",
    "tristia_5": "Tristia 5",
    "ex_Ponto_1": "Epistulae ex Ponto 1",
    "ex_Ponto_2": "Epistulae ex Ponto 2",
    "ex_Ponto_3": "Epistulae ex Ponto 3",
    "ex_Ponto_4": "Epistulae ex Ponto 4",
    "remedia_amoris": "Remedia Amoris",
    "Ibis": "Ibis",
    "halieutica": "Halieutica",
    "medicamina_faciei": "Medicamina Faciei",
    "de_rerum_natura": "De Rerum Natura",
    "carmina": "Carmina",
    "elegiae_1": "Elegies 1",
    "elegiae_2": "Elegies 2",
    "elegiae_3": "Elegies 3",
    "elegiae_4": "Elegies 4",
    "saturae": "Satires",
    "saturae_1": "Satires 1",
    "saturae_2": "Satires 2",
    "Punica": "Punica",
    "Argonautica": "Argonautica",
    "Thebais": "Thebaid",
    "Achilleis": "Achilleid",
    "siluae_1": "Silvae 1",
    "siluae_2": "Silvae 2",
    "siluae_3": "Silvae 3",
    "siluae_4": "Silvae 4",
    "siluae_5": "Silvae 5",
    "ars_poetica": "Ars Poetica",
    "carmina_1": "Odes 1",
    "carmina_4": "Odes 4",
    "epistulae_1": "Epistles 1",
    "epistulae_2": "Epistles 2",
    "epodi": "Epodes",
    "epigrammata_1": "Epigrams 1",
    "epigrammata_2": "Epigrams 2",
    "epigrammata_3": "Epigrams 3",
    "epigrammata_4": "Epigrams 4",
    "epigrammata_5": "Epigrams 5",
    "epigrammata_6": "Epigrams 6",
    "epigrammata_7": "Epigrams 7",
    "epigrammata_8": "Epigrams 8",
    "epigrammata_9": "Epigrams 9",
    "epigrammata_10": "Epigrams 10",
    "epigrammata_11": "Epigrams 11",
    "epigrammata_12": "Epigrams 12",
    "epigrammata_13": "Xenia",
    "epigrammata_14": "Apophoreta",
    "de_spectaculis": "Liber Spectaculorum",
    "Medea": "Medea",
    "Oedipus": "Oedipus",
    "apocolocyntosis": "Apocolocyntosis",
    "de_raptu_Proserpinae": "De Raptu Proserpinae",
    "in_Rufinum": "In Rufinum",
    "in_Eutropium": "In Eutropium",
    "de_bello_Gothico": "De Bello Gothico",
    "de_bello_Gildonico": "De Bello Gildonico",
    "de_consulatu_Stilichonis": "De Consulatu Stilichonis",
    "carmina_minora": "Carmina Minora",
    "astronomica": "Astronomica",
    "bellum_ciuile": "Bellum Civile",
    "satyricon": "Satyricon",
    "fragmenta": "Fragments",
    "de_re_rustica__liber_X": "De Re Rustica X",
    "euangeliorum_libri": "Evangeliorum Libri",
}

def pattern_to_scansion(pattern, meter_type):
    """Convert foot pattern (e.g., 'DSDS') to scansion symbols.
    
    MQDQ patterns encode feet 1-4 for hexameters (foot 5 is almost always dactyl,
    foot 6 is always – ×). For pentameters, pattern encodes feet 1-2, then 
    the second hemistich follows automatically.
    """
    if not pattern:
        return ""
    symbols = []
    
    if meter_type == 'H':
        # Hexameter: pattern has 4 letters for feet 1-4
        # Foot 5 is almost always dactyl (– ∪ ∪)
        # Foot 6 is always – × (or – – for spondaic ending, but rare)
        for foot in pattern:
            if foot == 'D':
                symbols.extend(['–', '∪', '∪'])
            elif foot == 'S':
                symbols.extend(['–', '–'])
        # Add foot 5 (dactyl) and foot 6 (– ×)
        symbols.extend(['–', '∪', '∪'])  # foot 5
        symbols.extend(['–', '×'])        # foot 6
    elif meter_type == 'E':
        # Elegiac pentameter: pattern has 2 letters for feet 1-2
        # Then: – (caesura) – ∪ ∪ – ∪ ∪ ×
        for foot in pattern:
            if foot == 'D':
                symbols.extend(['–', '∪', '∪'])
            elif foot == 'S':
                symbols.extend(['–', '–'])
        # Add the second hemistich: – | – ∪ ∪ – ∪ ∪ ×
        symbols.extend(['–', '–', '∪', '∪', '–', '∪', '∪', '×'])
    else:
        # Unknown meter, just convert the pattern directly
        for foot in pattern:
            if foot == 'D':
                symbols.extend(['–', '∪', '∪'])
            elif foot == 'S':
                symbols.extend(['–', '–'])
    
    return ''.join(symbols)

def parse_xml_file(xml_path):
    """Parse a Pede Certo XML file and extract lines with scansion."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    head = root.find('head')
    author = head.find('author').text if head.find('author') is not None else "Unknown"
    title = head.find('title').text if head.find('title') is not None else "Unknown"
    
    lines = []
    body = root.find('body')
    
    for division in body.findall('.//division'):
        div_title = division.get('title', '')
        
        for line_elem in division.findall('line'):
            line_name = line_elem.get('name', '')
            meter = line_elem.get('meter', 'H')
            pattern = line_elem.get('pattern', '')
            
            words = []
            word_scansions = []
            has_elision = []
            
            for word_elem in line_elem.findall('word'):
                word_text = word_elem.text or ""
                sy = word_elem.get('sy', '')
                mf = word_elem.get('mf', '')
                
                words.append(word_text)
                word_scansions.append(sy)
                has_elision.append(mf == 'SY')
            
            text = ' '.join(words)
            scansion = pattern_to_scansion(pattern, meter)
            
            lines.append({
                'division': div_title,
                'line': line_name,
                'text': text,
                'meter': meter,
                'pattern': pattern,
                'scansion': scansion,
                'word_scansions': word_scansions,
                'has_elision': has_elision,
            })
    
    return {
        'author': author,
        'title': title,
        'lines': lines,
    }

def generate_tess_tag(author, work, division, line):
    """Generate a .tess format tag matching V3 Tesserae format."""
    author_short = author.lower().replace(' ', '_')[:4]
    work_short = work.lower().replace(' ', '_')[:4]
    
    if division:
        return f"<{author_short}. {work_short}. {division}.{line}>"
    else:
        return f"<{author_short}. {work_short}. {line}>"

def main():
    os.makedirs(OUTPUT_TESS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_SCANSION_DIR, exist_ok=True)
    
    all_scansions = {}
    stats = {
        'authors': set(),
        'works': 0,
        'lines': 0,
        'hexameter': 0,
        'elegiac': 0,
        'other': 0,
    }
    
    for author_dir in sorted(Path(DATA_DIR).iterdir()):
        if not author_dir.is_dir():
            continue
        
        author_name = author_dir.name
        author_display = AUTHOR_NAME_MAP.get(author_name, author_name)
        stats['authors'].add(author_display)
        
        for xml_file in sorted(author_dir.glob('*.xml')):
            print(f"Processing: {author_name}/{xml_file.name}")
            
            try:
                data = parse_xml_file(xml_file)
            except Exception as e:
                print(f"  Error parsing {xml_file}: {e}")
                continue
            
            if not data['lines']:
                print(f"  No lines found in {xml_file.name}")
                continue
            
            work_key = xml_file.stem
            work_display = WORK_NAME_MAP.get(work_key, work_key.replace('_', ' ').title())
            
            tess_filename = f"{author_name.lower()}.{work_key}.tess"
            tess_path = os.path.join(OUTPUT_TESS_DIR, tess_filename)
            
            work_scansions = {}
            
            with open(tess_path, 'w', encoding='utf-8') as f:
                for line_data in data['lines']:
                    tag = generate_tess_tag(
                        author_display, 
                        work_display, 
                        line_data['division'], 
                        line_data['line']
                    )
                    f.write(f"{tag}\t{line_data['text']}\n")
                    
                    locus_key = f"{line_data['division']}.{line_data['line']}" if line_data['division'] else line_data['line']
                    work_scansions[locus_key] = {
                        'pattern': line_data['pattern'],
                        'scansion': line_data['scansion'],
                        'meter': line_data['meter'],
                    }
                    
                    if line_data['meter'] == 'H':
                        stats['hexameter'] += 1
                    elif line_data['meter'] == 'E':
                        stats['elegiac'] += 1
                    else:
                        stats['other'] += 1
                    
                    stats['lines'] += 1
            
            scansion_key = f"{author_name.lower()}.{work_key}"
            all_scansions[scansion_key] = {
                'author': author_display,
                'work': work_display,
                'meter_type': data['lines'][0]['meter'] if data['lines'] else 'H',
                'lines': work_scansions,
            }
            
            stats['works'] += 1
            print(f"  Created: {tess_path} ({len(data['lines'])} lines)")
    
    scansion_path = os.path.join(OUTPUT_SCANSION_DIR, 'mqdq_scansions.json')
    with open(scansion_path, 'w', encoding='utf-8') as f:
        json.dump(all_scansions, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== Summary ===")
    print(f"Authors: {len(stats['authors'])}")
    print(f"Works: {stats['works']}")
    print(f"Lines: {stats['lines']}")
    print(f"  Hexameter: {stats['hexameter']}")
    print(f"  Elegiac: {stats['elegiac']}")
    print(f"  Other: {stats['other']}")
    print(f"\nScansion lookup saved to: {scansion_path}")
    print(f"Tess files saved to: {OUTPUT_TESS_DIR}/")

if __name__ == "__main__":
    main()
