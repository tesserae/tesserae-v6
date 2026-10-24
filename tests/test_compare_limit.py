"""The size limit on live comparisons and the download queue (2026-10-24).

A pair above COMPARE_MAX_LINE_PAIRS is not run: the route answers with JSON
naming the per-book files and the queue. Texts here are tiny files in a
temporary corpus, and the line counts come from a fake table where the test is
about the arithmetic.
"""
import gzip
import importlib.util
import os
import sys
from datetime import datetime, timedelta

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import compare_limit, comparison_csv  # noqa: E402


@pytest.fixture(autouse=True)
def _no_limit_env(monkeypatch):
    monkeypatch.delenv(compare_limit.LIMIT_ENV, raising=False)
    monkeypatch.delenv('SMTP_HOST', raising=False)


def _table(counts):
    return lambda text_id: counts.get(text_id)


def _corpus(tmp_path, files):
    """texts/la/<name> with <n> lines each."""
    lang = tmp_path / 'texts' / 'la'
    lang.mkdir(parents=True)
    for name, n in files.items():
        (lang / name).write_text(''.join(f'<x. {i + 1}> line {i}\n' for i in range(n)), encoding='utf-8')
    return str(tmp_path / 'texts')


# ---- the limit -------------------------------------------------------------

def test_limit_defaults_to_twelve_million():
    assert compare_limit.max_line_pairs() == 12_000_000


def test_limit_reads_the_environment(monkeypatch):
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '100000')
    assert compare_limit.max_line_pairs() == 100_000
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '12,000,001')
    assert compare_limit.max_line_pairs() == 12_000_001
    for bad in ('', 'lots', '0', '-5'):
        monkeypatch.setenv(compare_limit.LIMIT_ENV, bad)
        assert compare_limit.max_line_pairs() == 12_000_000


def test_below_and_at_the_limit_run(tmp_path):
    counts = {'a.tess': 3000, 'b.tess': 4000}          # exactly 12,000,000
    assert compare_limit.check_size(str(tmp_path), 'la', 'a.tess', 'b.tess',
                                    line_count_fn=_table(counts)) is None
    counts['b.tess'] = 3999
    assert compare_limit.check_size(str(tmp_path), 'la', 'a.tess', 'b.tess',
                                    line_count_fn=_table(counts)) is None


def test_above_the_limit_returns_the_body(tmp_path):
    texts = _corpus(tmp_path, {'w.tess': 2, 'w.part.1.tess': 1, 'w.part.2.tess': 1,
                               'o.tess': 3, 'o.part.1.tess': 3})
    counts = {'w.tess': 4000, 'o.tess': 3001}          # 12,004,000
    body = compare_limit.check_size(texts, 'la', 'w.tess', 'o.tess', line_count_fn=_table(
        {**counts, 'w.part.1.tess': 2000, 'w.part.2.tess': 2000, 'o.part.1.tess': 3001}))
    assert body['too_large'] is True
    assert body['line_pairs'] == 12_004_000
    assert body['limit'] == 12_000_000
    assert body['download_job_url'] == '/api/comparisons/jobs'
    assert body['email_notice'] is False
    assert 'books' in body['message']
    listed = [(b['side'], b['id'], b['lines']) for b in body['books']]
    assert listed == [('source', 'w.part.1.tess', 2000), ('source', 'w.part.2.tess', 2000),
                      ('target', 'o.part.1.tess', 3001)]
    assert all(b['label'] for b in body['books'])


def test_a_book_file_lists_no_books(tmp_path):
    texts = _corpus(tmp_path, {'w.part.1.tess': 1, 'w.part.2.tess': 1, 'o.tess': 1})
    body = compare_limit.check_size(texts, 'la', 'w.part.1.tess', 'o.tess', line_count_fn=_table(
        {'w.part.1.tess': 5000, 'o.tess': 5000}))
    assert body['too_large'] and body['books'] == []


