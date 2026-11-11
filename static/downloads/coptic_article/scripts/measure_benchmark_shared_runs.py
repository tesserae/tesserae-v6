#!/usr/bin/env python3
"""Longest run of consecutive shared words for each pair of the 124-pair Hebrews x Psalms benchmark.

For every pair in gold/tsk_hebrews_psalms_gold_124.csv the script reports the longest run of
consecutive shared words (and separately of shared lemmas) between the Hebrews verse and the
Psalm verse, in the Sahidic texts and in the Greek texts (Swete's Septuagint for the Psalms, the SBL
Greek New Testament for Hebrews). A
pair with no run of three or more shared words in either language is one the article counts as
a cross-reference of theme, allusion or formula rather than a quotation (article section 3.2).

Input: the per-text lemma caches of a Tesserae V6 checkout (cache/lemmas/cop/*.json and
cache/lemmas/grc/*.json), which hold the tokens and lemmas of every line. The caches are built
by the application from the texts; no text is written to the output, only references, vote
counts and run lengths.

Usage, from the checkout root:
    python3 data_release/scripts/measure_benchmark_shared_runs.py \
        --gold data_release/gold/tsk_hebrews_psalms_gold_124.csv \
        --out data_release/outputs/hebrews_psalms_benchmark124_shared_runs.csv \
        [--verbatim-list PATH]   # the hand-curated list of 29 quotations, if available

Words are compared after lower-casing, ignoring tokens with no letter (punctuation). Greek
verses are matched by chapter and verse number because the Psalms file's reference form has
changed between releases.
"""
import argparse, csv, glob, json, os, re, sys


def cv(ref):
    m = re.search(r'(\d+)\.(\d+)\s*$', str(ref))
    return (m.group(1), m.group(2)) if m else None


def load_cache(root, lang, stem):
    """Return {(chapter, verse): {'tokens': [...], 'lemmas': [...]}} for one text."""
    paths = sorted(glob.glob(os.path.join(root, 'cache', 'lemmas', lang, stem + '*.json')))
    paths = [p for p in paths if os.path.basename(p) == stem + '.json' or os.path.basename(p).startswith(stem + '-')]
    if not paths:
        sys.exit(f'no lemma cache for {lang}/{stem} under {root}')
    data = json.load(open(paths[0], encoding='utf-8'))
    units = data['units_line'] if isinstance(data, dict) and 'units_line' in data else \
        [dict(ref=k, **v) for k, v in data.items() if isinstance(v, dict) and 'tokens' in v]
    return {cv(u['ref']): u for u in units if cv(u['ref'])}


def words(tokens):
    return [t.lower() for t in tokens if any(ch.isalpha() for ch in t)]


def longest_run(a, b):
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            if k > best:
                best = k
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.', help='Tesserae V6 checkout with cache/lemmas/')
    ap.add_argument('--gold', default='data_release/gold/tsk_hebrews_psalms_gold_124.csv')
    ap.add_argument('--out', default='data_release/outputs/hebrews_psalms_benchmark124_shared_runs.csv')
    ap.add_argument('--verbatim-list', default=None,
                    help='CSV with nt_v6_ref,lxx_v6_ref of the hand-curated verbatim quotations (optional)')
    a = ap.parse_args()

    cop_heb = load_cache(a.root, 'cop', 'sahidica.hebrews')
    cop_pss = load_cache(a.root, 'cop', 'sahidic.psalms')
    grc_heb = load_cache(a.root, 'grc', 'novum_testamentum.ad_hebraeos')
    grc_pss = load_cache(a.root, 'grc', 'septuaginta.psalmi')
    verbatim = set()
    if a.verbatim_list:
        verbatim = {(r['nt_v6_ref'], r['lxx_v6_ref']) for r in csv.DictReader(open(a.verbatim_list, encoding='utf-8'))}

    rows = []
    for r in csv.DictReader(open(a.gold, encoding='utf-8')):
        h, p = (r['nt_chap'], r['nt_verse']), (r['lxx_chap'], r['lxx_verse'])
        ch, cp, gh, gp = cop_heb.get(h), cop_pss.get(p), grc_heb.get(h), grc_pss.get(p)
        if not (ch and cp and gh and gp):
            sys.exit(f'missing verse for {r["nt_v6_ref"]} / {r["lxx_v6_ref"]}')
        rows.append({
            'hebrews_ref': r['nt_v6_ref'], 'psalm_ref': r['lxx_v6_ref'], 'votes': r['votes'],
            'on_verbatim_list': ('yes' if (r['nt_v6_ref'], r['lxx_v6_ref']) in verbatim else 'no') if verbatim else '',
            'sahidic_word_run': longest_run(words(ch['tokens']), words(cp['tokens'])),
            'sahidic_lemma_run': longest_run(words(ch['lemmas']), words(cp['lemmas'])),
            'greek_word_run': longest_run(words(gh['tokens']), words(gp['tokens'])),
            'greek_lemma_run': longest_run(words(gh['lemmas']), words(gp['lemmas'])),
        })

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
        w.writeheader(); w.writerows(rows)

    n = len(rows)
    def count(key, k): return sum(1 for x in rows if x[key] >= k)
    print(f'{n} pairs written to {a.out}')
    for key in ('sahidic_word_run', 'greek_word_run'):
        print(f'  {key}: >=3 in {count(key, 3)}, >=5 in {count(key, 5)}, under 3 in {n - count(key, 3)}')
    neither = sum(1 for x in rows if x['sahidic_word_run'] < 3 and x['greek_word_run'] < 3)
    print(f'  no run of 3 or more words in either language: {neither} of {n} ({100 * neither / n:.0f} percent)')
    if verbatim:
        print(f'  on the verbatim list: {sum(1 for x in rows if x["on_verbatim_list"] == "yes")}')


if __name__ == '__main__':
    main()
