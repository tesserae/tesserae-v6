#!/usr/bin/env python3
"""Daylight prototype: coverage, neighbours and gap tables.

Reads the article labels (labels.jsonl, kept outside the repository) and the
citation index, and writes tables only: no article text. Every table rests on
the JSTOR Early Journal Content holdings (24 journals, 1827 to 1922) and a gap
is always relative to those holdings.

  python daylight_tables.py [--corr 0.5] [--min-articles 20]

A topic is ("approach", name) or ("theme", name). A work's articles are the
articles that cite it (an article citing several works counts once for each).
"""
import argparse
import csv
import glob
import json
import math
import os
from collections import defaultdict

from daylight_common import HOLDINGS, OUT, ROOT, connect, cited_works

SKIP = {'other', 'not about classical antiquity'}

# Genre for Greek authors (data/text_genres.csv covers the Latin texts only).
GREEK_GENRE = {
    'homer': 'epic', 'hesiod': 'epic', 'apollonius_rhodius': 'epic', 'quintus_smyrnaeus': 'epic',
    'nonnus': 'epic', 'aeschylus': 'drama', 'sophocles': 'drama', 'euripides': 'drama',
    'aristophanes': 'drama', 'menander': 'drama', 'pindar': 'lyric', 'bacchylides': 'lyric',
    'theocritus': 'pastoral', 'callimachus': 'elegy', 'herodotus': 'historiography',
    'thucydides': 'historiography', 'xenophon': 'historiography', 'polybius': 'historiography',
    'plutarch': 'biography', 'diodorus_siculus': 'historiography', 'strabo': 'technical',
    'pausanias': 'technical', 'plato': 'philosophy', 'aristotle': 'philosophy',
    'demosthenes': 'oratory', 'lysias': 'oratory', 'isocrates': 'oratory', 'aeschines': 'oratory',
    'lucian': 'satire', 'dio_chrysostom': 'oratory', 'arrian': 'historiography',
    'appian': 'historiography', 'josephus': 'historiography', 'philo': 'philosophy',
}


def split_part(wid):
    return wid.split('.part.')[0]


def load_meta():
    """work id -> dict(author, language, genre, meter, era)."""
    lang = {}
    for p in glob.glob(os.path.join(ROOT, 'texts', '*', '*.tess')) + \
            glob.glob('/var/www/tesseraev6_flask/texts/*/*.tess'):
        lang.setdefault(split_part(os.path.basename(p)[:-5]), p.split('/')[-2])
    genre = {}
    path = os.path.join(ROOT, 'data', 'text_genres.csv')
    for r in csv.DictReader(open(path, encoding='utf-8')):
        genre.setdefault(split_part(r['filename'][:-5]), (r['era'], r['meter'], r['genre']))
    dates = json.load(open(os.path.join(ROOT, 'backend', 'author_dates.json'), encoding='utf-8'))
    return lang, genre, dates


def work_info(wid, lang, genre, dates):
    author = wid.split('.')[0]
    la = lang.get(wid)
    if la is None:
        la = next((v for k, v in lang.items() if k.split('.')[0] == author), 'unknown')
    era, meter, g = genre.get(wid, (None, None, None))
    if era is None:
        e = (dates.get(la, {}) or {}).get(author)
        era = e.get('era') if isinstance(e, dict) else None
    if g is None:
        g = GREEK_GENRE.get(author, 'unclassified')
    return {'work': wid, 'author': author, 'language': la, 'era': era or 'unknown',
            'meter': meter or 'unknown', 'genre': g}


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def load_labels():
    lab = {}
    for line in open(os.path.join(OUT, 'labels.jsonl'), encoding='utf-8'):
        d = json.loads(line)
        lab[d['id']] = d
    return lab


class Profiles:
    """Topic counts for groups of works, built once from the labels."""

    def __init__(self):
        con = connect()
        self.lab = load_labels()
        self.pages = dict(con.execute('select id, coalesce(n_pages,0) from articles'))
        self.cites = cited_works(con)
        self.topics_of = {}
        for aid, d in self.lab.items():
            self.topics_of[aid] = ([('approach', t) for t in d['approaches'] if t not in SKIP] +
                                   [('theme', t) for t in d['themes'] if t not in SKIP])
        self.by_work = defaultdict(set)
        for aid, ws in self.cites.items():
            if aid in self.lab:
                for w in ws:
                    self.by_work[split_part(w)].add(aid)

    def counts(self, article_ids):
        """(n_articles, {topic: (n_articles, n_pages)}) for a set of articles."""
        c = defaultdict(lambda: [0, 0])
        for aid in article_ids:
            for t in set(self.topics_of.get(aid, ())):
                c[t][0] += 1
                c[t][1] += self.pages.get(aid, 0)
        return len(article_ids), c


def fisher_p(a, n1, b, n2):
    """Two-sided Fisher exact p for a/n1 versus b/n2 (small counts; log-gamma)."""
    k, n, K = a + b, n1 + n2, n1

    def lp(x):
        return (math.lgamma(K + 1) - math.lgamma(x + 1) - math.lgamma(K - x + 1) +
                math.lgamma(n - K + 1) - math.lgamma(k - x + 1) - math.lgamma(n - K - k + x + 1) -
                (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)))
    lo, hi = max(0, k - (n - K)), min(k, K)
    p0 = lp(a)
    return min(1.0, sum(math.exp(lp(x)) for x in range(lo, hi + 1) if lp(x) <= p0 + 1e-9))


