"""The filter that removes restricted works' counts from whole-language files (scripts/corpus/filter_language_caches_by_registry.py)."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'corpus'))

import filter_language_caches_by_registry as flc  # noqa: E402


def test_subtract_removes_counts_and_drops_empty_entries_in_order():
    out = flc.subtract({'a': 5, 'b': 3, 'c': 1}, {'a': 2, 'c': 1})
    assert out == {'a': 3, 'b': 3}
    assert list(out) == ['a', 'b']


def test_subtract_stops_when_the_original_lacks_the_work():
    with pytest.raises(SystemExit):
        flc.subtract({'a': 1}, {'a': 2})
    with pytest.raises(SystemExit):
        flc.subtract({'a': 1}, {'zzz': 1})


def test_old_coptic_spelling_is_detected_and_mapped():
    old = {'ⲳⲵⲷⲹⲻⲽⲿ|ⲁ': 1}
    assert flc.table_uses_old_spelling(old)
    assert not flc.table_uses_old_spelling({'ϥ|ⲁ': 1})
    assert 'ϥϩ'.translate(flc.OLD_COPTIC_SPELLING) == 'ⲵⲹ'


def test_translation_pairs_drop_pairs_with_a_restricted_work(tmp_path):
    prod = tmp_path / 'prod'
    (prod / 'data').mkdir(parents=True)
    (prod / 'data/translation_pairs.json').write_text(json.dumps(
        {'count': 3, 'pairs': [{'work_a': 'bohairic.mark', 'work_b': 'sahidica.mark'},
                               {'work_a': 'sahidic.genesis', 'work_b': 'x'},
                               {'work_a': 'y', 'work_b': 'sahidica.nt'}]}), encoding='utf-8')
    out = tmp_path / 'out'
    out.mkdir()
    rep, dest = flc.filter_translation_pairs(str(prod), {'sahidica.mark', 'sahidica.nt'}, str(out))
    data = json.load(open(dest, encoding='utf-8'))
    assert data['count'] == 1 and rep['pairs_before'] == 3 and rep['pairs_after'] == 1


def test_the_script_refuses_to_write_under_production(tmp_path):
    prod = tmp_path / 'prod'
    prod.mkdir()
    with pytest.raises(SystemExit):
        flc.write_json(str(prod / 'x.json'), {}, str(prod))
