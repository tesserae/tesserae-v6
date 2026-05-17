#!/usr/bin/env python3
"""
Convert Iqbal's complete works from YAML dataset to Tesserae .tess format.

Source: https://github.com/AzeemGhumman/iqbal-demystified-dataset
Data at: /tmp/urdu_iqbal/data/poems/

Each YAML file is one poem with couplets (sher) containing Urdu, English,
and Roman transliteration. We extract the Urdu text.

Output: texts/ur/iqbal.{book_name}.tess (one file per book)
"""

import os
import re
import sys
import yaml
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IQBAL_DIR = '/tmp/urdu_iqbal/data'
TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'ur')

# Book ID -> (English name, short name for filename)
BOOK_NAMES = {
    '001': ('Bang-e-Dra', 'bang_e_dra'),
    '002': ('Bal-e-Jibril', 'bal_e_jibril'),
    '003': ('Zarb-e-Kaleem', 'zarb_e_kaleem'),
    '004': ('Armaghan-e-Hijaz (Urdu)', 'armaghan_e_hijaz_urdu'),
    '005': ('Asrar-e-Khudi', 'asrar_e_khudi'),
    '006': ('Rumuz-e-Bekhudi', 'rumuz_e_bekhudi'),
    '007': ('Payam-e-Mashriq', 'payam_e_mashriq'),
    '008': ('Zabur-e-Ajam', 'zabur_e_ajam'),
    '009': ('Javid Nama', 'javid_nama'),
    '010': ('Pas Cheh Bayad Kard', 'pas_cheh_bayad_kard'),
    '011': ('Armaghan-e-Hijaz (Persian)', 'armaghan_e_hijaz_persian'),
}


def main():
    os.makedirs(TEXTS_DIR, exist_ok=True)
    poems_dir = os.path.join(IQBAL_DIR, 'poems')

    total_lines = 0
    total_poems = 0

    for book_id, (book_title, book_short) in BOOK_NAMES.items():
        book_dir = os.path.join(poems_dir, book_id)
        if not os.path.isdir(book_dir):
            print(f"  SKIP: {book_title} (dir {book_id} not found)")
            continue

        yaml_files = sorted(Path(book_dir).glob('*.yaml'))
        if not yaml_files:
            print(f"  SKIP: {book_title} (no YAML files)")
            continue

        lines = []
        poem_count = 0

        for yf in yaml_files:
            try:
                with open(yf, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            except Exception as e:
                continue

            if not data or 'sher' not in data:
                continue

            poem_id = data.get('id', yf.stem)
            poem_count += 1

            # Get poem heading in Urdu
            heading_ur = ''
            for h in data.get('heading', []):
                if h.get('lang') == 'ur':
                    heading_ur = h.get('text', '')
                    break

            couplet_num = 0
            for sher in data['sher']:
                if sher.get('meta', False):
                    continue  # skip metadata entries

                # Get Urdu text
                urdu_text = ''
                for sc in sher.get('sherContent', []):
                    if sc.get('lang') == 'ur':
                        urdu_text = sc.get('text', '')
                        break

                if not urdu_text or not urdu_text.strip():
                    continue

                couplet_num += 1
                # Classical Urdu couplets often have two hemistichs separated by |
                # or are on a single line. Keep as-is for .tess.
                urdu_text = urdu_text.strip()
                ref = f'<iqbal.{book_short}.{poem_count}.{couplet_num}>'
                lines.append(f'{ref}\t{urdu_text}')

        if not lines:
            print(f"  SKIP: {book_title} (no Urdu text found)")
            continue

        filename = f'iqbal.{book_short}.tess'
        filepath = os.path.join(TEXTS_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

        print(f"  {book_title}: {poem_count} poems, {len(lines)} couplets -> {filename}")
        total_lines += len(lines)
        total_poems += poem_count

    print(f"\nTotal: {total_poems} poems, {total_lines} couplets across {len(BOOK_NAMES)} books")
    print(f"Texts directory: {TEXTS_DIR}")


if __name__ == '__main__':
    main()
