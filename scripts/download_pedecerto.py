#!/usr/bin/env python3
"""
Download Latin poetry texts with scansion from Pede Certo (pedecerto.eu)
Part of the MQDQ (Musisque Deoque) digital archive
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.pedecerto.eu"
DATA_DIR = "data/pedecerto"

MAJOR_AUTHORS = {
    "Vergilius": 78,
    "Lucanus": 119,
    "Ouidius": 94,
    "Horatius": 84,
    "Statius": 124,
    "Lucretius": 59,
    "Catullus": 67,
    "Tibullus": 87,
    "Propertius": 86,
    "Iuuenalis": 131,
    "Silius_Italicus": 125,
    "Valerius_Flaccus": 123,
    "Martialis": 130,
    "Seneca": 112,
    "Persius": 117,
    "Claudianus": 186,
    "Manilius": 104,
    "Calpurnius_Siculus": 115,
    "Petronius": 120,
    "Columella": 111,
    "Iuuencus": 171,
}

def get_works_for_author(author_id):
    """Get list of works for an author with their IDs."""
    url = f"{BASE_URL}/pagine/autori/idautori/{author_id}"
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        
        works = {}
        pattern = r"javascript:download\((\d+)\)\"[^>]*>([^<]+)</a>"
        for match in re.finditer(pattern, resp.text):
            work_id = int(match.group(1))
            work_name = match.group(2).strip()
            if work_name and not work_name.startswith("*"):
                works[work_name] = work_id
        
        return works
    except Exception as e:
        print(f"Error getting works for author {author_id}: {e}")
        return {}

def download_work(work_id, author_name, work_name):
    """Download a work's XML file from Pede Certo."""
    url = f"{BASE_URL}/pagine/download/idopere/{work_id}"
    safe_work_name = re.sub(r'[^\w\-]', '_', work_name)
    safe_author_name = re.sub(r'[^\w\-]', '_', author_name)
    
    author_dir = os.path.join(DATA_DIR, safe_author_name)
    os.makedirs(author_dir, exist_ok=True)
    
    filename = os.path.join(author_dir, f"{safe_work_name}.xml")
    
    if os.path.exists(filename):
        print(f"  Already exists: {filename}")
        return True
    
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(resp.content)
        
        print(f"  Downloaded: {filename}")
        return True
    except Exception as e:
        print(f"  Error downloading {work_name}: {e}")
        return False

def download_all():
    """Download all major authors' works."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    total_works = 0
    
    for author_name, author_id in MAJOR_AUTHORS.items():
        print(f"\n{author_name} (ID: {author_id}):")
        
        works = get_works_for_author(author_id)
        print(f"  Found {len(works)} works")
        
        for work_name, work_id in works.items():
            success = download_work(work_id, author_name, work_name)
            if success:
                total_works += 1
            time.sleep(0.5)
    
    print(f"\n\nTotal works downloaded: {total_works}")

if __name__ == "__main__":
    download_all()
