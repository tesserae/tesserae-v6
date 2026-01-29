#!/usr/bin/env python3
"""Download English texts from Tesserae using direct URLs."""
import os
import requests
import time

RAW_BASE = "https://raw.githubusercontent.com/tesserae/tesserae/master/texts/en"

ENGLISH_TEXTS = [
    "browning.sonnets_from_the_portuguese.tess",
    "carroll.alice_in_wonderland.tess",
    "cowper.task.tess",
    "milton.paradise_lost.tess",
    "shakespeare.a_midsummer_night's_dream.tess",
    "shakespeare.hamlet.tess",
    "shakespeare.richard_iii.tess",
    "shakespeare.sonnets.tess",
    "swift.gullivers_travels.tess",
    "wordsworth.prelude.tess",
    "world_english_bible.pentateuch.tess",
    "world_english_bible.prophets.tess",
    "world_english_bible.revelation.tess",
    "world_english_bible.writings.tess",
]

def download_file(url, local_path):
    """Download a file from URL to local path."""
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            return True
        else:
            print(f"  Failed: {response.status_code}")
    except Exception as e:
        print(f"  Error: {e}")
    return False

def main():
    texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'en')
    os.makedirs(texts_dir, exist_ok=True)
    
    downloaded = 0
    skipped = 0
    failed = 0
    
    print(f"Downloading {len(ENGLISH_TEXTS)} English texts...")
    
    for i, filename in enumerate(ENGLISH_TEXTS):
        local_path = os.path.join(texts_dir, filename)
        
        if os.path.exists(local_path):
            skipped += 1
            print(f"  [{i+1}/{len(ENGLISH_TEXTS)}] Skipped {filename} (exists)")
            continue
        
        url = f"{RAW_BASE}/{filename}"
        print(f"  [{i+1}/{len(ENGLISH_TEXTS)}] Downloading {filename}...")
        
        if download_file(url, local_path):
            downloaded += 1
        else:
            failed += 1
        
        time.sleep(0.1)
    
    print(f"\n=== Complete ===")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (existing): {skipped}")
    print(f"Failed: {failed}")
    print(f"Total English texts now: {len([f for f in os.listdir(texts_dir) if f.endswith('.tess')])}")

if __name__ == "__main__":
    main()