def write_csv(name, header, rows):
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corr', type=float, default=0.3)
    ap.add_argument('--min-articles', type=int, default=20)
    ap.add_argument('--min-expected', type=float, default=3.0)
    args = ap.parse_args()
    lang, genre, dates = load_meta()
    P = Profiles()
    info = {w: work_info(w, lang, genre, dates) for w in P.by_work}
    note = HOLDINGS
    topics = sorted({t for ts in P.topics_of.values() for t in ts})

    # coverage by work and by author
    prof, tot = {}, {}
    rows, rows_n = [], []
    for w in sorted(P.by_work):
        n, c = P.counts(P.by_work[w])
        prof[w], tot[w] = c, n
        for t, (na, npg) in sorted(c.items()):
            rows.append(['work', w, t[0], t[1], na, npg, n])
            rows_n.append(['work', w, t[0], t[1], na, n, round(na / n, 4)])
    by_author = defaultdict(set)
    for w, ids in P.by_work.items():
        by_author[info[w]['author']] |= ids
    for a in sorted(by_author):
        n, c = P.counts(by_author[a])
        for t, (na, npg) in sorted(c.items()):
            rows.append(['author', a, t[0], t[1], na, npg, n])
            rows_n.append(['author', a, t[0], t[1], na, n, round(na / n, 4)])
    write_csv('coverage.csv', ['level', 'name', 'topic_type', 'topic', 'articles', 'pages', 'total_articles'], rows)
    write_csv('coverage_norm.csv', ['level', 'name', 'topic_type', 'topic', 'articles', 'total_articles',
                                    'share_of_total'], rows_n)

    # neighbours: same language, and same genre or same era+meter; then profile correlation
    def vec(w):
        return [prof[w].get(t, [0, 0])[0] / tot[w] for t in topics]
    big = [w for w in P.by_work if tot[w] >= args.min_articles]
    raw = {w: vec(w) for w in big}
    # Centre on the average work: otherwise every pair of works correlates highly because
    # textual criticism and the like dominate everywhere (median r was 0.80 uncentred).
    mean = [sum(raw[w][i] for w in big) / len(big) for i in range(len(topics))]
    vecs = {w: [x - m for x, m in zip(raw[w], mean)] for w in big}
    neigh = defaultdict(list)
    nrows = []
    for w in big:
        iw = info[w]
        for v in big:
            if v == w:
                continue
            iv = info[v]
            if iv['language'] != iw['language']:
                continue
            same_genre = iv['genre'] == iw['genre'] and iw['genre'] != 'unclassified'
            same_form = iv['era'] == iw['era'] and iv['meter'] == iw['meter'] and iw['meter'] != 'unknown'
            if not (same_genre or same_form):
                continue
            r = pearson(vecs[w], vecs[v])
            keep = r >= args.corr
            nrows.append([w, v, iw['language'], iw['genre'], iv['genre'], iw['era'], iv['era'],
                          'genre' if same_genre else 'era+meter', round(r, 3), tot[w], tot[v],
                          'yes' if keep else 'no'])
            if keep:
                neigh[w].append(v)
    write_csv('neighbours.csv', ['work', 'candidate', 'language', 'genre', 'candidate_genre', 'era',
                                 'candidate_era', 'grouped_by', 'profile_correlation', 'work_articles',
                                 'candidate_articles', 'neighbour'], nrows)

    # gaps
    grows = []
    for w in big:
        ns = neigh.get(w, [])
        if not ns:
            continue
        wt = sum(tot[n] for n in ns)
        for t in topics:
            exp_share = sum(prof[n].get(t, [0, 0])[0] for n in ns) / wt
            obs = prof[w].get(t, [0, 0])[0]
            exp_n = exp_share * tot[w]
            if exp_n < args.min_expected:
                continue
            score = (exp_n - obs) / math.sqrt(exp_n)
            grows.append([w, t[0], t[1], tot[w], obs, round(obs / tot[w], 4), round(exp_share, 4),
                          round(exp_n, 1), round(score, 2), len(ns), wt])
    grows.sort(key=lambda r: -r[8])
    write_csv('gaps.csv', ['work', 'topic_type', 'topic', 'work_articles', 'observed_articles',
                           'observed_share', 'expected_share', 'expected_articles', 'gap_score',
                           'neighbours', 'neighbour_articles'], grows)
    meta_rows = [[w] + [info[w][k] for k in ('author', 'language', 'era', 'meter', 'genre')] + [tot[w]]
                 for w in sorted(info)]
    write_csv('work_metadata.csv', ['work', 'author', 'language', 'era', 'meter', 'genre', 'articles'],
              meta_rows)
    json.dump({'holdings': note, 'corr_threshold': args.corr, 'min_articles': args.min_articles,
               'min_expected': args.min_expected, 'labelled_articles': len(P.lab),
               'works_with_articles': len(P.by_work), 'works_ge_min': len(big),
               'works_with_neighbours': len(neigh), 'gap_rows': len(grows)},
              open(os.path.join(OUT, 'tables_summary.json'), 'w'), indent=1)
    print(json.dumps(json.load(open(os.path.join(OUT, 'tables_summary.json')))))


if __name__ == '__main__':
    main()
