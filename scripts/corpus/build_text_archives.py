#!/usr/bin/env python3
"""Build one static archive of corpus texts per language, with a manifest.

For each language folder under texts/ this writes, into the output folder:

  texts_<lang>.tar.gz            every .tess file except the restricted ones
                                 (backend/restricted_texts.py decides) and those
                                 from sources whose terms allow no online copy
                                 (WITHHELD_SOURCES below), plus
                                 MANIFEST.tsv and README.txt inside
  texts_<lang>_manifest.tsv      the same manifest, beside the archive

The manifest has one row per file: file name, author, work, lines, electronic
source and its URL, print source, license, whether the license limits use to
noncommercial, and the date of the archive. A file is matched to its credit row
in backend/text_sources.json the way scripts/corpus/verify_text_coverage.py
matches it: author and work, casefolded, exact first, then the same author with
one work name starting the other. A file with no row gets "unknown" and is
counted. A row that names no license gets "not stated in the credit row".

Each archive is written under a .new name and renamed over the old one.

Usage:
  python scripts/corpus/build_text_archives.py --out ~/tesserae-backups/text_archives_DATE
  python scripts/corpus/build_text_archives.py --out DIR --language la --language grc
  python scripts/corpus/build_text_archives.py --out DIR --texts-root /path/to/texts

On production the output folder is public_data/ (served at /tesserae-data/).
"""
import argparse
import csv
import datetime
import io
import json
import os
import re
import sys
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from backend import fspaths, restricted_texts, utils  # noqa: E402

COLUMNS = ['file', 'author', 'work', 'lines', 'electronic_source', 'electronic_source_url',
           'print_source', 'license', 'noncommercial_only', 'archive_date']
UNKNOWN = 'unknown'
NOT_STATED = 'not stated in the credit row'
NONCOMMERCIAL = re.compile(
    r'\bBY-NC|non-?commercial|academic use only|for academic use|research use only', re.I)
# Sources whose stated terms do not allow an online copy of their texts. The
# files stay on the site (search, Reader, Similar Passages) and out of the bulk
# archives. Matched on the credit row's e_source or e_source_url. Read on
# 2026-10-25: Musisque Deoque allows reproduction on paper or on portable
# offline media only, for scholarly use; Corpus Thomisticum and augustinus.it
# reserve all rights.
WITHHELD_SOURCES = [
    ('Musisque Deoque', re.compile(r'musisque|mqdq|musa medievalis|musamedievalis', re.I),
     'copies allowed on paper or portable offline media only'),
    ('Corpus Thomisticum', re.compile(r'thomisticum', re.I), 'all rights reserved'),
    ('augustinus.it', re.compile(r'augustinus\.it', re.I), 'all rights reserved'),
]


def withheld_reason(src):
    """The source name and reason when a credit row's source bars online copies, else None."""
    if not src:
        return None
    text = ' '.join(str(src.get(k) or '') for k in ('e_source', 'e_source_url'))
    for name, pat, why in WITHHELD_SOURCES:
        if pat.search(text):
            return f'{name} ({why})'
    return None
LINE = re.compile(r'<[^>]+>')

README = """Tesserae corpus texts: {name} ({lang})
Archive date: {date}
Files: {n}

What these files are
Each .tess file is one text, or one book of a text, in the Tesserae line
format: one line per reference, written as a reference in angle brackets,
a tab, and the line of text, for example

  <verg. aen. 1.1>\\tArma virumque cano, Troiae qui primus ab oris

MANIFEST.tsv lists every file with its author, work, number of lines,
electronic source and its address, print source, and license.

Licenses
Each text carries the license named in its row of the manifest. Where the row
says "not stated in the credit row", the text comes from the edition named in
that row, and its terms are those of that source. {nc_line}
{unknown_line}
Texts held under an indexing-only license are not in this archive.
{withheld_line}

Where to read more
The Sources page of the Tesserae site names every edition and its license, and
the Terms page states the conditions of use for bulk copies:
https://tesserae.caset.buffalo.edu/ (open Sources and Terms from the footer).
"""


def load_sources(root):
    with open(os.path.join(root, 'backend', 'text_sources.json'), encoding='utf-8') as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else data.get('entries', [])


def _key(s):
    return (s or '').strip().casefold()


class SourceIndex:
    """Credit rows, matched to a file by author and work."""

    def __init__(self, rows):
        self.exact = {}
        self.by_author = {}
        for r in rows:
            a, w = _key(r.get('author')), _key(r.get('work'))
            self.exact.setdefault((a, w), r)
            self.by_author.setdefault(a, []).append((w, r))

    def find(self, author, work):
        a, w = _key(author), _key(work)
        hit = self.exact.get((a, w))
        if hit:
            return hit
        if a and w:
            for sw, r in self.by_author.get(a, []):
                if sw and (sw.startswith(w) or w.startswith(sw)):
                    return r
        return None


