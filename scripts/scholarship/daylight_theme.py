"""Daylight prototype, the Theme Search angle.

daylight_theme(query) runs the existing scholarship theme search for a phrase
and groups the article windows it returns by the work they cite, normalised by
each work's total articles in the citation index. It returns tables only (work,
articles returned, work total, share); no article text.

Rests on the JSTOR Early Journal Content holdings (1827 to 1922).
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend import scholarship_theme  # noqa: E402
from daylight_common import connect  # noqa: E402

PROD_DIR = '/var/www/tesseraev6_flask/data/scholarship_theme'


def work_totals():
    con = connect()
    return {w: n for w, n in con.execute(
        'select work_id, count(distinct article_id) from citations where work_id is not null group by 1')}


def daylight_theme(query, depth=300, min_total=20):
    """Works ranked by (distinct articles among the `depth` best windows) / (work's total articles)."""
    os.environ.setdefault('TESSERAE_SCHOLARSHIP_THEME_DIR', PROD_DIR)
    old = (scholarship_theme.MAX_K, scholarship_theme.DEEP)
    scholarship_theme.MAX_K, scholarship_theme.DEEP = depth, max(2 * depth, 600)
    try:
        res = scholarship_theme.theme(query, k=depth)
    finally:
        scholarship_theme.MAX_K, scholarship_theme.DEEP = old
    totals = work_totals()
    seen = defaultdict(set)
    for c in res.get('results', []):
        if c.get('kind') == 'article' and c.get('work'):
            seen[c['work'].split('.part.')[0]].add((c.get('link') or {}).get('url') or c['id'])
    rows = [{'work': w, 'articles_returned': len(a), 'work_articles': totals.get(w, 0),
             'share': round(len(a) / totals[w], 4)} for w, a in seen.items() if totals.get(w, 0) >= min_total]
    rows.sort(key=lambda r: -r['share'])
    return {'query': query, 'depth': depth, 'windows_returned': len(res.get('results', [])), 'rows': rows}
