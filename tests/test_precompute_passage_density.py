"""scripts/precompute_passage_density.py: argument handling and the
"skip when already cached" logic.

No real passage index is loaded here (that is multi-gigabyte and not present
in CI) -- discover_works() is exercised against a monkeypatched _records list,
the same stubbing pattern tests/test_density_cache.py and
tests/test_passages_works_route.py already use, and process_density() /
process_lexical() are exercised against a temporary cache directory with a
monkeypatched compute function, so a "cached" decision never actually calls
backend.passage_index.connection_density() or
backend.lexical_density.line_density().
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'scripts'))

from backend import lexical_density  # noqa: E402
from backend import passage_index  # noqa: E402
import precompute_passage_density as ppd  # noqa: E402


# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------

def test_defaults():
    args = ppd.build_parser().parse_args([])
    assert args.language == 'all'
    assert args.only_missing is True
    assert args.force is False
    assert args.limit is None
    assert args.dry_run is False
    assert args.lexical is False


def test_language_choices_are_restricted():
    args = ppd.build_parser().parse_args(['--language', 'la'])
    assert args.language == 'la'
    try:
        ppd.build_parser().parse_args(['--language', 'nonsense'])
        assert False, 'an unknown language should be rejected'
    except SystemExit:
        pass


def test_force_and_limit_and_dry_run_and_lexical_flags():
    args = ppd.build_parser().parse_args(
        ['--force', '--limit', '3', '--dry-run', '--lexical', '--language', 'grc'])
    assert args.force is True
    assert args.limit == 3
    assert args.dry_run is True
    assert args.lexical is True
    assert args.language == 'grc'


# ---------------------------------------------------------------------------
# discover_works(): pulled from the loaded index, skips windowless entries
# ---------------------------------------------------------------------------

def _stub_records(monkeypatch, records):
    monkeypatch.setitem(passage_index._state, 'loaded', True)
    monkeypatch.setitem(passage_index._state, 'ok', True)
    monkeypatch.setitem(passage_index._state, 'error', None)
    monkeypatch.setattr(passage_index, '_records', records)
    monkeypatch.setattr(passage_index, '_ensure_loaded', lambda: None)


def test_discover_works_uses_raw_per_part_work_ids(monkeypatch):
    _stub_records(monkeypatch, [
        {'id': 'a', 'language': 'la', 'work': 'vergil.aeneid.part.1'},
        {'id': 'b', 'language': 'la', 'work': 'vergil.aeneid.part.1'},
        {'id': 'c', 'language': 'la', 'work': 'vergil.aeneid.part.2'},
        {'id': 'd', 'language': 'grc', 'work': 'homer.iliad.part.1'},
    ])
    by_lang = ppd.discover_works()
    assert by_lang['la'] == ['vergil.aeneid.part.1', 'vergil.aeneid.part.2']
    assert by_lang['grc'] == ['homer.iliad.part.1']


def test_discover_works_filters_by_language(monkeypatch):
    _stub_records(monkeypatch, [
        {'id': 'a', 'language': 'la', 'work': 'ovid.metamorphoses'},
        {'id': 'b', 'language': 'grc', 'work': 'homer.iliad.part.1'},
    ])
    by_lang = ppd.discover_works(['la'])
    assert by_lang == {'la': ['ovid.metamorphoses']}


def test_discover_works_skips_records_with_no_work_or_language(monkeypatch):
    _stub_records(monkeypatch, [
        {'id': 'a', 'language': 'la', 'work': 'ovid.metamorphoses'},
        {'id': 'b', 'language': None, 'work': 'ghost.text'},
        {'id': 'c', 'language': 'la', 'work': None},
    ])
    by_lang = ppd.discover_works()
    assert by_lang == {'la': ['ovid.metamorphoses']}


def test_discover_works_raises_when_index_unavailable(monkeypatch):
    monkeypatch.setitem(passage_index._state, 'loaded', True)
    monkeypatch.setitem(passage_index._state, 'ok', False)
    monkeypatch.setitem(passage_index._state, 'error', 'index not built')
    monkeypatch.setattr(passage_index, '_ensure_loaded', lambda: None)
    try:
        ppd.discover_works()
        assert False, 'should have raised when the index is unavailable'
    except RuntimeError as e:
        assert 'index not built' in str(e)


# ---------------------------------------------------------------------------
# process_density(): skip-when-cached / force logic, no real computation
# ---------------------------------------------------------------------------

def test_process_density_skips_when_already_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))
    cache_path = passage_index._density_cache_path('some.work', ppd.DENSITY_SCALE)
    with open(cache_path, 'w', encoding='utf-8') as fh:
        json.dump({'work': 'some.work', 'windows': []}, fh)

    calls = []
    monkeypatch.setattr(passage_index, 'connection_density',
                        lambda work, scale='fine': calls.append(work))

    status = ppd.process_density('some.work', force=False)
    assert status == 'skipped_cached'
    assert not calls, 'a cached work must not call connection_density()'


def test_process_density_computes_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))

    calls = []
    monkeypatch.setattr(passage_index, 'connection_density',
                        lambda work, scale='fine': calls.append((work, scale)))

    status = ppd.process_density('new.work', force=False)
    assert status == 'computed'
    assert calls == [('new.work', ppd.DENSITY_SCALE)]


def test_process_density_force_recomputes_and_removes_stale_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))
    cache_path = passage_index._density_cache_path('some.work', ppd.DENSITY_SCALE)
    with open(cache_path, 'w', encoding='utf-8') as fh:
        json.dump({'work': 'some.work', 'windows': []}, fh)

    calls = []

    def fake_connection_density(work, scale='fine'):
        calls.append((work, scale))
        # the real function would rewrite the cache file; simulate that
        with open(cache_path, 'w', encoding='utf-8') as fh:
            json.dump({'work': work, 'windows': [], 'recomputed': True}, fh)

    monkeypatch.setattr(passage_index, 'connection_density', fake_connection_density)

    status = ppd.process_density('some.work', force=True)
    assert status == 'computed'
    assert calls == [('some.work', ppd.DENSITY_SCALE)]


def test_process_density_catches_and_reports_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))

    def boom(work, scale='fine'):
        raise RuntimeError('boom')

    monkeypatch.setattr(passage_index, 'connection_density', boom)
    status = ppd.process_density('broken.work', force=False)
    assert status == 'failed'


# ---------------------------------------------------------------------------
# process_lexical(): same skip-when-cached contract, other module
# ---------------------------------------------------------------------------

def test_process_lexical_skips_when_already_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(lexical_density, '_CACHE_DIR', str(tmp_path))
    cache_path = lexical_density._cache_path('some.work', 'la')
    with open(cache_path, 'w', encoding='utf-8') as fh:
        json.dump({'work': 'some.work', 'lines': []}, fh)

    calls = []
    monkeypatch.setattr(lexical_density, 'line_density',
                        lambda work, language='la', use_cache=True: calls.append(work))

    status = ppd.process_lexical('some.work', 'la', force=False)
    assert status == 'skipped_cached'
    assert not calls, 'a cached work must not call line_density()'


def test_process_lexical_computes_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(lexical_density, '_CACHE_DIR', str(tmp_path))

    calls = []
    monkeypatch.setattr(
        lexical_density, 'line_density',
        lambda work, language='la', use_cache=True: calls.append((work, language, use_cache)))

    status = ppd.process_lexical('new.work', 'grc', force=False)
    assert status == 'computed'
    assert calls == [('new.work', 'grc', True)]


def test_process_lexical_force_bypasses_cache_read(monkeypatch, tmp_path):
    monkeypatch.setattr(lexical_density, '_CACHE_DIR', str(tmp_path))
    cache_path = lexical_density._cache_path('some.work', 'la')
    with open(cache_path, 'w', encoding='utf-8') as fh:
        json.dump({'work': 'some.work', 'lines': []}, fh)

    calls = []
    monkeypatch.setattr(
        lexical_density, 'line_density',
        lambda work, language='la', use_cache=True: calls.append((work, language, use_cache)))

    status = ppd.process_lexical('some.work', 'la', force=True)
    assert status == 'computed'
    assert calls == [('some.work', 'la', False)]


def test_process_lexical_catches_and_reports_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(lexical_density, '_CACHE_DIR', str(tmp_path))

    def boom(work, language='la', use_cache=True):
        raise RuntimeError('boom')

    monkeypatch.setattr(lexical_density, 'line_density', boom)
    status = ppd.process_lexical('broken.work', 'la', force=False)
    assert status == 'failed'


# ---------------------------------------------------------------------------
# main(): dry-run wiring end to end against a stubbed index
# ---------------------------------------------------------------------------

def test_main_dry_run_lists_targets_and_computes_nothing(monkeypatch, tmp_path, capsys):
    _stub_records(monkeypatch, [
        {'id': 'a', 'language': 'la', 'work': 'ovid.metamorphoses.part.1'},
        {'id': 'b', 'language': 'la', 'work': 'ovid.metamorphoses.part.2'},
    ])
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))

    calls = []
    monkeypatch.setattr(passage_index, 'connection_density',
                        lambda work, scale='fine': calls.append(work))

    rc = ppd.main(['--dry-run', '--language', 'la'])
    assert rc == 0
    assert not calls, 'dry-run must not compute anything'
    out = capsys.readouterr().out
    assert 'ovid.metamorphoses.part.1' in out
    assert 'ovid.metamorphoses.part.2' in out
    assert '2 work(s) would be processed' in out
