#!/usr/bin/env python3
"""Write copies of the whole-language count files without the restricted works.

The public data bundle carries three files that cover a whole language and
hold counts from every work in it, so leaving a restricted work's own files
out does not remove its share:

    cache/frequencies/<lang>.json   lemma counts over the whole language
    cache/bigrams/<lang>_bigrams.json   bigram counts and per-bigram document counts
    data/translation_pairs.json     which works are translations of which (language independent)

This script reads data/restricted_texts.json, counts what each restricted work
contributes, lemmatizing with the deployed text processor the way the original builders do
(backend/frequency_cache.py and backend/bigram_frequency.py), subtracts that
from the original file, drops entries that fall to zero, and writes the result
to --out. It never writes over an original, and the script refuses to write over
refuses any path under --prod.

Before it subtracts, it adds up the whole language from the texts the
same way and reports whether that equals the original file. When it does, the
subtraction is the same as a rebuild from the remaining works. When it does
not, the report says so and the subtraction stands on the original file.

    venv/bin/python scripts/corpus/filter_language_caches_by_registry.py \\
        --lang cop --prod /var/www/tesseraev6_flask --out STAGING/filtered

Prints a JSON report. Reads production data, never writes under it.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

def _code_root():
    """The folder whose `backend` package does the lemmatizing. Production by default, so the lemmas are
    those of the deployed code and of the Coptic data that lives only on the server; the repository
    when --prod is not given."""
    for i, a in enumerate(sys.argv):
        if a == '--prod' and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith('--prod='):
            return a.split('=', 1)[1]
    return '/var/www/tesseraev6_flask'


sys.dont_write_bytecode = True  # nothing may be written under the production folder, not even .pyc files
sys.path.insert(0, _code_root())
sys.path.insert(1, os.path.join(ROOT, 'scripts', 'ops'))

from backend.work_names import base_work, is_part  # noqa: E402
from backend.text_processor import TextProcessor  # noqa: E402
import public_bundle_lib as lib  # noqa: E402

_processor = None

# Coptic aggregate files are left out of the bigram table, as in bigram_frequency.py
BIGRAM_AGGREGATE_SUFFIXES = ('bible', 'ot', 'nt', 'all')


def load_ids(registry):
    with open(registry, encoding='utf-8') as f:
        return set(json.load(f).get('texts', {}))


def unit_lemmas(prod, lang, text_file, use_cache=False):
    """Lemma lists of the line units of one text, from the deployed code. The bigram builder reads the
    lemma cache when it is current and processes the text otherwise, the frequency builder always
    processes the text, and this does the same so the counts agree with the files being filtered."""
    global _processor
    if use_cache:
        from backend.lemma_cache import get_cached_units
        cached = get_cached_units(text_file, lang)
        units = (cached or {}).get('units_line')
        if units:
            return [u.get('lemmas', []) for u in units]
    if _processor is None:
        _processor = TextProcessor()
    units = _processor.process_file(os.path.join(prod, 'texts', lang, text_file), lang)
    return [u.get('lemmas', []) for u in units]


def dedupe_parts(files):
    """backend.frequency_cache.deduplicate_text_files and the same step in bigram_frequency."""
    full = {f[:-len('.tess')] for f in files if '.part.' not in f}
    return [f for f in files if not (is_part(f) and base_work(f) in full)]


def counted_files(lang, files, kind):
    if kind == 'bigrams' and lang == 'cop':
        files = [f for f in files if f[:-len('.tess')].split('.')[-1] not in BIGRAM_AGGREGATE_SUFFIXES]
    return dedupe_parts(files)


def count_lemmas(prod, lang, files):
    c = Counter()
    for f in files:
        for lem in unit_lemmas(prod, lang, f):
            c.update(lem)
    return c


def bigram_key(a, b):
    return f'{min(a, b)}|{max(a, b)}'


# The Coptic bigram table in production (built 8 August 2026) spells seven letters with other code points
# than the lemmas of the same texts use (Coptic block, in order: shei, fei, khei, hori, gangia, shima, dei
# come out as the seven letters two code points apart that follow). This map reproduces that spelling so a
# restricted work's bigrams are subtracted under the keys the table really holds.
OLD_COPTIC_SPELLING = str.maketrans('\u03e3\u03e5\u03e7\u03e9\u03eb\u03ed\u03ef', '\u2cb3\u2cb5\u2cb7\u2cb9\u2cbb\u2cbd\u2cbf')


def table_uses_old_spelling(keys):
    chars = set()
    for k in keys:
        chars.update(k)
    return not chars & set('\u03e3\u03e5\u03e7\u03e9\u03eb\u03ed\u03ef') and set('\u2cb3\u2cb5\u2cb7\u2cb9\u2cbb\u2cbd\u2cbf') <= chars


def count_bigrams(prod, lang, files, translate=None):
    freq, docfreq, occurrences = Counter(), Counter(), 0
    for f in files:
        seen = set()
        for lem in unit_lemmas(prod, lang, f, use_cache=True):
            if translate:
                lem = [x.translate(translate) if x else x for x in lem]
            bgs = [bigram_key(lem[i], lem[i + 1]) for i in range(len(lem) - 1) if lem[i] and lem[i + 1]]
            freq.update(bgs)
            occurrences += len(bgs)
            seen.update(bgs)
        docfreq.update(seen)
    return freq, docfreq, occurrences


def subtract(original, remove):
    """original minus remove, entries at zero dropped, original order kept (most common first).
    Every key being removed must exist in the original with at least that count."""
    missing = [k for k in remove if k not in original]
    if missing:
        raise SystemExit(f'STOP: {len(missing)} keys of the removed work are not in the original file, first {missing[:3]}')
    out = {}
    for k, v in original.items():
        left = v - remove.get(k, 0)
        if left < 0:
            raise SystemExit(f'STOP: {k!r} would go negative ({v} - {remove[k]}), the original does not contain that work')
        if left:
            out[k] = left
    return out


def corpus_checksum(prod, lang, kept):
    """backend.frequency_cache.get_corpus_checksum over the files that stay."""
    info = []
    for name in sorted(kept):
        st = os.stat(os.path.join(prod, 'texts', lang, name))
        info.append(f'{name}:{st.st_size}:{st.st_mtime}')
    return hashlib.md5('\n'.join(info).encode('utf-8', 'surrogateescape')).hexdigest()  # nosec B324


def write_json(path, data, prod):
    real = os.path.realpath(path)
    if real.startswith(os.path.realpath(prod) + os.sep):
        raise SystemExit(f'STOP: refusing to write under production: {path}')
    with open(real + '.partial', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(real + '.partial', real)
    return os.path.getsize(real)


def same(a, b):
    return dict(a) == dict(b)


def filter_frequencies(prod, lang, ids, out, check=True):
    src = os.path.join(prod, 'cache', 'frequencies', f'{lang}.json')
    with open(src, encoding='utf-8') as f:
        orig = json.load(f)
    all_files = sorted(n for n in os.listdir(os.path.join(prod, 'texts', lang)) if n.endswith('.tess'))
    counted = counted_files(lang, all_files, 'frequencies')
    restricted = [f for f in counted if base_work(f[:-len('.tess')]) in ids]
    report = {'file': f'cache/frequencies/{lang}.json', 'restricted_files_counted': len(restricted)}
    if check:
        full = count_lemmas(prod, lang, counted)
        report['rebuild_from_caches_matches_original'] = same(full, orig['frequencies'])
        report['rebuild_total_lemmas'] = sum(full.values())
    removed = count_lemmas(prod, lang, restricted)
    freqs = subtract(orig['frequencies'], removed)
    kept = [f for f in all_files if base_work(f[:-len('.tess')]) not in ids
            and lib.excluded_reason(f'texts/{lang}/{f}', lib.load_exclusions(), ids) is None]
    new = dict(orig)
    new['frequencies'] = freqs
    new['total_lemmas'] = orig['total_lemmas'] - sum(removed.values())
    new['text_count'] = len(kept)
    new['checksum'] = corpus_checksum(prod, lang, kept)
    new['filtered_by_registry'] = len(ids)  # a count, so the file does not name the works
    dest = os.path.join(out, f'{lang}.frequencies.filtered.json')
    report.update({'out': dest, 'size_before': os.path.getsize(src), 'size_after': write_json(dest, new, prod),
                   'keys_before': len(orig['frequencies']), 'keys_after': len(freqs),
                   'total_lemmas_before': orig['total_lemmas'], 'total_lemmas_after': new['total_lemmas'],
                   'text_count_before': orig['text_count'], 'text_count_after': new['text_count']})
    return report, dest


def filter_bigrams(prod, lang, ids, out, check=True):
    src = os.path.join(prod, 'cache', 'bigrams', f'{lang}_bigrams.json')
    with open(src, encoding='utf-8') as f:
        orig = json.load(f)
    all_files = sorted(n for n in os.listdir(os.path.join(prod, 'texts', lang)) if n.endswith('.tess'))
    counted = counted_files(lang, all_files, 'bigrams')
    restricted = [f for f in counted if base_work(f[:-len('.tess')]) in ids]
    old = table_uses_old_spelling(orig['frequencies'])
    tr = OLD_COPTIC_SPELLING if old else None
    report = {'file': f'cache/bigrams/{lang}_bigrams.json', 'restricted_files_counted': len(restricted),
              'table_uses_old_coptic_letter_spelling': old}
    if check:
        freq, docfreq, occ = count_bigrams(prod, lang, counted, tr)
        report['rebuild_from_caches_matches_original'] = (
            same(freq, orig['frequencies']) and same(docfreq, orig['doc_frequencies'])
            and occ == orig['total_bigrams'] and len(counted) == orig['total_docs'])
    rfreq, rdoc, rocc = count_bigrams(prod, lang, restricted, tr)
    new = dict(orig)
    new['frequencies'] = subtract(orig['frequencies'], rfreq)
    new['doc_frequencies'] = subtract(orig['doc_frequencies'], rdoc)
    new['total_bigrams'] = orig['total_bigrams'] - rocc
    new['total_docs'] = orig['total_docs'] - len(restricted)
    new['filtered_by_registry'] = len(ids)  # a count, so the file does not name the works
    dest = os.path.join(out, f'{lang}_bigrams.filtered.json')
    report.update({'out': dest, 'size_before': os.path.getsize(src), 'size_after': write_json(dest, new, prod),
                   'keys_before': len(orig['frequencies']), 'keys_after': len(new['frequencies']),
                   'doc_keys_before': len(orig['doc_frequencies']), 'doc_keys_after': len(new['doc_frequencies']),
                   'total_bigrams_before': orig['total_bigrams'], 'total_bigrams_after': new['total_bigrams'],
                   'total_docs_before': orig['total_docs'], 'total_docs_after': new['total_docs']})
    return report, dest


def filter_translation_pairs(prod, ids, out):
    src = os.path.join(prod, 'data', 'translation_pairs.json')
    with open(src, encoding='utf-8') as f:
        orig = json.load(f)
    pairs = [p for p in orig['pairs'] if p.get('work_a') not in ids and p.get('work_b') not in ids]
    new = dict(orig)
    new['pairs'] = pairs
    new['count'] = len(pairs)
    dest = os.path.join(out, 'translation_pairs.filtered.json')
    report = {'file': 'data/translation_pairs.json', 'out': dest, 'size_before': os.path.getsize(src),
              'size_after': write_json(dest, new, prod), 'pairs_before': len(orig['pairs']), 'pairs_after': len(pairs)}
    return report, dest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--lang', default='cop')
    ap.add_argument('--prod', default='/var/www/tesseraev6_flask')
    ap.add_argument('--registry', default=os.path.join(ROOT, 'data', 'restricted_texts.json'))
    ap.add_argument('--out', required=True, help='folder for the filtered copies')
    ap.add_argument('--no-check', action='store_true', help='skip the whole-language rebuild comparison')
    args = ap.parse_args()
    ids = load_ids(args.registry)
    os.makedirs(args.out, exist_ok=True)
    reports = []
    for fn in (lambda: filter_frequencies(args.prod, args.lang, ids, args.out, not args.no_check),
               lambda: filter_bigrams(args.prod, args.lang, ids, args.out, not args.no_check),
               lambda: filter_translation_pairs(args.prod, ids, args.out)):
        rep, _ = fn()
        reports.append(rep)
    print(json.dumps(reports, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
