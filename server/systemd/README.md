# Systemd units for the comparison download queue

`tess-comparison-queue.service` and `tess-comparison-queue.timer` run
`scripts/comparison_queue_runner.py` every five minutes. The runner takes the
oldest queued job in the `comparison_jobs` table, runs it, and writes
`data/comparison_jobs/<id>.csv`. See `backend/blueprints/comparison_jobs.py`
for the routes and `backend/compare_limit.py` for the size limit.

## Install (as the account that runs the site services)

```
mkdir -p ~/.config/systemd/user ~/tesserae-backups/jobs
cp server/systemd/tess-comparison-queue.service server/systemd/tess-comparison-queue.timer ~/.config/systemd/user/
mkdir -p /var/www/tesseraev6_flask/data/comparison_jobs      # the runner also creates it
systemctl --user daemon-reload
systemctl --user enable --now tess-comparison-queue.timer
```

The table `comparison_jobs` is created by `db.create_all()` when the web app
starts (touch `tesseraev6_flask.wsgi` after the pull) and by the runner if it
starts first.

## What the unit does

- Reads `DATABASE_URL` from `/var/www/tesseraev6_flask/.env` with
  `EnvironmentFile=`; the file keeps its mode 664.
- Runs the job inside `systemd-run --user --scope -p MemoryMax=14G -p
  MemorySwapMax=0`, so an overrun kills the job and nothing else. The 14 GB is
  above the 12 GB cap `tess-job` allows for development jobs; the measured
  limit for a live comparison is 12 GB at a pair of 118 million lines.
- One job per start. The timer waits five minutes after the unit finishes
  (`OnUnitInactiveSec`), and the runner holds `data/comparison_jobs/runner.lock`.
- Removes jobs and files older than 14 days at every start.
- Writes its log to `~/tesserae-backups/jobs/comparison_queue.log`.

## Mail

The visitor's email box on the page appears only when `SMTP_HOST` is set in the
`.env` (the site's own administrator notices fall back to a local relay, which
cannot be assumed to deliver to outside addresses). Set `SMTP_HOST`, and if
needed `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_FROM`,
then reload. Without it the status page, `/comparisons/<id>`, is the notice.

## Limit

`COMPARE_MAX_LINE_PAIRS` (environment, default 12000000) is read on every
request; no restart is needed beyond the one that loads the `.env`.