def test_the_limit_in_the_environment_moves_the_gate(tmp_path, monkeypatch):
    counts = _table({'a.tess': 300, 'b.tess': 400})
    assert compare_limit.check_size(str(tmp_path), 'la', 'a.tess', 'b.tess', line_count_fn=counts) is None
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '100000')
    assert compare_limit.check_size(str(tmp_path), 'la', 'a.tess', 'b.tess',
                                    line_count_fn=counts)['limit'] == 100_000


def test_a_missing_text_is_left_to_the_route(tmp_path):
    assert compare_limit.check_size(str(tmp_path), 'la', 'a.tess', 'gone.tess',
                                    line_count_fn=_table({'a.tess': 10 ** 9})) is None


def test_email_notice_follows_smtp_host(monkeypatch):
    assert compare_limit.email_notice_available() is False
    monkeypatch.setenv('SMTP_HOST', 'mail.example.edu')
    assert compare_limit.email_notice_available() is True


def test_line_count_counts_non_blank_lines_and_follows_the_file(tmp_path):
    texts = _corpus(tmp_path, {'a.tess': 7})
    path = tmp_path / 'texts' / 'la' / 'a.tess'
    path.write_text(path.read_text() + '\n\n', encoding='utf-8')
    assert compare_limit.text_line_count(texts, 'la', 'a.tess') == 7
    path.write_text(path.read_text() + '<x. 8> more\n', encoding='utf-8')
    assert compare_limit.text_line_count(texts, 'la', 'a.tess') == 8
    assert compare_limit.text_line_count(texts, 'la', 'nope.tess') is None


# ---- the comparison route --------------------------------------------------

def _fusion_client(monkeypatch, texts):
    from flask import Flask
    from backend.blueprints import fusion as fb
    monkeypatch.setattr(fb, '_texts_dir', texts)
    monkeypatch.setattr(fb, '_poll_use_meter', lambda *a: False)
    monkeypatch.setattr(fb, 'get_user_location', lambda: (None, None, None))
    monkeypatch.setattr(fb, 'current_user', None)
    app = Flask(__name__)
    app.register_blueprint(fb.fusion_bp)
    return app.test_client(), fb


def test_stream_route_answers_json_above_the_limit(monkeypatch, tmp_path):
    texts = _corpus(tmp_path, {'a.tess': 40, 'b.tess': 30, 'b.part.1.tess': 15, 'b.part.2.tess': 15})
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '1000')
    client, fb = _fusion_client(monkeypatch, texts)
    monkeypatch.setattr(fb, 'CACHE_DIR', str(tmp_path / 'cache'))
    resp = client.post('/search-fusion', json={'source': 'a.tess', 'target': 'b.tess', 'language': 'la'})
    assert resp.status_code == 200 and resp.mimetype == 'application/json'
    body = resp.get_json()
    assert body['too_large'] is True and body['line_pairs'] == 1200 and body['limit'] == 1000
    assert [b['id'] for b in body['books']] == ['b.part.1.tess', 'b.part.2.tess']


def test_stream_route_runs_below_the_limit(monkeypatch, tmp_path):
    texts = _corpus(tmp_path, {'a.tess': 40, 'b.tess': 30})
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '1200')
    client, fb = _fusion_client(monkeypatch, texts)
    monkeypatch.setattr(fb, 'CACHE_DIR', str(tmp_path / 'cache'))
    resp = client.post('/search-fusion', json={'source': 'a.tess', 'target': 'b.tess', 'language': 'la'})
    assert resp.mimetype == 'text/event-stream'
    resp.close()


def test_a_cached_pair_runs_whatever_its_size(monkeypatch, tmp_path):
    texts = _corpus(tmp_path, {'a.tess': 40, 'b.tess': 30})
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '1000')
    client, fb = _fusion_client(monkeypatch, texts)
    monkeypatch.setattr(fb, 'CACHE_DIR', str(tmp_path / 'cache'))
    body = {'source': 'a.tess', 'target': 'b.tess', 'language': 'la'}
    p = fb._stream_params(body)
    cache_file = tmp_path / 'cache' / (fb.get_cache_key('a.tess', 'b.tess', 'la', fb._cache_key(p)) + '.json')
    cache_file.parent.mkdir()
    cache_file.write_text('{}')
    resp = client.post('/search-fusion', json=body)
    assert resp.mimetype == 'text/event-stream'
    resp.close()
    # skip_cache asks for a fresh run, which the gate then refuses.
    again = client.post('/search-fusion', json={**body, 'skip_cache': True})
    assert again.get_json()['too_large'] is True


