"""backend/lemma_tables.py: the corrections file applied over the Latin lemma table (2026-10-18),
the shipped data files, the in-process lemmatizer, and the cache manifest's check."""
import csv
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import lemma_tables  # noqa: E402


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding='utf-8')


def test_correction_wins_over_the_table_and_other_forms_are_left_alone(tmp_path):
    _write(tmp_path / 'latin_lemmas.json', {'c': 'que', 'rex': 'rex', 'regem': 'rex'})
    _write(tmp_path / 'latin_corrections.json', {'c': 'c', 'actia': 'actius'})
    table = lemma_tables.load_latin_lemma_table(str(tmp_path / 'latin_lemmas.json'))
    assert table == {'c': 'c', 'rex': 'rex', 'regem': 'rex', 'actia': 'actius'}


def test_missing_corrections_file_gives_the_table_unchanged(tmp_path):
    _write(tmp_path / 'latin_lemmas.json', {'c': 'que', 'rex': 'rex'})
    table = lemma_tables.load_latin_lemma_table(str(tmp_path / 'latin_lemmas.json'))
    assert table == {'c': 'que', 'rex': 'rex'}
    assert lemma_tables.load_latin_corrections(str(tmp_path / 'latin_lemmas.json')) == {}


def test_missing_corrections_file_is_logged_once(tmp_path, caplog):
    _write(tmp_path / 'latin_lemmas.json', {'rex': 'rex'})
    caplog.set_level('INFO', logger='backend.lemma_tables')
    for _ in range(3):
        lemma_tables.load_latin_lemma_table(str(tmp_path / 'latin_lemmas.json'))
    assert sum('No Latin corrections file' in r.getMessage() for r in caplog.records) == 1


def test_shipped_files_are_sorted_folded_and_have_one_provenance_row_per_form():
    folder = os.path.join(ROOT, 'data', 'lemma_tables')
    corr = json.load(open(os.path.join(folder, 'latin_corrections.json'), encoding='utf-8'))
    from backend.latin_orthography import fold_latin
    assert list(corr) == sorted(corr)
    assert all(fold_latin(k) == k and fold_latin(v) == v for k, v in corr.items())
    rows = list(csv.DictReader(open(os.path.join(folder, 'latin_corrections_provenance.csv'), encoding='utf-8')))
    assert [r['form'] for r in rows] == list(corr)
    assert [r['lemma'] for r in rows] == list(corr.values())
    assert {r['source'] for r in rows} == {'hand', 'assimilated_prefix', 'parse_fill'}
    assert all(r['date'] == '2026-10-18' and r['evidence'] for r in rows)


def test_lemmatizer_gives_the_corrected_lemmas():
    from backend.text_processor import TextProcessor
    tp = TextProcessor()
    expected = {'c': 'c', 'facies': 'facies', 'actius': 'actius', 'actia': 'actius',
                'actiaque': 'actius', 'distrahor': 'distraho'}
    for form, lemma in expected.items():
        assert tp.lemmatize_word(form) == {lemma}, form
    # an unrelated form is unchanged
    assert tp.lemmatize_word('regem') == {'rex'}


def test_the_loader_and_the_server_table_agree():
    from backend.text_processor import get_latin_lemma_table
    assert get_latin_lemma_table() == lemma_tables.load_latin_lemma_table()


def _manifest_module():
    path = os.path.join(ROOT, 'scripts', 'corpus', 'lemma_cache_manifest.py')
    spec = importlib.util.spec_from_file_location('lemma_cache_manifest_lc', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_repo_and_cache(tmp_path, lcm):
    repo = tmp_path / 'repo'
    (repo / 'data' / 'lemma_tables').mkdir(parents=True)
    (repo / 'backend').mkdir()
    for rel in lcm.TABLES:
        (repo / rel).write_text('{"a": "b"}')
    (repo / lcm.TOKENIZER).write_text('# tokenizer\n')
    cache = tmp_path / 'cache'
    (cache / 'la').mkdir(parents=True)
    (cache / 'la' / 'x-1.json').write_text('{}')
    return repo, cache


def test_manifest_hashes_the_corrections_file_and_goes_stale_when_it_changes(tmp_path):
    lcm = _manifest_module()
    assert 'data/lemma_tables/latin_corrections.json' in lcm.TABLES
    repo, cache = _fake_repo_and_cache(tmp_path, lcm)
    lcm.write_manifest(str(cache), repo=str(repo))
    assert lcm.check_manifest(str(cache), repo=str(repo)) == []
    (repo / 'data' / 'lemma_tables' / 'latin_corrections.json').write_text('{"a": "c"}')
    reasons = lcm.check_manifest(str(cache), repo=str(repo))
    assert len(reasons) == 1 and 'latin_corrections.json' in reasons[0]


def test_manifest_written_before_the_corrections_file_existed_is_stale(tmp_path):
    lcm = _manifest_module()
    repo, cache = _fake_repo_and_cache(tmp_path, lcm)
    corrections = repo / 'data' / 'lemma_tables' / 'latin_corrections.json'
    corrections.unlink()
    lcm.write_manifest(str(cache), repo=str(repo))
    assert lcm.check_manifest(str(cache), repo=str(repo)) == []
    # the old manifest recorded the file as missing; now the file exists, so the cache lacks it
    corrections.write_text('{"a": "c"}')
    reasons = lcm.check_manifest(str(cache), repo=str(repo))
    assert len(reasons) == 1 and 'latin_corrections.json' in reasons[0]
    # a manifest with no entry at all for the file (the 2026-10-17 manifest) is stale too
    manifest_path = cache / lcm.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest['tables'] = [t for t in manifest['tables'] if not t['path'].endswith('latin_corrections.json')]
    manifest_path.write_text(json.dumps(manifest))
    reasons = lcm.check_manifest(str(cache), repo=str(repo))
    assert len(reasons) == 1 and 'does not record it' in reasons[0]


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q']))
