#!/usr/bin/env python3
"""Print every URL rule of the Flask app, one per line, for comparing two versions of the code.

    python3 scripts/review/url_map_dump.py            # sorted: "METHODS path -> endpoint"
    python3 scripts/review/url_map_dump.py --ordered  # in the order the rules were registered
    python3 scripts/review/url_map_dump.py --columns paths   # only "METHODS path" (no endpoint)

Run it on main and on a branch and compare the two outputs. A refactor that moves
routes into blueprints changes the endpoint column by a prefix (line_search becomes
line_search.line_search) and must change nothing else. Set TESSERAE_DIRECT_SERVER=1
to dump the map as the development server (with the /api prefix) builds it.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
os.environ.setdefault('SESSION_SECRET', 'url-map-dump-throwaway')
os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/url_map_dump.db')


def main():
    ordered = '--ordered' in sys.argv
    paths_only = '--columns' in sys.argv and 'paths' in sys.argv
    import contextlib
    with contextlib.redirect_stdout(sys.stderr):  # start-up log lines go to stderr
        from backend.app import app
    rows = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(m for m in (rule.methods or ()) if m not in ('HEAD', 'OPTIONS')))
        row = f"{methods} {rule.rule}" if paths_only else f"{methods} {rule.rule} -> {rule.endpoint}"
        rows.append(row)
    if not ordered:
        rows.sort()
    print('\n'.join(rows))


if __name__ == '__main__':
    main()