def test_poll_route_and_estimate_carry_the_answer(monkeypatch, tmp_path):
    texts = _corpus(tmp_path, {'a.tess': 40, 'b.tess': 30})
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '1000')
    client, fb = _fusion_client(monkeypatch, texts)
    monkeypatch.setattr(fb, 'CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setattr(fb, 'ensure_cache_dir', lambda: None)
    poll = client.get('/fusion-search?source=a.tess&target=b.tess&language=la').get_json()
    assert poll['status'] == 'too_large' and poll['line_pairs'] == 1200 and 'books' in poll['message']
    est = client.get('/fusion-estimate?source=a.tess&target=b.tess&language=la').get_json()
    assert est['too_large']['too_large'] is True and est['pairs'] == 1200


def test_the_connector_passes_the_answer_on(monkeypatch):
    from backend.blueprints import mcp_http
    monkeypatch.setattr(mcp_http, '_get', lambda path, params: {
        'status': 'too_large', 'message': 'say how to proceed', 'line_pairs': 5, 'limit': 1,
        'books': [{'side': 'source', 'id': 'a.part.1.tess'}]})
    out = mcp_http._fusion_poll({'source': 'a', 'target': 'b'}, 30)
    assert out['status'] == 'too_large' and out['note'] == 'say how to proceed'
    assert out['books'][0]['id'] == 'a.part.1.tess'


# ---- the CSV ---------------------------------------------------------------

ROWS = [
    {'fused_score': 1.5, 'channels': ['lemma', 'exact'],
     'source': {'ref': 'a 1.1', 'text': 'Arma virum <b>que</b> cano, Troiae'},
     'target': {'ref': 'b 2.2', 'text': 'virum "arma" tenet'},
     'matched_words': [{'lemma': 'arma', 'source_word': 'Arma', 'target_word': 'arma'},
                       {'lemma': 'vir', 'source_word': 'virum', 'target_word': 'virum'},
                       {'lemma': 'x~y (60%)'}]},
    {'fused_score': 3.25, 'channels': ['semantic'], 'source': {'ref': 'a 1.9', 'text': 'nihil'},
     'target': {'ref': 'b 9.9', 'text': 'nihil'}, 'matched_words': []},
]


def test_csv_rows_follow_the_page_export():
    rows = comparison_csv.result_rows(ROWS)
    assert rows[0][:2] == ['1', 'a 1.9'] and rows[0][5] == '3.250'
    second = rows[1]
    assert second[0] == '2' and second[1] == 'a 1.1'
    assert second[2] == '**Arma** **virum** que cano, Troiae'      # tags stripped, words marked
    assert second[4] == '**virum** "**arma**" tenet'
    assert second[6] == 'arma; vir; x~y (60%)' and second[7] == 'lemma; exact'


def test_csv_file_has_the_page_columns_and_a_byte_order_mark(tmp_path):
    path = tmp_path / 'out.csv'
    assert comparison_csv.write_csv(str(path), ROWS) == 2
    raw = path.read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf')
    first = raw.decode('utf-8-sig').splitlines()[0]
    assert first == ('"Rank","Source Locus","Source Text","Target Locus","Target Text",'
                     '"Score","Matched Words","Channels"')


# ---- the queue -------------------------------------------------------------

@pytest.fixture
def queue(monkeypatch, tmp_path):
    from flask import Flask
    from backend.models import db, ComparisonJob
    from backend.blueprints import comparison_jobs as cj
    texts = _corpus(tmp_path, {'a.tess': 40, 'b.tess': 30, 'tiny.tess': 3})
    monkeypatch.setenv(compare_limit.LIMIT_ENV, '1000')
    monkeypatch.setattr(cj, '_texts_dir', texts)
    monkeypatch.setattr(cj, 'JOBS_DIR', str(tmp_path / 'jobs'))
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{tmp_path / 'q.db'}"
    app.config['TESTING'] = True
    app.register_blueprint(cj.comparison_jobs_bp)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app, ComparisonJob, db, tmp_path


BODY = {'source': 'a.tess', 'target': 'b.tess', 'language': 'la',
        'settings': {'max_results': 300, 'mode': 'merged', 'evil': 'x', 'use_meter': 'yes'}}


def test_a_job_is_queued_with_clean_settings_and_a_cookie(queue):
    app, Job, db, _ = queue
    client = app.test_client()
    resp = client.post('/comparisons/jobs', json=BODY)
    assert resp.status_code == 201
    job = resp.get_json()
    assert job['status'] == 'queued' and job['position'] == 1 and job['line_pairs'] == 1200
    assert 'tess_compare_token' in resp.headers.get('Set-Cookie', '')
    row = db.session.get(Job, job['id'])
    import json
    assert json.loads(row.settings) == {'max_results': 300, 'mode': 'merged'}
    assert row.owner_token and row.owner_token != client.get_cookie('tess_compare_token').value
    status = client.get(f"/comparisons/jobs/{job['id']}").get_json()
    assert status['status'] == 'queued' and 'download_url' not in status


def test_a_pair_under_the_limit_is_refused(queue):
    app, *_ = queue
    resp = app.test_client().post('/comparisons/jobs', json={**BODY, 'target': 'tiny.tess'})
    assert resp.status_code == 400 and resp.get_json()['runs_live'] is True


def test_a_visitor_may_have_two_waiting(queue):
    app, *_ = queue
    client = app.test_client()
    assert client.post('/comparisons/jobs', json=BODY).status_code == 201
    assert client.post('/comparisons/jobs', json=BODY).status_code == 201
    third = client.post('/comparisons/jobs', json=BODY)
    assert third.status_code == 429
    # Another visitor (no cookie) is not held back by the first one's two.
    assert app.test_client().post('/comparisons/jobs', json=BODY).status_code == 201


def test_the_queue_holds_twenty(queue):
    app, Job, db, _ = queue
    for i in range(20):
        db.session.add(Job(id=f'q{i:03d}abc', source='a.tess', target='b.tess', status='queued',
                           owner_token=f'o{i}', created=datetime.now()))
    db.session.commit()
    resp = app.test_client().post('/comparisons/jobs', json=BODY)
    assert resp.status_code == 503


def test_bad_requests(queue):
    app, *_ = queue
    c = app.test_client()
    assert c.post('/comparisons/jobs', json={'source': 'a.tess'}).status_code == 400
    assert c.post('/comparisons/jobs', json={**BODY, 'target': 'zzz.tess'}).status_code == 404
    assert c.post('/comparisons/jobs', json={**BODY, 'email': 'not an address'}).status_code == 400
    ok = c.post('/comparisons/jobs', json={**BODY, 'email': 'reader@example.edu'})
    assert ok.status_code == 201
    assert c.get('/comparisons/jobs/nosuchjob1').status_code == 404
    assert c.get('/comparisons/jobs/../../etc').status_code == 404


def test_download_waits_for_the_file_then_serves_it(queue):
    app, Job, db, tmp = queue
    client = app.test_client()
    job_id = client.post('/comparisons/jobs', json=BODY).get_json()['id']
    assert client.get(f'/comparisons/jobs/{job_id}/download').status_code == 409
    jobs_dir = tmp / 'jobs'
    jobs_dir.mkdir()
    path = jobs_dir / f'{job_id}.csv'
    comparison_csv.write_csv(str(path), ROWS)
    row = db.session.get(Job, job_id)
    row.status, row.file_path, row.rows, row.finished = 'done', str(path), 2, datetime.now()
    db.session.commit()
    status = client.get(f'/comparisons/jobs/{job_id}').get_json()
    assert status['status'] == 'done' and status['rows'] == 2
    assert status['download_url'] == f'/api/comparisons/jobs/{job_id}/download'
    got = client.get(f'/comparisons/jobs/{job_id}/download')
    assert got.status_code == 200 and got.mimetype == 'text/csv'
    assert b'"Rank"' in got.data
    # A file path outside the jobs folder is never served.
    row.file_path = str(tmp / 'texts' / 'la' / 'a.tess')
    db.session.commit()
    assert client.get(f'/comparisons/jobs/{job_id}/download').status_code == 410


def test_a_gzip_file_is_served_as_gzip(queue):
    app, Job, db, tmp = queue
    client = app.test_client()
    job_id = client.post('/comparisons/jobs', json=BODY).get_json()['id']
    (tmp / 'jobs').mkdir()
    path = tmp / 'jobs' / f'{job_id}.csv.gz'
    with gzip.open(path, 'wb') as fh:
        fh.write(b'Rank\n')
    row = db.session.get(Job, job_id)
    row.status, row.file_path, row.finished = 'done', str(path), datetime.now()
    db.session.commit()
    got = client.get(f'/comparisons/jobs/{job_id}/download')
    assert got.mimetype == 'application/gzip'
    assert 'csv.gz' in got.headers['Content-Disposition']


# ---- the runner ------------------------------------------------------------

def _runner():
    spec = importlib.util.spec_from_file_location(
        'comparison_queue_runner', os.path.join(PROJECT_ROOT, 'scripts', 'comparison_queue_runner.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_cleans_up_stale_and_old_jobs(monkeypatch, tmp_path):
    runner = _runner()
    monkeypatch.setattr(runner, 'JOBS_DIR', str(tmp_path / 'jobs'))
    (tmp_path / 'jobs').mkdir()
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'r.db'}")
    session = runner.open_session()
    from backend.models import ComparisonJob as Job
    old_file = tmp_path / 'jobs' / 'old.csv'
    old_file.write_text('x')
    now = datetime.now()
    session.add_all([
        Job(id='oldone1', source='a', target='b', status='done', created=now - timedelta(days=20),
            finished=now - timedelta(days=15), file_path=str(old_file)),
        Job(id='fresh1', source='a', target='b', status='done', created=now - timedelta(days=20),
            finished=now - timedelta(days=2)),
        Job(id='stuck1', source='a', target='b', status='running', created=now, started=now),
        Job(id='wait1', source='a', target='b', status='queued', created=now),
    ])
    session.commit()
    runner.clean_up(session)
    left = {j.id: j.status for j in session.query(Job).all()}
    assert left == {'fresh1': 'done', 'stuck1': 'failed', 'wait1': 'queued'}
    assert not old_file.exists()
    assert session.get(Job, 'stuck1').error == 'too large even for the queue, compare book by book'


def test_runner_writes_gzip_over_twenty_megabytes(monkeypatch, tmp_path):
    runner = _runner()
    monkeypatch.setattr(runner, 'JOBS_DIR', str(tmp_path / 'jobs'))
    monkeypatch.setattr(runner, 'GZIP_OVER_BYTES', 100)

    class J:
        id = 'big1'
    rows = [dict(ROWS[0], fused_score=i / 10) for i in range(20)]
    path, n = runner.write_output(J(), rows)
    assert path.endswith('.csv.gz') and n == 20 and not (tmp_path / 'jobs' / 'big1.csv').exists()
    with gzip.open(path, 'rt', encoding='utf-8-sig') as fh:
        assert fh.readline().startswith('"Rank"')


def test_visitor_email_is_sent_only_with_a_mail_host(monkeypatch):
    from backend import email_notifications as en
    assert en.send_visitor_email('a@b.edu', 's', 'b') is False        # no SMTP_HOST
    sent = []

    class Fake:
        def __init__(self, host, port, timeout=None): sent.append((host, port))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def sendmail(self, frm, to, msg): sent.append((to, 'Subject' in msg))

    monkeypatch.setenv('SMTP_HOST', 'mail.example.edu')
    monkeypatch.setattr(en.smtplib, 'SMTP', Fake)
    assert en.send_visitor_email('a@b.edu', 'ready', 'body') is True
    assert sent[0] == ('mail.example.edu', 25) and sent[1] == (['a@b.edu'], True)


def test_runner_lifts_the_row_cap_and_caches_only_the_pages_rows(monkeypatch, tmp_path):
    runner = _runner()
    from backend import runtime, cache
    from backend.blueprints import fusion as fb
    seen = {}

    def fake_events(p, su, tu, cancellation=None):
        seen['max_results'] = p.max_results
        rows = [{'fused_score': 9000 - i, 'source': {'ref': f's{i}', 'text': 'a'},
                 'target': {'ref': f't{i}', 'text': 'b'}} for i in range(6000)]
        yield ('complete', {'results': rows, 'total_results': 6000})

    saved = {}
    monkeypatch.setattr(fb, 'iter_pair_events', fake_events)
    monkeypatch.setattr(fb, '_resolve_pair', lambda p: None)
    monkeypatch.setattr(fb, '_poll_use_meter', lambda *a: False)
    monkeypatch.setattr(fb, 'init_fusion_blueprint', lambda *a, **k: None)
    monkeypatch.setattr(runtime, 'get_processed_units', lambda *a: ['unit'])
    monkeypatch.setattr(cache, 'save_cached_results',
                        lambda s, t, lang, settings, results, meta: saved.update(n=len(results), meta=meta, settings=settings))

    class J:
        source, target, language, settings = 'a.tess', 'b.tess', 'la', '{}'
    results, meta = runner.run_comparison(J())
    assert seen['max_results'] == 0               # no cap in the run
    assert len(results) == 6000                   # the file gets every row
    assert saved['n'] == 5000 and saved['settings']['max_results'] == 5000   # the page's key and cap
    assert meta['total_candidates'] == 6000


def test_runner_declines_without_memory_or_with_a_job_scope(monkeypatch):
    runner = _runner()
    monkeypatch.setattr(runner, 'mem_available_gb', lambda: 40.0)
    monkeypatch.setattr(runner, 'tess_job_running', lambda: False)
    assert runner.may_start() == (True, '')
    monkeypatch.setattr(runner, 'mem_available_gb', lambda: 25.9)
    ok, why = runner.may_start()
    assert not ok and '26' in why
    monkeypatch.setattr(runner, 'mem_available_gb', lambda: 40.0)
    monkeypatch.setattr(runner, 'tess_job_running', lambda: True)
    assert runner.may_start() == (False, 'a tess-job scope is running')
    monkeypatch.setattr(runner, 'tess_job_running', lambda: None)
    assert runner.may_start()[0] is False
    monkeypatch.setattr(runner, 'mem_available_gb', lambda: None)
    assert runner.may_start()[0] is False


def test_tess_job_scopes_are_listed_with_the_named_command(monkeypatch):
    runner = _runner()
    calls = []

    class Out:
        returncode, stdout = 0, 'tess-job-x-1.scope loaded active running /bin/x\n'
    monkeypatch.setattr(runner.subprocess, 'run', lambda cmd, **k: calls.append(cmd) or Out())
    assert runner.tess_job_running() is True
    assert calls[0][:6] == ['systemctl', '--user', 'list-units', '--type=scope', '--state=running', 'tess-job-*']
    Out.stdout = ''
    assert runner.tess_job_running() is False


def test_a_visitor_sees_only_their_own_recent_jobs(queue):
    app, Job, db, _ = queue
    a = app.test_client()
    assert a.get('/comparisons/jobs').get_json() == {'jobs': []}        # no cookie, no list
    first = a.post('/comparisons/jobs', json=BODY).get_json()['id']
    b = app.test_client()
    other = b.post('/comparisons/jobs', json=BODY).get_json()['id']
    old = Job(id='old0000abc', source='a.tess', target='b.tess', status='done', created=datetime.now() - timedelta(days=20),
              owner_token=db.session.get(Job, first).owner_token)
    db.session.add(old)
    db.session.commit()
    mine = a.get('/comparisons/jobs').get_json()['jobs']
    assert [j['id'] for j in mine] == [first]                           # not the other's, not the old one
    assert mine[0]['status'] == 'queued' and mine[0]['position'] == 1
    assert [j['id'] for j in b.get('/comparisons/jobs').get_json()['jobs']] == [other]
