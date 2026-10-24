#!/usr/bin/env python
"""Run the oldest queued comparison download, one job per start (2026-10-24).

A pair of works above COMPARE_MAX_LINE_PAIRS is not run live; a visitor can
queue it instead (backend/blueprints/comparison_jobs.py). A systemd user timer
starts this script every five minutes inside
`systemd-run --user --scope --slice tesserae-jobs.slice -p MemoryMax=20G -p MemorySwapMax=0` (see
server/systemd/README.md). Each start:

  1. takes a lock, so two runners never overlap;
  2. marks a job still "running" with no runner alive as failed (the runner was
     killed, most likely at the memory cap), so it is not retried in a loop;
  3. removes jobs and files older than 14 days;
  4. finds the oldest queued job and, before taking it, checks that
     MemAvailable is at least 26 GB and that no tess-job scope is running,
     else exits quietly for the timer's next tick;
  5. runs the comparison through the same code the live route uses
     (backend/blueprints/fusion.py iter_pair_events, window pass on: mode
     merged unless the page sent another) with NO row cap (max_results 0, so
     every scored pair the pipeline keeps is written), writes
     data/comparison_jobs/<id>.csv (gzip when over 20 MB), marks it done,
     leaves the top rows (the page's own cap) in the results cache under the
     page's key so the pair opens on the page at once, and mails the visitor if
     an address was given and the site can send mail.

A job killed at the memory cap cannot record its own end: the next start finds
it still "running" and marks it failed, never retried.

Usage: comparison_queue_runner.py [--once-id ID] [--no-checks]
(--once-id runs that job whatever its status, --no-checks skips the memory and
tess-job checks, both for a manual check)
"""
import argparse
import fcntl
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RETENTION_DAYS = 14
MIN_AVAILABLE_GB = 26
KILLED_MESSAGE = 'too large even for the queue, compare book by book'
GZIP_OVER_BYTES = 20 * 1024 * 1024
JOBS_DIR = os.path.join(ROOT, 'data', 'comparison_jobs')


def log(msg):
    print(f"{datetime.now().isoformat(timespec='seconds')} {msg}", flush=True)


def open_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.models import ComparisonJob
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise SystemExit('DATABASE_URL is not set')
    engine = create_engine(url, pool_pre_ping=True)
    ComparisonJob.__table__.create(engine, checkfirst=True)
    return Session(engine)


def remove_file(path):
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def clean_up(session):
    """Fail stale running jobs; delete jobs and files past retention."""
    from backend.models import ComparisonJob
    for job in session.query(ComparisonJob).filter_by(status='running').all():
        job.status = 'failed'
        job.finished = datetime.now()
        job.error = KILLED_MESSAGE
        log(f'job {job.id} was running with no runner alive: marked failed')
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for job in session.query(ComparisonJob).all():
        stamp = job.finished or job.created
        if stamp and stamp < cutoff:
            remove_file(job.file_path)
            session.delete(job)
            log(f'job {job.id} removed (older than {RETENTION_DAYS} days)')
    session.commit()
    # Files with no row (a job removed by hand) older than retention.
    if os.path.isdir(JOBS_DIR):
        limit = time.time() - RETENTION_DAYS * 86400
        for name in os.listdir(JOBS_DIR):
            path = os.path.join(JOBS_DIR, name)
            if name.endswith(('.csv', '.csv.gz')) and os.path.getmtime(path) < limit:
                remove_file(path)


def mem_available_gb():
    """MemAvailable from /proc/meminfo in GB, or None when it cannot be read."""
    try:
        with open('/proc/meminfo') as fh:
            for line in fh:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) / 1048576
    except (OSError, ValueError):
        pass
    return None


