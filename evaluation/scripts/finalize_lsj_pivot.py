"""Filter the raw LSJ/Lewis-Short pivot pairs into the dictionary file.

This rewrites the lost /tmp/finalize_lsj_pivot.py from the parameters recorded
in research/plans/Bernstein/lexicon_pivot_expansion_plan.md (2026-05-22).
Input is the output of extract_lsj_ls_pivot.py (lsj_ls_pivot_full.csv, columns
greek,latin,score,shared_glosses,n_glosses). Three filters, in this order:

1. keep pairs with score >= 0.3
2. drop a pair when every gloss in its shared-gloss set is on the stoplist
3. keep at most 20 Latin lemmas per Greek lemma, highest score first

The original stoplist was an "expanded" list that is not recoverable. This
script uses the extractor's ENGLISH_STOP (copied below) plus the two glosses the plan names
("fin" and "act"). See the measurement report for how far that falls from the
May file.

Usage:
    python evaluation/scripts/finalize_lsj_pivot.py RAW_CSV OUT_CSV
"""
import csv
import sys
from collections import defaultdict

MIN_SCORE = 0.3
MAX_FANOUT = 20
NAMED_NOISE = {'fin', 'act'}

# Copied from extract_lsj_ls_pivot.py (which is not tracked in git), so this
# script runs on its own.
# Common English function/stop words that produce noisy pivots
ENGLISH_STOP = {
    'the', 'a', 'an', 'is', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'shall', 'should', 'may', 'might', 'can', 'could', 'must',
    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
    'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their',
    'this', 'that', 'these', 'those', 'who', 'whom', 'which', 'what',
    'and', 'or', 'but', 'if', 'when', 'where', 'how', 'why', 'because',
    'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'out', 'off', 'over', 'under', 'again', 'further',
    'then', 'once', 'here', 'there', 'all', 'each', 'every', 'both',
    'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
    'also', 'now', 'even', 'still', 'already', 'yet',
    # Glossing artifacts
    'esp', 'esply', 'etc', 'cf', 'see', 'foll', 'pl', 'sing',
    'sc', 'usu', 'eg', 'ie', 'v', 'l',
    # Vacuous verb glosses (would pair anything)
    'go', 'come', 'put', 'get', 'set', 'let', 'say', 'tell', 'give',
    'take', 'make', 'see', 'know', 'think', 'find', 'look',
}


def finalize(raw_path, out_path):
    stop = set(ENGLISH_STOP) | NAMED_NOISE
    by_greek = defaultdict(list)
    n_raw = n_score = n_stop = 0
    with open(raw_path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            n_raw += 1
            if float(row['score']) < MIN_SCORE:
                continue
            n_score += 1
            glosses = [g.strip() for g in row['shared_glosses'].split(';')]
            if all(g in stop for g in glosses):
                n_stop += 1
                continue
            by_greek[row['greek']].append((float(row['score']), row['latin']))
    lines = []
    n_pairs = 0
    for greek in sorted(by_greek):
        ranked = sorted(by_greek[greek], key=lambda x: -x[0])[:MAX_FANOUT]
        n_pairs += len(ranked)
        lines.append(greek + ',' + ','.join(lat for _, lat in ranked))
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        f.write('# LSJ <-> Lewis-Short pivot expansion\n')
        f.write('# Pipeline: evaluation/scripts/extract_lsj_ls_pivot.py + evaluation/scripts/finalize_lsj_pivot.py\n')
        f.write(f'# Filters: score >= {MIN_SCORE}, stoplist (extractor ENGLISH_STOP + fin, act), fanout cap = {MAX_FANOUT} Latin per Greek lemma.\n')
        f.write(f'# {len(lines):,} Greek lemmas, {n_pairs:,} Greek-Latin pairs.\n')
        f.write('# Rationale: research/plans/Bernstein/lexicon_pivot_expansion_plan.md\n')
        f.write('# Format: greek_lemma,latin1,latin2,...\n')
        for line in lines:
            f.write(line + '\n')
    print(f'raw pairs {n_raw:,}; score>={MIN_SCORE} {n_score:,}; dropped by stoplist {n_stop:,}; '
          f'final {n_pairs:,} pairs, {len(lines):,} Greek lemmas')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    finalize(sys.argv[1], sys.argv[2])
