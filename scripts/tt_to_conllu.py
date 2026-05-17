#!/usr/bin/env python3
"""Convert Coptic Scriptorium TT (TreeTagger XML) files to CoNLL-U.

Coptic Scriptorium publishes the full Sahidic NT only in TT format — the
upstream sahidica.nt_CONLLU dir contains 2-byte stubs for all books except
Mark and 1 Corinthians. The TT files contain the same UD annotations
(lemmas, POS, head, deprel) as the CoNLL-U format, just wrapped in XML
markup that can have OVERLAPPING (non-tree) tags — `<entity>` regions
routinely cross `<norm_group>` boundaries — so a strict XML parser fails.

This module uses a regex-based scanner that only cares about the
elements relevant to syntax/lemma extraction:

  - <verse_n verse_n="N" ...>     verse boundary (1 sentence per verse)
  - <orig_group orig_group="X">   bound-group boundary (Mark-style)
  - <norm_group ... orig_group=X norm_group=Y>  Matthew-style: orig_group
                                  attr serves the same role; if no
                                  separate <orig_group> element is
                                  currently open, this opens an implicit
                                  bound group with text=X.
  - <norm xml:id pos lemma func head norm new_sent ...>   the actual
                                  word-level tokens.

Each <verse_n> block becomes one CoNLL-U sentence so downstream
processing emits one .tess line per verse, matching the existing
sahidica.mark / sahidica.1corinthians conventions.

Usage:
    python scripts/tt_to_conllu.py <tt_dir> <out_conllu_dir>
"""

import os
import re
import sys
from pathlib import Path


XPOS_TO_UPOS = {
    'N': 'NOUN', 'NPROP': 'PROPN', 'V': 'VERB', 'VBD': 'VERB',
    'VIMP': 'VERB', 'VSTAT': 'VERB', 'VBE': 'VERB',
    'ART': 'DET', 'PPOS': 'DET',
    'PPERS': 'PRON', 'PPERO': 'PRON', 'PDEM': 'PRON', 'PINT': 'PRON',
    'PREP': 'ADP', 'PTC': 'PART', 'NEG': 'PART',
    'CONJ': 'SCONJ', 'CCONJ': 'CCONJ', 'CREL': 'SCONJ',
    'CPRET': 'AUX', 'CCIRC': 'AUX', 'CFOC': 'AUX', 'CFUT': 'AUX',
    'APST': 'AUX', 'AOPT': 'AUX', 'ANEG': 'AUX', 'ACOND': 'AUX',
    'EXIST': 'VERB', 'NUM': 'NUM',
    'ADV': 'ADV', 'ADJ': 'ADJ', 'ANY': 'X',
    'PUNCT': 'PUNCT', 'INTJ': 'INTJ', 'IMOD': 'AUX',
    'UNKNOWN_FUNC': 'X', 'FM': 'X',
}


def xpos_to_upos(xpos):
    return XPOS_TO_UPOS.get(xpos, 'X')


# Match any element tag at the start of a line; group(1) is element name,
# group(2) is the attribute string, group(3) is '/' if it's a self-close.
TAG_RE = re.compile(r'^<(/?)([a-zA-Z_][\w:]*)\b([^>]*?)(/?)>$')

