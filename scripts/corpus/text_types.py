#!/usr/bin/env python3
"""The prose/poetry table, data/text_types.json: one reviewed label per text.

detect_text_type (backend/utils.py) reads this table. The cascade (name markers,
median line length, language default) only proposes a value for a text that has
no entry yet. Procedure: docs/DATA_OPERATIONS.md, "Adding a text".

Commands:
  fill   add an entry, with the cascade's proposal and its source, for every file
         under texts/<lang>/ that has none. Never changes an existing entry.
  check  exit 1 and list every file with no entry and every entry whose file is gone.
  diff   compare every entry with what the cascade says today and with
         text_metadata_overrides.json. Prints differences, changes nothing.

Options: --table PATH, --texts DIR (default texts/ in the repository),
--extra-texts DIR (used for a language folder that --texts lacks, e.g. the
untracked ar, fa and ur folders on a checkout that has only the committed texts).
"""
import argparse
import datetime
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

DEFAULT_TABLE = os.path.join(REPO, 'data', 'text_types.json')
DEFAULT_TEXTS = os.path.join(REPO, 'texts')
DESCRIPTION = ('The prose or poetry label of every text, one entry per .tess file. '
               'detect_text_type reads this table. "source" says where the first value came from: '
               'override, marker, line_length, default, or reviewed (a person set it). '
               'The name markers and median line length only propose a value for a new text '
               '(scripts/corpus/text_types.py fill).')


def list_files(texts, extra=None):
    """{lang: {filename: path}} for every .tess file; extra fills in language folders texts lacks."""
    found = {}
    for root in (texts, extra):
        if not root or not os.path.isdir(root):
            continue
        for lang in sorted(os.listdir(root)):
            d = os.path.join(root, lang)
            if not os.path.isdir(d) or lang in found:
                continue
            found[lang] = {fn: os.path.join(d, fn) for fn in sorted(os.listdir(d)) if fn.endswith('.tess')}
    return found


def load_table(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith('_')}


def save_table(path, table):
    out = {'_description': DESCRIPTION, '_last_updated': datetime.date.today().isoformat()}
    for lang in sorted(table):
        out[lang] = {fn: table[lang][fn] for fn in sorted(table[lang])}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write('\n')


def fill(table_path, texts, extra=None):
    from backend.utils import propose_text_type
    table = load_table(table_path)
    added = []
    for lang, files in list_files(texts, extra).items():
        entries = table.setdefault(lang, {})
        for fn, path in files.items():
            if fn in entries:
                continue
            label, source = propose_text_type(fn, filepath=path, language=lang)
            entries[fn] = {'text_type': label, 'source': source}
            added.append((lang, fn, label, source))
    if added:
        save_table(table_path, table)
    for lang, fn, label, source in added:
        print(f'added {lang}/{fn}: {label} ({source})')
    print(f'{len(added)} entries added; table at {table_path}')
    return 0


def check(table_path, texts, extra=None):
    table = load_table(table_path)
    files = list_files(texts, extra)
    missing, stale, skipped = [], [], []
    for lang, fns in files.items():
        for fn in fns:
            if fn not in table.get(lang, {}):
                missing.append(f'{lang}/{fn}')
    for lang, entries in table.items():
        if lang not in files:
            skipped.append(lang)
            continue
        for fn in entries:
            if fn not in files[lang]:
                stale.append(f'{lang}/{fn}')
    for name in missing:
        print(f'no entry: {name}')
    for name in stale:
        print(f'entry without a file: {name}')
    for lang in skipped:
        print(f'(language folder texts/{lang} not present here; its {len(table[lang])} entries not checked)')
    if missing or stale:
        print(f'FAIL: {len(missing)} files without an entry, {len(stale)} entries without a file')
        return 1
    print('ok: the table and the texts folder agree')
    return 0


def diff(table_path, texts, extra=None):
    from backend.utils import propose_text_type, load_metadata_overrides
    table = load_table(table_path)
    files = list_files(texts, extra)
    overrides = load_metadata_overrides(force_reload=True)
    n = 0
    for lang, entries in sorted(table.items()):
        for fn, entry in sorted(entries.items()):
            label = entry.get('text_type')
            path = files.get(lang, {}).get(fn)
            if path is None and lang in files:
                continue
            proposed = propose_text_type(fn, filepath=path, language=lang)[0] if path or lang not in files else None
            if proposed is not None and proposed != label:
                print(f'{lang}/{fn}: table {label} ({entry.get("source")}), cascade {proposed}')
                n += 1
            ov = overrides.get(fn, {}).get('text_type')
            if ov is not None and ov != label:
                print(f'{lang}/{fn}: table {label} ({entry.get("source")}), override {ov}')
                n += 1
    print(f'{n} differences')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['fill', 'check', 'diff'])
    ap.add_argument('--table', default=DEFAULT_TABLE)
    ap.add_argument('--texts', default=DEFAULT_TEXTS)
    ap.add_argument('--extra-texts', default=None)
    a = ap.parse_args(argv)
    return {'fill': fill, 'check': check, 'diff': diff}[a.command](a.table, a.texts, a.extra_texts)


if __name__ == '__main__':
    sys.exit(main())
