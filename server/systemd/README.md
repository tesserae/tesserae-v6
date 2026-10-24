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

- Runs from the production checkout: the interpreter
  `/var/www/tesseraev6_flask/venv/bin/python` and the script
  `/var/www/tesseraev6_flask/scripts/comparison_queue_runner.py`, with
  `WorkingDirectory=/var/www/tesseraev6_flask`, so a deploy updates the runner.
- Reads `DATABASE_URL` from `/var/www/tesseraev6_flask/.env` with
  `EnvironmentFile=`; the file keeps its mode 664.
- Runs the job inside `systemd-run --user --scope --slice tesserae-jobs.slice
  -p MemoryMax=20G -p MemorySwapMax=0`. Whole-epic pairs measured over 12 GB
  with the window pass on (the Aeneid against the Metamorphoses was killed at
  12 GB), so the scope gets 20 GB. The slice (`~/.config/systemd/user/
  tesserae-jobs.slice`) must allow it: `MemoryMax=24G` today, which holds while
  no other job overlaps.
- Before taking a job the runner checks that `MemAvailable` is at least 26 GB and
  that no `tess-job-*` scope is running
  (`systemctl --user list-units --type=scope --state=running 'tess-job-*'`).
  If either fails, or systemctl cannot answer, it logs the reason and exits for
  the timer's next tick. The job stays queued. `--no-checks` skips this for a
  manual run.
- A job killed at the cap cannot record its own end. The next start finds it
  still `running`, marks it failed with "too large even for the queue, compare
  book by book", and never retries it.
- The file is the whole comparison: no row cap (`max_results` 0), every scored
  pair the pipeline keeps. Gzip applies over 20 MB. The results cache receives
  only the page's own top rows.
- One job per start. The timer waits five minutes after the unit finishes
  (`OnUnitInactiveSec`), and the runner holds `data/comparison_jobs/runner.lock`.
- Removes jobs and files older than 14 days at every start.
- Writes its log to `~/tesserae-backups/jobs/comparison_queue.log`.

## Mail

The visitor's email box on the page, and the runner's mail step, depend on one
setting, `VISITOR_MAIL_ENABLED`, read from the environment and true only for the
value `1` (default off). `SMTP_HOST` is not the test: production sets it to
`localhost` for the administrators' notices, and a test message sent through
that relay to an outside Gmail address never arrived. Turn the setting on only
after a relay that reaches outside addresses is configured (`SMTP_HOST`, and if
needed `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_FROM`),
then reload. With it off the status page, `/comparisons/<id>`, and the "Your
prepared comparisons" list on the Compare page are the notice.

## Limit

`COMPARE_MAX_LINE_PAIRS` (environment, default 12000000) is read on every
request; no restart is needed beyond the one that loads the `.env`.
