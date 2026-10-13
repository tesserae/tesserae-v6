#!/usr/bin/env python3
"""Daylight prototype: the owner's two examples, the top gaps, the Theme Search
comparison and the free labels that did not fit the vocabulary. Reads the tables
written by daylight_tables.py and writes OUT/report_tables.md (tables and counts
only). Every figure rests on the JSTOR Early Journal Content holdings, 1827 to 1922.
"""
import csv
import json
import os
from collections import Counter

from daylight_common import HOLDINGS, OUT
from daylight_tables import Profiles, fisher_p, load_meta, work_info, split_part
from daylight_theme import daylight_theme

L = []


def out(s=''):
    L.append(s)


def read(name):
    return list(csv.DictReader(open(os.path.join(OUT, name), encoding='utf-8')))


def compare(P, label, A, B, topics, a_name, b_name):
    na, ca = P.counts(A)
    nb, cb = P.counts(B)
    out(f'**{label}**: {a_name} ({na} articles) against {b_name} ({nb} articles)')
    out()
    out('| topic | %s | share | %s | share | Fisher p |' % (a_name, b_name))
    out('|---|---|---|---|---|---|')
    for t in topics:
        x, y = ca.get(t, [0, 0])[0], cb.get(t, [0, 0])[0]
        out(f'| {t[0]}: {t[1]} | {x} | {x / na:.3f} | {y} | {y / nb:.3f} | {fisher_p(x, na, y, nb):.3g} |')
    out()


def gap_lines(rows, n):
    out('| work | topic | articles | observed | expected | score |')
    out('|---|---|---|---|---|---|')
    for r in rows[:n]:
        out(f"| {r['work']} | {r['topic_type']}: {r['topic']} | {r['work_articles']} | {r['observed_articles']} "
            f"| {r['expected_articles']} | {r['gap_score']} |")
    out()


