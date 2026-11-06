# scripts/review

Read-only checks and reports for the maintainers.

## usage_report.py

Outside use of the site from the `search_logs` table (the server's own requests, flagged `internal`, are left out): searches by month and type, distinct addresses, and Theme Search by scope, reader applied or not, and the top twenty questions. It reads `DATABASE_URL` from the process environment and does not print it.

    (set -a; . /var/www/tesseraev6_flask/.env; set +a; venv/bin/python scripts/review/usage_report.py)

Add `--since YYYY-MM-DD` for a different start (default: 30 days back).

The golden-record scripts in this folder are described in `README_GOLDEN.md`.