def tess_job_running():
    """True when a tess-job scope is running; None when systemctl cannot say."""
    try:
        out = subprocess.run(
            ['systemctl', '--user', 'list-units', '--type=scope', '--state=running',
             'tess-job-*', '--no-legend', '--plain'],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return any(line.strip() for line in out.stdout.splitlines())


def may_start():
    """(True, '') when memory and the job slice allow a heavy job now, else (False, reason)."""
    avail = mem_available_gb()
    if avail is None:
        return False, 'cannot read MemAvailable'
    if avail < MIN_AVAILABLE_GB:
        return False, f'MemAvailable {avail:.1f} GB is below {MIN_AVAILABLE_GB} GB'
    running = tess_job_running()
    if running is None:
        return False, 'cannot list tess-job scopes'
    if running:
        return False, 'a tess-job scope is running'
    return True, ''


def run_comparison(job):
    """Run the pair through the live route's code; return (results, metadata)."""
    from backend import runtime
    from backend.blueprints import fusion as fb
    from backend.cache import save_cached_results
    from backend.formula_filter import apply_formula_filter

    fb.init_fusion_blueprint(runtime.matcher, runtime.scorer, runtime.text_processor,
                             runtime.TEXTS_DIR, runtime.get_processed_units)
    data = {**json.loads(job.settings or '{}'), 'source': job.source, 'target': job.target,
            'language': job.language}
    data.pop('skip_cache', None)
    p = fb._stream_params(data)
    if fb._resolve_pair(p):
        raise RuntimeError('Text files not found')
    # The page's cache key (its cap), taken before the cap is lifted: the file is
    # the whole comparison, the cache entry the page's own top rows.
    cache_settings = fb._cache_key(p)
    page_cap = p.max_results
    p.max_results = 0       # no cap: every pair the pipeline keeps goes in the file

    source_units = runtime.get_processed_units(p.source_id, p.language, p.source_unit_type,
                                               runtime.text_processor)
    target_units = runtime.get_processed_units(p.target_id, p.language, p.target_unit_type,
                                               runtime.text_processor)
    if not source_units or not target_units:
        raise RuntimeError('Could not process text units')
    log(f'{len(source_units)} x {len(target_units)} units, mode={p.mode}')
    results, total = None, None
    last = 0.0
    for event_type, evt in fb.iter_pair_events(p, source_units, target_units):
        if event_type == 'complete':
            results, total = evt['results'], evt.get('total_results')
        elif event_type in ('parts', 'channel_done') and time.time() - last > 60:
            last = time.time()
            log(f'{event_type}: {json.dumps({k: v for k, v in evt.items() if k != "results"})[:200]}')
    if results is None:
        raise RuntimeError('The comparison produced no result')
    meta = {'source_lines': len(source_units), 'target_lines': len(target_units),
            'mode': p.mode, 'total_candidates': total}
    # The entry the live route would have stored (the top rows, in score order, at
    # the page's cap), so the pair opens on the page at once.
    save_cached_results(p.source_id, p.target_id, p.language, cache_settings,
                        results[:page_cap], meta)
    log(f'{len(results)} rows scored; {min(len(results), page_cap)} kept for the page cache')
    results, _hidden = apply_formula_filter(results, p.formula_max, p.formula_only)
    return results, meta


def write_output(job, results):
    from backend.comparison_csv import write_csv
    os.makedirs(JOBS_DIR, exist_ok=True)
    path = os.path.join(JOBS_DIR, f'{job.id}.csv')
    rows = write_csv(path, results)
    if os.path.getsize(path) > GZIP_OVER_BYTES:
        gz = path + '.gz'
        with open(path, 'rb') as src, gzip.open(gz, 'wb') as dst:
            shutil.copyfileobj(src, dst)
        os.remove(path)
        path = gz
    return path, rows


def notify(job):
    """Mail the visitor when an address was given and the site can send mail."""
    if not job.email:
        return
    from backend.email_notifications import send_visitor_email
    site = os.environ.get('SITE_URL', 'https://tesserae.caset.buffalo.edu').rstrip('/')
    body = (f'Your comparison of {job.source} and {job.target} is ready.\n\n'
            f'{site}/comparisons/{job.id}\n\n'
            f'The file is kept for {RETENTION_DAYS} days.\n')
    if send_visitor_email(job.email, 'Your comparison is ready', body):
        log('visitor mailed')
    else:
        log('visitor not mailed (no mail host configured or sending failed)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once-id', help='run this job id whatever its status')
    ap.add_argument('--no-checks', action='store_true', help='skip the memory and tess-job checks')
    args = ap.parse_args()

    os.makedirs(JOBS_DIR, exist_ok=True)
    lock = open(os.path.join(JOBS_DIR, 'runner.lock'), 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log('another runner holds the lock; nothing to do')
        return 0

    from backend.models import ComparisonJob
    session = open_session()
    clean_up(session)
    if args.once_id:
        job = session.get(ComparisonJob, args.once_id)
    else:
        job = (session.query(ComparisonJob).filter_by(status='queued')
               .order_by(ComparisonJob.created).first())
    if job is None:
        log('no queued job')
        return 0
    if not args.no_checks:
        ok, why = may_start()
        if not ok:
            log(f'not starting job {job.id}: {why}')
            return 0

    job.status = 'running'
    job.started = datetime.now()
    session.commit()
    log(f'job {job.id}: {job.source} x {job.target} ({job.language})')
    try:
        results, _meta = run_comparison(job)
        path, rows = write_output(job, results)
        job.status, job.file_path, job.rows = 'done', path, rows
        job.finished, job.error = datetime.now(), None
        session.commit()
        log(f'job {job.id} done: {rows} rows, {os.path.getsize(path)} bytes')
        notify(job)
    except Exception as e:
        traceback.print_exc()
        job.status, job.finished = 'failed', datetime.now()
        job.error = str(e)[:500]
        session.commit()
        log(f'job {job.id} failed: {e}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
