#!/usr/bin/env python3
"""Read-only usage report from the search_logs table, outside use only.

Prints, for a date range (--since, default 30 days back), searches by month and
by search type with the server's own requests (internal rows) left out, the
number of distinct addresses, and the Theme Search rows by scope, by whether the
reader re-ordered the results, and the twenty most common questions. It reads
DATABASE_URL from the process environment and never prints it.

    (set -a; . /var/www/tesseraev6_flask/.env; set +a; venv/bin/python scripts/review/usage_report.py)
    ... usage_report.py --since 2026-10-01
"""
import argparse
import datetime
import os
import sys

import psycopg2


def _since(text):
    if text:
        return datetime.date.fromisoformat(text)
    return datetime.date.today() - datetime.timedelta(days=30)


def _print(title, rows, headers):
    print(f'\n{title}')
    if not rows:
        print('  (none)')
        return
    print('  ' + '  '.join(headers))
    for r in rows:
        print('  ' + '  '.join(str(x) for x in r))


def report(cur, since):
    base = "created_at >= %s AND internal IS NOT TRUE"
    cur.execute(f"SELECT COUNT(*) FROM search_logs WHERE {base}", (since,))
    outside = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM search_logs WHERE created_at >= %s AND internal IS TRUE", (since,))
    internal = cur.fetchone()[0]
    print(f'Search log since {since}: {outside} outside searches, {internal} internal rows left out.')

    cur.execute(f"SELECT to_char(created_at, 'YYYY-MM'), COUNT(*) FROM search_logs WHERE {base} "
                "GROUP BY 1 ORDER BY 1", (since,))
    _print('Searches by month', cur.fetchall(), ['month', 'searches'])

    cur.execute(f"SELECT search_type, COUNT(*) FROM search_logs WHERE {base} "
                "GROUP BY 1 ORDER BY 2 DESC", (since,))
    _print('Searches by type', cur.fetchall(), ['type', 'searches'])

    cur.execute(f"SELECT COUNT(DISTINCT client_ip) FROM search_logs WHERE {base}", (since,))
    print(f'\nDistinct addresses: {cur.fetchone()[0]}')

    theme = f"{base} AND search_type = 'Theme Search'"
    cur.execute(f"SELECT split_part(match_type, ',', 1), COUNT(*) FROM search_logs WHERE {theme} "
                "GROUP BY 1 ORDER BY 2 DESC", (since,))
    _print('Theme Search by scope', cur.fetchall(), ['scope', 'searches'])

    cur.execute(f"SELECT (match_type LIKE '%%, reader%%'), COUNT(*) FROM search_logs WHERE {theme} "
                "GROUP BY 1 ORDER BY 1 DESC", (since,))
    _print('Theme Search by reader applied',
           [('applied' if a else 'not applied', n) for a, n in cur.fetchall()], ['reader', 'searches'])

    cur.execute(f"SELECT query_text, COUNT(*) FROM search_logs WHERE {theme} AND query_text IS NOT NULL "
                "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 20", (since,))
    _print('Top twenty Theme Search questions', cur.fetchall(), ['question', 'times'])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--since', help='first day to include, YYYY-MM-DD (default: 30 days back)')
    args = ap.parse_args()
    url = os.environ.get('DATABASE_URL')
    if not url:
        sys.exit('DATABASE_URL is not set in the environment.')
    conn = psycopg2.connect(url)
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            report(cur, _since(args.since))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
