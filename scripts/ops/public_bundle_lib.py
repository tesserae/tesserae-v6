#!/usr/bin/env python3
"""Selection, licence checks, manifest and LICENSES.md for the public data bundle.

scripts/ops/build_public_bundle.sh calls this file; tests/test_public_bundle.py
imports it. Nothing here writes into the production folder. The production
folder (default /var/www/tesseraev6_flask) is read only input.

    python3 -I scripts/ops/public_bundle_lib.py plan --mode core --prod PROD --work WORK
    python3 -I scripts/ops/public_bundle_lib.py measure --mode full --prod PROD

`plan` writes into WORK:
    files.prod.null   NUL-separated paths, relative to PROD, that go into the archive as they are
    stage/            generated or filtered files, relative to the archive root
    MANIFEST.tsv      path, size, sha256, licence source (also copied into stage/)
and prints a summary. `measure` only adds up sizes.

The exclusion rules live in scripts/ops/public_bundle_exclusions.json.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from backend.work_names import base_work  # noqa: E402

EXCLUSIONS_PATH = os.path.join(HERE, 'public_bundle_exclusions.json')
DEFAULT_PROD = '/var/www/tesseraev6_flask'

_HASH_SUFFIX = re.compile(r'-[0-9a-f]{32}$')
_LANG_PREFIX = re.compile(r'^([a-z]{2,3})__')


def load_exclusions(path=EXCLUSIONS_PATH):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_registry_ids(path):
    """Text ids in the restricted registry at `path` (empty set if none)."""
    try:
        with open(path, encoding='utf-8') as f:
            return set((json.load(f).get('texts') or {}).keys())
    except OSError:
        return set()


def work_of(rel):
    """Base work id for any file name this bundle handles: a text
    (vergil.aeneid.part.3.tess), a lemma cache file (name-<hash>.json), a
    translation (la__vergil.aeneid.json), an embedding (name.npy,
    name.meta.json)."""
    name = rel.rsplit('/', 1)[-1]
    name = _LANG_PREFIX.sub('', name)
    for suffix in ('.meta.json', '.tess', '.json', '.npy'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    name = _HASH_SUFFIX.sub('', name)
    return base_work(name)


def non_core_languages(excl):
    langs = set(excl.get('withheld_languages', {}))
    langs |= {k for k in excl.get('other_languages_not_bundled', {})}
    return langs


def _match_path(rel, pattern):
    if any(ch in pattern for ch in '*?['):
        return fnmatch.fnmatch(rel, pattern)
    return rel == pattern or rel.startswith(pattern + '/')


def excluded_reason(rel, excl, restricted_ids=frozenset()):
    """Why this path must not be in a public bundle, or None if it may be."""
    for lang in non_core_languages(excl):
        for tpl in excl['language_scoped_path_templates']:
            if _match_path(rel, tpl.format(lang=lang)):
                return f'language {lang} is not bundled'
    for pattern, why in excl['never_paths'].items():
        if _match_path(rel, pattern) or rel.rsplit('/', 1)[-1] == pattern:
            return why
    base = rel.rsplit('/', 1)[-1]
    for pat in excl['never_name_patterns']:
        if fnmatch.fnmatch(base, pat):
            return f'name matches {pat}'
    for part in rel.split('/')[:-1]:
        for pat in excl['never_dir_name_patterns']:
            if fnmatch.fnmatch(part, pat):
                return f'folder matches {pat}'
    if restricted_ids and rel.split('/')[0] in ('texts', 'cache', 'backend', 'data'):
        if rel.endswith(('.tess', '.json', '.npy')) and work_of(rel) in restricted_ids:
            return 'text is in the restricted registry'
    return None


def translation_licence_ok(path, excl):
    """(ok, licence string) for one translation file, from its own license field."""
    rule = excl['translation_licence']
    try:
        with open(path, encoding='utf-8') as f:
            lic = str(json.load(f).get('license', ''))
    except (OSError, ValueError):
        return False, 'unreadable'
    low = lic.lower().strip()
    if not any(low.startswith(p) for p in rule['allowed_prefixes']):
        return False, lic
    if any(w in low for w in rule['forbidden_words']) or re.search(r'(?<![a-z])nc(?![a-z])', low):
        return False, lic
    return True, lic


# --------------------------------------------------------------- selection

class Item:
    __slots__ = ('rel', 'group', 'licence', 'abs')

    def __init__(self, rel, group, licence, abs_path):
        self.rel, self.group, self.licence, self.abs = rel, group, licence, abs_path


TEXT_LICENCE = 'Per work: see data/text_sources.json and LICENSES.md'
DERIVED_LICENCE = 'Derived from the texts in this bundle, same terms as the texts'
OWN_LICENCE = 'Tesserae project, MIT (derived from the texts in this bundle)'


def _walk_files(base, keep=lambda name: True):
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for fn in sorted(files):
            if keep(fn):
                yield os.path.join(root, fn)


def select(mode, prod, excl, restricted_ids, notes):
    """Yield Items for the files taken as they are. Excluded paths are counted
    into `notes` (dict reason -> count) and never yielded."""
    core = excl['core_languages']

    def want(rel, group, licence):
        why = excluded_reason(rel, excl, restricted_ids)
        if why:
            notes[why] = notes.get(why, 0) + 1
            return None
        return Item(rel, group, licence, os.path.join(prod, rel))

    def tree(sub, group, licence, keep=lambda n: True):
        base = os.path.join(prod, sub)
        if not os.path.isdir(base):
            return
        for p in _walk_files(base, keep):
            it = want(os.path.relpath(p, prod), group, licence)
            if it:
                yield it

    def one(rel, group, licence):
        if os.path.isfile(os.path.join(prod, rel)):
            it = want(rel, group, licence)
            if it:
                yield it

    for lang in core:
        yield from tree(f'texts/{lang}', 'texts', TEXT_LICENCE,
                        lambda n: n.endswith('.tess') or n.upper().startswith(('LICENSE', 'SBLGNT_LICENSE')))
        yield from one(f'cache/lemmas/{lang}.json', 'lemma_cache', DERIVED_LICENCE)
        yield from tree(f'cache/lemmas/{lang}', 'lemma_cache', DERIVED_LICENCE, lambda n: n.endswith('.json'))
        yield from one(f'data/inverted_index/{lang}_index.db', 'inverted_index', DERIVED_LICENCE)
        yield from one(f'cache/bigrams/{lang}_bigrams.json', 'bigrams', DERIVED_LICENCE)
        yield from one(f'cache/frequencies/{lang}.json', 'frequencies', DERIVED_LICENCE)

    for lang in ('la', 'grc'):
        yield from one(f'data/inverted_index/{lang}_documents_index.db', 'documents',
                       'Per document: CC BY-SA 4.0, CC BY 4.0 or CC BY 3.0, see metadata.db and LICENSES.md')

    # lemma tables: everything except the withheld languages and backups
    yield from tree('data/lemma_tables', 'lemma_tables',
                    'Treebank or lexicon derived: see the *_LICENSE.txt files and LICENSES.md',
                    lambda n: n.endswith(('.json', '.txt')))

    # translations: only files whose own licence field passes the check
    tdir = os.path.join(prod, 'data/translations')
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if not fn.endswith('.json'):
                continue
            rel = f'data/translations/{fn}'
            if _LANG_PREFIX.match(fn) is None or _LANG_PREFIX.match(fn).group(1) not in core:
                notes['translation of a language that is not bundled'] = notes.get(
                    'translation of a language that is not bundled', 0) + 1
                continue
            why = excluded_reason(rel, excl, restricted_ids)
            if why:
                notes[why] = notes.get(why, 0) + 1
                continue
            ok, lic = translation_licence_ok(os.path.join(tdir, fn), excl)
            if not ok:
                notes['translation licence is not public domain or open'] = notes.get(
                    'translation licence is not public domain or open', 0) + 1
                continue
            yield Item(rel, 'translations', lic[:200], os.path.join(prod, rel))

    for rel, lic in (('data/text_sources.json', 'Credit table for the texts (Text Credits page)'),
                     ('data/sources_credits.json', 'Credit table for every collection'),
                     ('data/translation_pairs.json', OWN_LICENCE)):
        yield from one(rel, 'metadata', lic)

    # documents collection: metadata.db and the sidecars next to it
    yield from tree('data/documents', 'documents',
                    'Per document: CC BY-SA 4.0, CC BY 4.0 or CC BY 3.0, see metadata.db and LICENSES.md')

    if mode == 'full':
        for lang in core:
            yield from tree(f'backend/embeddings/{lang}', 'embeddings',
                            'Computed from the texts in this bundle with the models named in LICENSES.md')
        for name in ('la', 'grc', 'en', 'la_documents', 'grc_documents'):
            yield from one(f'cache/reuse_pairs/{name}.db', 'reuse_pairs', DERIVED_LICENCE)
            yield from one(f'cache/reuse_pairs/{name}_stats.json', 'reuse_pairs', DERIVED_LICENCE)


def passage_index_sources(prod):
    """The current passage index files in production (originals, before the
    language filter), by name."""
    names = ('ids.json', 'embeddings.npy', 'descriptions.jsonl', 'desc_fts.sqlite',
             'window_texts.db', 'window_names.db', 'works_by_language.json')
    return {n: os.path.join(prod, 'data/passage_index', n) for n in names}


def connections_map_source(prod):
    """The newest connections map database, or None."""
    d = os.path.join(prod, 'cache/connections_map')
    if not os.path.isdir(d):
        return None
    cands = [os.path.join(d, f) for f in os.listdir(d) if re.fullmatch(r'[\d.\-]+\.db', f)]
    return max(cands, key=os.path.getmtime) if cands else None


# ------------------------------------------------------------ generated files

def filtered_text_descriptions(prod, excl, restricted_ids):
    """data/text_descriptions.json without the languages that are not bundled
    and without restricted texts."""
    with open(os.path.join(prod, 'data/text_descriptions.json'), encoding='utf-8') as f:
        data = json.load(f)
    core = set(excl['core_languages'])
    out = {}
    for k, v in data.items():
        if isinstance(v, dict):
            if k in core:
                out[k] = {w: d for w, d in v.items() if w not in restricted_ids}
        else:
            out[k] = v
    return out


def sha256_file(path, block=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_manifest(rows, out_path):
    """rows: iterable of (rel, abs_path, licence). Hashes each file."""
    n = 0
    total = 0
    with open(out_path, 'w', encoding='utf-8') as out:
        out.write('path\tsize_bytes\tsha256\tlicence_source\n')
        for rel, abs_path, lic in rows:
            size = os.path.getsize(abs_path)
            out.write(f'{rel}\t{size}\t{sha256_file(abs_path)}\t{lic}\n')
            n += 1
            total += size
    return n, total


ATTRIBUTION = [
    ('Perseus Digital Library and Open Greek and Latin',
     'Latin and Greek texts and many English translations come from the Perseus Digital Library '
     '(PerseusDL canonical-latinLit and canonical-greekLit) and the Open Greek and Latin project, '
     'licensed CC BY-SA 4.0 (some older files CC BY-SA 3.0). Credit "Perseus Digital Library, Tufts University" '
     'and "Open Greek and Latin" and keep the same licence on adaptations.'),
    ('Coptic SCRIPTORIUM', 'Coptic texts and translation layers: CC BY 4.0, credit Coptic SCRIPTORIUM.'),
    ('Miqra according to the Masorah (Hebrew Bible)',
     'CC BY-SA 4.0. Editor Seth (Avi) Kadish, obtained through Sefaria. See texts/he/LICENSE.'),
    ('SBL Greek New Testament',
     'Scripture quotations marked SBLGNT are from The Greek New Testament: SBL Edition. Copyright 2010 '
     'Society of Biblical Literature and Logos Bible Software. May not be sold on its own. '
     'See texts/grc/SBLGNT_LICENSE.txt.'),
    ('Lemma tables', 'Classical Greek: GLAUx treebanks, CC BY-SA 4.0. Koine Greek: LXX-Rahlfs-1935 by Eliran Wong, '
     'CC BY-NC-SA 4.0 (NonCommercial). Hebrew: ETCBC BHSA, CC BY-NC 4.0 (NonCommercial). '
     'The full notices are in data/lemma_tables/*_LICENSE.txt. Because of these, the bundle as a whole '
     'may be used for non-commercial purposes only.'),
]


def licences_md(items, excl, prod, counts):
    """LICENSES.md text. `counts` carries the translation licence tally and
    exclusion notes."""
    with open(os.path.join(prod, 'data/sources_credits.json'), encoding='utf-8') as f:
        credits = json.load(f)
    wanted = ('Literary texts', 'Translations', 'Inscriptions and papyri', 'Places and identifiers')
    L = []
    L.append('# Licences and attribution for the Tesserae public data bundle\n')
    L.append('This bundle gathers files from several sources, each with its own licence. '
             'MANIFEST.tsv gives the licence source of every file. Keep this file with the data.\n')
    L.append('## Read this first\n')
    L.append('Some parts are licensed for non-commercial use only (the Koine Greek and Hebrew lemma tables). '
             'Use the bundle for scholarship and teaching, not for a commercial product. '
             'Parts under share-alike licences (CC BY-SA) must keep the same licence when you pass them on.\n')
    L.append('## Attribution lines the licences require\n')
    for title, line in ATTRIBUTION:
        L.append(f'- **{title}.** {line}')
    L.append('')
    L.append('## Collections and their licences\n')
    for e in credits:
        if e['collection'] not in wanted:
            continue
        L.append(f"### {e['name']}\n")
        L.append(f"- Collection: {e['collection']}")
        L.append(f"- Licence: {e['licence_name']} ({e['licence_url']})")
        L.append(f"- Source: {e['url']}")
        L.append(f"- Version: {e['version']}")
        L.append(f"- Used on the site: {e['what_we_use']} This bundle carries only the Latin, Greek, English, Coptic and Hebrew parts.")
        if e.get('notes'):
            L.append(f"- Notes: {e['notes']}")
        L.append('')
    L.append('## Translations in this bundle\n')
    L.append('A translation file is included only if its own license field begins with "Public domain" or an open '
             'Creative Commons licence and does not name a non-commercial term. Count of files by licence:\n')
    L.append('| Files | Licence field (first 110 characters) |')
    L.append('|---|---|')
    for lic, n in sorted(counts.get('translation_licences', {}).items(), key=lambda kv: -kv[1]):
        L.append(f'| {n} | {lic[:110].replace("|", "/")} |')
    L.append('')
    L.append('## Literary texts by electronic source\n')
    L.append('Every text is credited in data/text_sources.json (author, work, electronic source, print source). '
             'The tally by electronic source is:\n')
    L.append('| Works | Electronic source |')
    L.append('|---|---|')
    for src, n in counts.get('text_sources', []):
        L.append(f'| {n} | {src} |')
    L.append('')
    L.append('## Models used to make the vectors (full bundle only)\n')
    L.append('Line and passage vectors were computed with SPhilBERTa (Latin, Greek, English), multilingual-e5-large '
             '(Coptic and the passage windows) and a fine-tuned MiqraBERT (Hebrew). These models are not in the bundle. '
             'Check the licence on each model card before you reuse the vectors outside Tesserae.\n')
    L.append('## Descriptions of passages (full bundle only)\n')
    L.append('The passage descriptions in descriptions.jsonl were written by language models from the texts in this bundle '
             'and are released with the project code under the MIT licence.\n')
    L.append('## Left out of this bundle, and why\n')
    withheld_tr = counts.get('excluded', {}).get('translation licence is not public domain or open', 0)
    L.append(f'- Translation files whose own licence is not public domain or open: {withheld_tr} (for example the part of the Punica of Silius Italicus that rests on a non-commercial translation)')
    for p, why in excl['never_paths'].items():
        L.append(f'- `{p}`: {why}')
    for lang, why in excl['withheld_languages'].items():
        L.append(f'- Language `{lang}`: {why}')
    for lang, why in excl['other_languages_not_bundled'].items():
        L.append(f'- Language `{lang}`: {why}')
    L.append('')
    return '\n'.join(L)


# -------------------------------------------------------------------- CLI

def _summary(items):
    by = {}
    for it in items:
        try:
            sz = os.path.getsize(it.abs)
        except OSError:
            sz = 0
        g = by.setdefault(it.group, [0, 0])
        g[0] += 1
        g[1] += sz
    return by


def _registry_path(prod, excl):
    p = os.path.join(prod, excl['restricted_registry'])
    return p if os.path.isfile(p) else os.path.join(ROOT, excl['restricted_registry'])


def cmd_measure(args):
    excl = load_exclusions()
    prod = args.prod
    restricted = load_registry_ids(_registry_path(prod, excl))
    notes = {}
    items = list(select(args.mode, prod, excl, restricted, notes))
    by = _summary(items)
    if args.mode == 'full':
        pi = passage_index_sources(prod)
        sz = sum(os.path.getsize(p) for p in pi.values() if os.path.isfile(p))
        by['passage_index (before the language filter, upper bound)'] = [len(pi), sz]
        m = connections_map_source(prod)
        if m:
            by['connections_map (before the language filter, upper bound)'] = [1, os.path.getsize(m)]
    total = 0
    for g, (n, sz) in sorted(by.items(), key=lambda kv: -kv[1][1]):
        print(f'{g:75s} {n:8d} files {sz / 1e9:9.2f} GB')
        total += sz
    print(f'{"TOTAL (uncompressed)":75s} {"":8s}       {total / 1e9:9.2f} GB')
    for why, n in sorted(notes.items()):
        print(f'excluded: {why}: {n}')
    return 0


def cmd_plan(args):
    excl = load_exclusions()
    prod = args.prod
    work = args.work
    stage = os.path.join(work, 'stage')
    os.makedirs(stage, exist_ok=True)
    registry_file = _registry_path(prod, excl)
    restricted = load_registry_ids(registry_file)
    notes = {}
    items = list(select(args.mode, prod, excl, restricted, notes))

    # registry guard: the index databases hold the lines of every text, so a
    # restricted text cannot be removed by leaving files out
    if restricted:
        print('REFUSING: the restricted registry is not empty and the index databases hold the lines of '
              'every text. Remove those texts from a copy of the indexes with '
              'scripts/corpus/remove_restricted_text.py, then build the bundle from that copy.',
              file=sys.stderr)
        return 4

    desc = filtered_text_descriptions(prod, excl, restricted)
    with open(os.path.join(stage, 'data_text_descriptions.json.tmp'), 'w', encoding='utf-8') as f:
        json.dump(desc, f, ensure_ascii=False, indent=1)
    os.makedirs(os.path.join(stage, 'data'), exist_ok=True)
    os.replace(os.path.join(stage, 'data_text_descriptions.json.tmp'),
               os.path.join(stage, 'data/text_descriptions.json'))

    # tallies for LICENSES.md
    tl = {}
    for it in items:
        if it.group == 'translations':
            tl[it.licence] = tl.get(it.licence, 0) + 1
    srcs = {}
    try:
        with open(os.path.join(prod, 'data/text_sources.json'), encoding='utf-8') as f:
            for e in json.load(f):
                s = (e.get('e_source') or 'unknown').strip()
                srcs[s] = srcs.get(s, 0) + 1
    except OSError:
        pass
    counts = {'translation_licences': tl, 'text_sources': sorted(srcs.items(), key=lambda kv: -kv[1]),
              'excluded': notes}
    with open(os.path.join(stage, 'LICENSES.md'), 'w', encoding='utf-8') as f:
        f.write(licences_md(items, excl, prod, counts))
    with open(os.path.join(stage, 'README_BUNDLE.txt'), 'w', encoding='utf-8') as f:
        f.write(f'Tesserae public data bundle ({args.mode}).\n'
                'Unpack at the root of a Tesserae checkout: tar --zstd -xf <bundle> -C <checkout>.\n'
                'Steps: docs/RUN_YOUR_OWN.md in the repository. Licences: LICENSES.md. '
                'File list with hashes: MANIFEST.tsv.\n')

    stage_items = [
        Item('data/text_descriptions.json', 'metadata', OWN_LICENCE + ' (machine-written, languages filtered)',
             os.path.join(stage, 'data/text_descriptions.json')),
    ]
    # the stage copy replaces the production copy of the same name
    prod_items = [it for it in items if it.rel != 'data/text_descriptions.json']

    # extra staged files (the filtered passage index and map) are added by the
    # shell script after filter_passage_index.py has run; it passes them in
    for extra in args.extra or []:
        rel, _, group = extra.partition('=')
        stage_items.append(Item(rel, group or 'passage_index', 'Derived from the texts in this bundle',
                                os.path.join(stage, rel)))

    rows = [(it.rel, it.abs, it.licence) for it in prod_items + stage_items]
    rows += [('LICENSES.md', os.path.join(stage, 'LICENSES.md'), 'This bundle'),
             ('README_BUNDLE.txt', os.path.join(stage, 'README_BUNDLE.txt'), 'This bundle')]
    n, total = write_manifest(rows, os.path.join(stage, 'MANIFEST.tsv'))

    with open(os.path.join(work, 'files.prod.null'), 'wb') as f:
        for it in prod_items:
            f.write(it.rel.encode('utf-8') + b'\0')
    with open(os.path.join(work, 'files.stage.null'), 'wb') as f:
        for it in stage_items:
            f.write(it.rel.encode('utf-8') + b'\0')
        for rel in ('LICENSES.md', 'README_BUNDLE.txt', 'MANIFEST.tsv'):
            f.write(rel.encode('utf-8') + b'\0')
    print(f'planned {n} files, {total / 1e9:.2f} GB uncompressed (manifest rows)')
    for g, (c, sz) in sorted(_summary(prod_items + stage_items).items(), key=lambda kv: -kv[1][1]):
        print(f'  {g:20s} {c:8d} files {sz / 1e9:8.2f} GB')
    for why, c in sorted(notes.items()):
        print(f'  excluded: {why}: {c}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, fn in (('plan', cmd_plan), ('measure', cmd_measure)):
        p = sub.add_parser(name)
        p.add_argument('--mode', choices=('core', 'full'), required=True)
        p.add_argument('--prod', default=DEFAULT_PROD)
        if name == 'plan':
            p.add_argument('--work', required=True)
            p.add_argument('--extra', action='append', help='REL[=group] of a file already in WORK/stage')
        p.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
