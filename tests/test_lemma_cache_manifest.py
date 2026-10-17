"""scripts/corpus/lemma_cache_manifest.py: write a manifest for a temporary cache folder, check it
in step, then change a table, the tokenizer and a file count and check it stale. No live data is read."""
import importlib.util
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'scripts', 'corpus', 'lemma_cache_manifest.py')
_spec = importlib.util.spec_from_file_location('lemma_cache_manifest', _PATH)
lcm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lcm)


def _fake_repo(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'data' / 'lemma_tables').mkdir(parents=True)
    (repo / 'backend').mkdir()
    for rel in lcm.TABLES:
        (repo / rel).write_text('{"a": "b"}')
    (repo / lcm.TOKENIZER).write_text('# tokenizer v1\n')
    return repo


def _fake_cache(tmp_path):
    cache = tmp_path / 'cache'
    (cache / 'la').mkdir(parents=True)
    (cache / 'grc').mkdir()
    (cache / 'la' / 'x-1.json').write_text('{}')
    (cache / 'la' / 'y-2.json').write_text('{}')
    (cache / 'grc' / 'z-3.json').write_text('{}')
    return cache


def test_write_then_check_in_step(tmp_path, capsys):
    repo, cache = _fake_repo(tmp_path), _fake_cache(tmp_path)
    path = lcm.write_manifest(str(cache), repo=str(repo), builder='scripts/rebuild_lemma_cache.py',
                              fallbacks='none', differing_share={'la': 11.68})
    manifest = json.load(open(path))
    assert manifest['file_counts'] == {'grc': 1, 'la': 2}
    assert manifest['tokenizer']['sha256'] == lcm.sha256_of(str(repo / lcm.TOKENIZER))
    assert [t['path'] for t in manifest['tables']] == list(lcm.TABLES)
    assert manifest['differing_share_percent_of_lines'] == {'la': 11.68}
    assert lcm.check_manifest(str(cache), repo=str(repo)) == []
    assert lcm.main(['--check', str(cache), '--repo', str(repo)]) == 0
    assert 'in step' in capsys.readouterr().out


def test_changed_table_tokenizer_or_count_is_stale(tmp_path, capsys):
    repo, cache = _fake_repo(tmp_path), _fake_cache(tmp_path)
    lcm.write_manifest(str(cache), repo=str(repo))
    (repo / lcm.TABLES[0]).write_text('{"a": "c"}')
    reasons = lcm.check_manifest(str(cache), repo=str(repo))
    assert len(reasons) == 1 and 'latin_lemmas.json' in reasons[0]
    (repo / lcm.TOKENIZER).write_text('# tokenizer v2\n')
    (cache / 'la' / 'extra-4.json').write_text('{}')
    reasons = lcm.check_manifest(str(cache), repo=str(repo))
    assert len(reasons) == 3
    assert lcm.main(['--check', str(cache), '--repo', str(repo)]) == 1
    assert capsys.readouterr().out.startswith('stale: ')


def test_missing_manifest_is_stale(tmp_path):
    repo, cache = _fake_repo(tmp_path), _fake_cache(tmp_path)
    assert lcm.main(['--check', str(cache), '--repo', str(repo)]) == 1
