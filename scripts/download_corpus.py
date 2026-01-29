#!/usr/bin/env python3
"""Download Tesserae text corpus from GitHub."""
import os
import requests
import time

GITHUB_API = "https://api.github.com/repos/tesserae/tesserae/contents/texts"
RAW_BASE = "https://raw.githubusercontent.com/tesserae/tesserae/master/texts"

def get_directory_contents(path):
    """Get contents of a GitHub directory."""
    url = f"{GITHUB_API}/{path}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return []

def download_file(url, local_path):
    """Download a file from URL to local path."""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return False

def download_language(lang, local_dir):
    """Download all texts for a language."""
    print(f"\n=== Downloading {lang} texts ===")
    os.makedirs(local_dir, exist_ok=True)
    
    contents = get_directory_contents(lang)
    downloaded = 0
    skipped = 0
    
    for item in contents:
        name = item['name']
        item_type = item['type']
        
        if item_type == 'file' and name.endswith('.tess'):
            local_path = os.path.join(local_dir, name)
            if os.path.exists(local_path):
                skipped += 1
                continue
            url = item['download_url']
            print(f"  Downloading {name}...")
            if download_file(url, local_path):
                downloaded += 1
            time.sleep(0.1)
            
        elif item_type == 'dir':
            subdir_contents = get_directory_contents(f"{lang}/{name}")
            for subitem in subdir_contents:
                if subitem['type'] == 'file' and subitem['name'].endswith('.tess'):
                    local_path = os.path.join(local_dir, subitem['name'])
                    if os.path.exists(local_path):
                        skipped += 1
                        continue
                    url = subitem['download_url']
                    print(f"  Downloading {subitem['name']}...")
                    if download_file(url, local_path):
                        downloaded += 1
                    time.sleep(0.1)
    
    print(f"  Downloaded: {downloaded}, Skipped (existing): {skipped}")
    return downloaded

def main():
    texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')
    
    la_count = download_language('la', os.path.join(texts_dir, 'la'))
    grc_count = download_language('grc', os.path.join(texts_dir, 'grc'))
    
    print(f"\n=== Complete ===")
    print(f"Latin texts: {la_count}")
    print(f"Greek texts: {grc_count}")

if __name__ == "__main__":
    main()