def count_lines(path):
    n = 0
    with open(fspaths.fs_path(path), encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if line.startswith('<') and LINE.match(line):
                n += 1
    return n


def manifest_row(path, filename, index, date):
    md = utils.get_text_metadata(path)
    author, work = md.get('author', ''), md.get('work', '')
    src = index.find(author, work)
    withheld = withheld_reason(src)
    if src is None:
        lic, nc = UNKNOWN, ''
        e_src = e_url = printed = UNKNOWN
        matched = False
    else:
        lic = (src.get('license') or '').strip() or NOT_STATED
        nc = 'yes' if NONCOMMERCIAL.search(lic) else 'no'
        e_src = (src.get('e_source') or '').strip()
        e_url = (src.get('e_source_url') or '').strip()
        printed = (src.get('print_source') or '').strip()
        matched = True
    row = {'file': filename, 'author': author, 'work': work, 'lines': count_lines(path),
           'electronic_source': e_src, 'electronic_source_url': e_url, 'print_source': printed,
           'license': lic, 'noncommercial_only': nc, 'archive_date': date}
    return row, matched, withheld


def _clean(v):
    return re.sub(r'[\t\r\n]+', ' ', str(v))


def manifest_bytes(rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter='\t', lineterminator='\n')
    w.writerow(COLUMNS)
    for r in rows:
        w.writerow([_clean(r[c]) for c in COLUMNS])
    return buf.getvalue().encode('utf-8')


def build_language(lang, texts_root, out_dir, index, date, names):
    """Write the archive and manifest for one language. Returns its counts."""
    lang_dir = os.path.join(texts_root, lang)
    files = sorted(f for f in fspaths.listdir_text(lang_dir) if f.endswith('.tess'))
    restricted = {f for f in files if restricted_texts.is_restricted(f)}
    rows, unknown, noncommercial, not_stated = [], 0, 0, 0
    kept, withheld = [], {}
    for f in files:
        if f in restricted:
            continue
        row, matched, why = manifest_row(os.path.join(lang_dir, f), f, index, date)
        if why:
            withheld[f] = why
            continue
        rows.append(row)
        kept.append(f)
        unknown += 0 if matched else 1
        noncommercial += 1 if row['noncommercial_only'] == 'yes' else 0
        not_stated += 1 if row['license'] == NOT_STATED else 0
    manifest = manifest_bytes(rows)
    nc_line = (f'{noncommercial} text(s) are licensed for noncommercial use only, and the manifest '
               'marks them "yes" in the noncommercial_only column; use them only so.'
               if noncommercial else
               'No text in this archive is marked noncommercial-only in the manifest.')
    unknown_line = (f'{unknown} file(s) have no credit row yet and read "unknown" in the manifest; '
                    'ask through Suggest a change on the site before reusing them.'
                    if unknown else '')
    by_source = {}
    for why in withheld.values():
        by_source[why] = by_source.get(why, 0) + 1
    withheld_line = (f'{len(withheld)} text(s) are not in this archive because their source allows no '
                     'online copy: ' + '; '.join(f'{n} from {src}' for src, n in sorted(by_source.items()))
                     + '. They can be read and searched on the site.'
                     if withheld else '')
    readme = README.format(name=names.get(lang, lang), lang=lang, date=date, n=len(kept),
                           nc_line=nc_line, unknown_line=unknown_line,
                           withheld_line=withheld_line).encode('utf-8')

    os.makedirs(out_dir, exist_ok=True)
    arc = os.path.join(out_dir, f'texts_{lang}.tar.gz')
    man = os.path.join(out_dir, f'texts_{lang}_manifest.tsv')
    top = f'texts_{lang}'
    mtime = int(time.time())

    def add_bytes(tf, name, data):
        ti = tarfile.TarInfo(f'{top}/{name}')
        ti.size, ti.mtime, ti.mode = len(data), mtime, 0o644
        tf.addfile(ti, io.BytesIO(data))

    with tarfile.open(arc + '.new', 'w:gz') as tf:
        add_bytes(tf, 'README.txt', readme)
        add_bytes(tf, 'MANIFEST.tsv', manifest)
        for f in kept:
            tf.add(fspaths.fs_path(os.path.join(lang_dir, f)), arcname=f'{top}/{f}')
    with open(man + '.new', 'wb') as fh:
        fh.write(manifest)
    os.replace(arc + '.new', arc)
    os.replace(man + '.new', man)
    return {'language': lang, 'files': len(kept), 'restricted': len(restricted),
            'withheld_by_terms': len(withheld), 'withheld_sources': by_source,
            'no_credit_row': unknown, 'noncommercial': noncommercial,
            'license_not_stated': not_stated,
            'archive_bytes': os.path.getsize(arc), 'manifest_bytes': os.path.getsize(man)}


LANGUAGE_NAMES = {'la': 'Latin', 'grc': 'Greek', 'en': 'English', 'cop': 'Coptic', 'he': 'Hebrew',
                  'fa': 'Persian', 'ur': 'Urdu', 'ar': 'Arabic', 'fro': 'Old French',
                  'gmh': 'Middle High German', 'it': 'Italian'}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True, help='folder to write the archives into')
    ap.add_argument('--texts-root', default=os.path.join(ROOT, 'texts'))
    ap.add_argument('--language', '-l', action='append', help='repeatable; default every folder present')
    ap.add_argument('--date', default=datetime.date.today().isoformat())
    a = ap.parse_args(argv)
    texts_root = os.path.abspath(a.texts_root)
    langs = a.language or sorted(d for d in os.listdir(texts_root)
                                 if os.path.isdir(os.path.join(texts_root, d)))
    index = SourceIndex(load_sources(ROOT))
    results = []
    t0 = time.time()
    for lang in langs:
        t1 = time.time()
        r = build_language(lang, texts_root, os.path.abspath(a.out), index, a.date, LANGUAGE_NAMES)
        r['seconds'] = round(time.time() - t1, 1)
        results.append(r)
        print(f"{lang}: {r['files']} files, {r['restricted']} restricted left out, "
              f"{r['withheld_by_terms']} withheld by their source's terms, "
              f"{r['no_credit_row']} without a credit row, {r['noncommercial']} noncommercial-only, "
              f"{r['archive_bytes'] / 1e6:.1f} MB, {r['seconds']} s", flush=True)
    print(f'total {sum(r["archive_bytes"] for r in results) / 1e6:.1f} MB in {time.time() - t0:.1f} s')
    return results


if __name__ == '__main__':
    main()
