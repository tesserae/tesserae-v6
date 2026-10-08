#!/usr/bin/env python3
"""Usage summary across the search log and the usage events table.

    venv/bin/python scripts/usage_stats.py [--since 2026-01-01]

Counts distinct visitors (address or account) and events by kind, month and
country, excluding the UB campus range and localhost. Prints only aggregates.
"""
import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
import psycopg2  # noqa: E402

EXCLUDE = "(client_ip is null or (client_ip::text not like '128.205.%' and client_ip::text not in ('127.0.0.1', '::1')))"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='2026-01-01')
    a = ap.parse_args()
    con = psycopg2.connect(os.environ['DATABASE_URL']); cur = con.cursor()
    union = f"""
      select 'search:' || search_type as kind, language, coalesce(client_ip::text, user_id::text) as who, country, created_at
        from search_logs where created_at >= %s and {EXCLUDE}
      union all
      select kind, language, coalesce(client_ip::text, user_id::text), country, created_at
        from usage_events where created_at >= %s and source = 'site' and {EXCLUDE}
    """
    cur.execute(f"select kind, count(*), count(distinct who) from ({union}) u group by kind order by 2 desc", (a.since, a.since))
    print(f'Events since {a.since} (kind, events, visitors):')
    for k, n, v in cur.fetchall():
        print(f'  {k:32s} {n:7d} {v:6d}')
    cur.execute(f"select to_char(created_at, 'YYYY-MM'), count(*), count(distinct who) from ({union}) u group by 1 order by 1", (a.since, a.since))
    print('By month (events, visitors):')
    for m, n, v in cur.fetchall():
        print(f'  {m} {n:7d} {v:6d}')
    cur.execute(f"select country, count(distinct who) from ({union}) u where country is not null and country <> '' group by 1 order by 2 desc", (a.since, a.since))
    rows = cur.fetchall()
    print(f'Countries ({len(rows)}):', ', '.join(f'{c} {n}' for c, n in rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