# Generic attr matcher (handles both attr="x" and attr='x').
ATTR_RE = re.compile(r"""([\w:]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def parse_attrs(attr_str):
    return {m.group(1): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in ATTR_RE.finditer(attr_str)}


def parse_tt(tt_path):
    """Return list of verse dicts. Tolerates overlapping XML elements."""
    verses = []
    cur_verse = None
    cur_orig_group = None       # dict with 'text' and 'tokens'
    in_orig_group_element = False  # True if a literal <orig_group> tag is open

    with open(tt_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    # The TT files put each tag on its own line. Walk line by line.
    for raw_line in raw.split('\n'):
        line = raw_line.strip()
        if not line or not line.startswith('<'):
            continue
        m = TAG_RE.match(line)
        if not m:
            continue
        is_close = (m.group(1) == '/')
        name = m.group(2)
        attrs = parse_attrs(m.group(3) or '')

        if name == 'verse_n':
            if not is_close:
                cur_verse = {
                    'verse_n': attrs.get('verse_n', ''),
                    'orig_groups': [],
                }
            else:
                if cur_verse is not None:
                    verses.append(cur_verse)
                cur_verse = None
                cur_orig_group = None
                in_orig_group_element = False

        elif name == 'orig_group':
            if not is_close:
                # Only relevant inside a verse
                if cur_verse is not None:
                    cur_orig_group = {
                        'text': attrs.get('orig_group', ''),
                        'tokens': [],
                    }
                    in_orig_group_element = True
            else:
                if cur_verse is not None and cur_orig_group is not None:
                    cur_verse['orig_groups'].append(cur_orig_group)
                cur_orig_group = None
                in_orig_group_element = False

        elif name == 'norm_group':
            if not is_close:
                # In Matthew-style files there is no <orig_group> wrapper —
                # norm_group itself carries orig_group="X". Open an implicit
                # bound group in that case.
                if cur_verse is not None and not in_orig_group_element:
                    cur_orig_group = {
                        'text': attrs.get('orig_group', '') or attrs.get('norm_group', ''),
                        'tokens': [],
                    }
            else:
                # Close the implicit bound group (if we opened one).
                if cur_verse is not None and not in_orig_group_element and cur_orig_group is not None:
                    cur_verse['orig_groups'].append(cur_orig_group)
                    cur_orig_group = None

        elif name == 'norm':
            if is_close:
                continue
            if cur_verse is None or cur_orig_group is None:
                continue
            cur_orig_group['tokens'].append({
                'xml_id': attrs.get('xml:id') or attrs.get('xmlid', ''),
                'form': attrs.get('norm', ''),
                'lemma': attrs.get('lemma', ''),
                'xpos': attrs.get('pos', ''),
                'func': attrs.get('func', '_'),
                'head_id': (attrs.get('head', '') or '').lstrip('#'),
                'new_sent': attrs.get('new_sent', '') == 'true',
                'misc_lang': attrs.get('lang', ''),
            })

    # Some files don't close the final verse (file ends inside it).
    if cur_verse is not None:
        if cur_orig_group is not None and cur_orig_group not in cur_verse['orig_groups']:
            cur_verse['orig_groups'].append(cur_orig_group)
        verses.append(cur_verse)

    return verses


def write_conllu(verses, out_path, doc_id):
    """Emit a CoNLL-U file for one chapter. One sentence per verse."""
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# newdoc id = {doc_id}\n")
        for verse in verses:
            verse_n = verse['verse_n']
            tokens = []
            xml_id_to_local = {}
            mwts = []  # (start_local, end_local, surface_text)

            local_idx = 0
            for og in verse['orig_groups']:
                if not og['tokens']:
                    continue
                start = local_idx + 1
                for tok in og['tokens']:
                    local_idx += 1
                    if tok['xml_id']:
                        xml_id_to_local[tok['xml_id']] = local_idx
                    tokens.append(tok)
                end = local_idx
                if end > start:
                    mwts.append((start, end, og['text']))
                elif end == start and og['text'] and og['text'] != tokens[-1]['form']:
                    mwts.append((start, end, og['text']))

            if not tokens:
                continue

            display_text = ' '.join(og['text'] for og in verse['orig_groups'] if og['text'])

            sent_id = f"{doc_id}_v{verse_n}"
            f.write(f"# sent_id = {sent_id}\n")
            f.write(f"# verse_n = {verse_n}\n")
            f.write(f"# text = {display_text}\n")

            mwt_at_start = {s: (e, txt) for (s, e, txt) in mwts}

            for i, tok in enumerate(tokens, 1):
                if i in mwt_at_start:
                    e, txt = mwt_at_start[i]
                    f.write(f"{i}-{e}\t{txt}\t_\t_\t_\t_\t_\t_\t_\t_\n")

                form = tok['form'] or '_'
                lemma = tok['lemma'] or form
                xpos = tok['xpos'] or '_'
                upos = xpos_to_upos(xpos)
                head_xml = tok.get('head_id', '')
                head_local = xml_id_to_local.get(head_xml, 0) if head_xml else 0
                deprel = tok['func'] or 'dep'
                if head_local == 0 and deprel != 'root':
                    deprel = 'root'

                misc = '_'
                if tok.get('misc_lang'):
                    misc = f"OrigLang={tok['misc_lang']}"

                f.write(f"{i}\t{form}\t{lemma}\t{upos}\t{xpos}\t_\t{head_local}\t{deprel}\t_\t{misc}\n")
            f.write("\n")


def main():
    if len(sys.argv) != 3:
        print("Usage: python tt_to_conllu.py <tt_dir> <out_conllu_dir>", file=sys.stderr)
        sys.exit(1)

    tt_dir = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    tt_files = sorted(Path(tt_dir).glob('*.tt'))
    print(f"Converting {len(tt_files)} TT files from {tt_dir}")
    print(f"  -> {out_dir}")

    total_verses = 0
    empty = 0
    for i, tt_file in enumerate(tt_files, 1):
        verses = parse_tt(str(tt_file))
        doc_id = tt_file.stem
        out_path = os.path.join(out_dir, doc_id + '.conllu')
        write_conllu(verses, out_path, doc_id)
        total_verses += len(verses)
        if not verses:
            empty += 1
        if i % 25 == 0 or i == len(tt_files):
            print(f"  [{i}/{len(tt_files)}] {tt_file.name}: {len(verses)} verses (cum {total_verses})")

    print(f"\nDone. {len(tt_files)} files, {total_verses} verses, {empty} empty.")


if __name__ == '__main__':
    main()