def main():
    summ = json.load(open(os.path.join(OUT, 'tables_summary.json')))
    out('# Daylight prototype tables')
    out()
    out(f'Holdings: {HOLDINGS}. A gap is relative to these holdings. Labelled articles: {summ["labelled_articles"]}. '
        f'Neighbour rule: same language, same genre or same era and metre, profile correlation at least {summ["corr_threshold"]}.')
    out()
    P = Profiles()
    lang, genre, dates = load_meta()
    info = {w: work_info(w, lang, genre, dates) for w in P.by_work}
    neigh = read('neighbours.csv')
    nb = lambda w: [r for r in neigh if r['work'] == w and r['neighbour'] == 'yes']

    out('## The two examples')
    out()
    A, T = 'vergil.aeneid', 'statius.thebaid'
    compare(P, 'Metrical analysis, Aeneid against Thebaid', P.by_work[A], P.by_work[T],
            [('approach', 'metrical analysis'), ('theme', 'metre and prosody'), ('theme', 'rhythm of prose')],
            'Aeneid', 'Thebaid')
    for w in (A, T):
        ns = nb(w)
        out(f'Neighbours of {w} ({len(ns)}): ' + ', '.join(f"{r['candidate']} (r={r['profile_correlation']}, n={r['candidate_articles']})"
                                                       for r in sorted(ns, key=lambda r: -float(r['profile_correlation']))[:12]))
        out()
    gaps = read('gaps.csv')
    for w in (T,):
        for r in gaps:
            if r['work'] == w and r['topic'] in ('metrical analysis', 'metre and prosody'):
                out(f"Gap row for {w}: {r['topic_type']}: {r['topic']}, observed {r['observed_articles']} of {r['work_articles']}, "
                    f"expected {r['expected_articles']} from {r['neighbours']} neighbours, score {r['gap_score']}.")
    out()
    eur = set().union(*[ids for w, ids in P.by_work.items() if info[w]['author'] == 'euripides'])
    sen_t = set().union(*[ids for w, ids in P.by_work.items()
                          if info[w]['author'] == 'seneca' and info[w]['genre'] == 'drama'])
    sen_works = sorted(w for w in P.by_work if info[w]['author'] == 'seneca' and info[w]['genre'] == 'drama')
    out('Seneca tragedies used: ' + ', '.join(f'{w} ({len(P.by_work[w])})' for w in sen_works))
    eur_works = sorted(w for w in P.by_work if info[w]['author'] == 'euripides')
    out()
    out('Euripides works used: ' + ', '.join(f'{w} ({len(P.by_work[w])})' for w in eur_works))
    out()
    compare(P, 'The place of women, Euripides against Seneca tragedies', eur, sen_t,
            [('theme', 'the place of women'), ('theme', 'marriage and family'), ('theme', 'love and desire')],
            'Euripides', 'Seneca tragedies')
    out('(Per play, Euripides and Seneca are separate works in the corpus, each with its own, thinner, article set; '
        'the groups above pool the plays so that the counts are not swamped by thinness.)')
    out()
    for w in ('euripides.hippolytus', 'seneca.phoenissae'):
        ns = nb(w)
        out(f'Work-level neighbours of {w} ({len(P.by_work[w])} articles; {len(ns)}): ' +
            ', '.join(f"{r['candidate']} (r={r['profile_correlation']})" for r in sorted(ns, key=lambda r: -float(r['profile_correlation']))[:10]))
        for r in gaps:
            if r['work'] == w and r['topic'] == 'the place of women':
                out(f"Gap row: observed {r['observed_articles']} of {r['work_articles']}, expected {r['expected_articles']}, score {r['gap_score']}.")
        out()
    out('## Top twenty gaps overall (works with at least 20 articles)')
    out()
    gap_lines(gaps, 20)
    out('## Top five gaps for each of ten well-covered works')
    out()
    big = sorted((w for w in P.by_work), key=lambda w: -len(P.by_work[w]))
    done = 0
    for w in big:
        rows = [r for r in gaps if r['work'] == w]
        if not rows:
            continue
        out(f'### {w} ({len(P.by_work[w])} articles, {rows[0]["neighbours"]} neighbours)')
        out()
        gap_lines(rows, 5)
        done += 1
        if done == 10:
            break

    out('## Theme Search grouped by cited work')
    out()
    pairs = [('metrical analysis', ('approach', 'metrical analysis')), ('the place of women', ('theme', 'the place of women')),
             ('ecphrasis', None), ('slavery', ('theme', 'slavery and labour'))]
    for q, topic in pairs:
        r = daylight_theme(q)
        out(f'**"{q}"**: {r["windows_returned"]} windows returned (depth {r["depth"]}), works with at least 20 articles')
        out()
        out('| work | articles returned | work articles | share | label-table share |')
        out('|---|---|---|---|---|')
        lab_share = {}
        if topic:
            for w, ids in P.by_work.items():
                if len(ids) >= 20:
                    lab_share[w] = P.counts(ids)[1].get(topic, [0, 0])[0] / len(ids)
        for row in r['rows'][:10]:
            ls = lab_share.get(row['work'])
            out(f"| {row['work']} | {row['articles_returned']} | {row['work_articles']} | {row['share']} | "
                f"{'' if ls is None else round(ls, 4)} |")
        out()
        if topic:
            ts = [x['work'] for x in r['rows'][:10]]
            ls_top = [w for w, _ in sorted(lab_share.items(), key=lambda kv: -kv[1])[:10]]
            both = set(ts) & set(ls_top)
            # Spearman over works present in both
            common = [x['work'] for x in r['rows'] if x['work'] in lab_share]
            def ranks(vals):
                o = sorted(range(len(vals)), key=lambda i: -vals[i])
                rk = [0] * len(vals)
                for p, i in enumerate(o):
                    rk[i] = p
                return rk
            if len(common) > 3:
                a = ranks([next(x['share'] for x in r['rows'] if x['work'] == w) for w in common])
                b = ranks([lab_share[w] for w in common])
                n = len(common)
                rho = 1 - 6 * sum((x - y) ** 2 for x, y in zip(a, b)) / (n * (n * n - 1))
            else:
                rho = float('nan')
            out(f'Agreement with the label table for {topic[1]}: {len(both)} of the top 10 works shared; '
                f'Spearman rho {rho:.2f} over {len(common)} works returned by both.')
        else:
            out('No label in the vocabulary names this topic, so there is no label-table comparison.')
        out()

    out('## Free labels that did not fit the lists (sample of 600)')
    out()
    voc = json.load(open(os.path.join(OUT, 'daylight_vocabulary.json')))
    fa = Counter(); ft = Counter()
    for line in open(os.path.join(OUT, 'free_labels.jsonl'), encoding='utf-8'):
        d = json.loads(line)
        fa.update(set(x for x in d['approaches'] if x not in voc['approaches'] and x != 'other'))
        ft.update(set(x for x in d['themes'] if x not in voc['themes'] and x != 'other'))
    both = fa + ft
    out('Counts in the 600-article free pass; exact-string misses against the written lists, so some are '
        'near-synonyms of a listed label rather than gaps in it.')
    out()
    out('| free label | articles |')
    out('|---|---|')
    for k, v in both.most_common(10):
        out(f'| {k} | {v} |')
    out()
    open(os.path.join(OUT, 'report_tables.md'), 'w', encoding='utf-8').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
