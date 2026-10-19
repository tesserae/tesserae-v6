"""Passage-index results carry the short locus, never only the file's tag.

The corpus files tag lines with abbreviations ("thuc. pele. 2.57.1"). Pages
that printed ref_start showed the tag. _short_locus_fields is the one place
that makes the reader-facing form (2026-10-15).
"""
from backend import passage_index
from backend.passage_index import _short_locus_fields as f


def test_whole_work_tag():
    r = f('vergil.aeneid', 'verg. aen. 1.1', 'verg. aen. 1.1')
    assert r['locus'] == '1.1'
    assert r['locus_start'] == '1.1' and r['locus_end'] == '1.1'
    assert r['citation'].endswith(' 1.1') and 'verg.' not in r['citation']


def test_part_tag():
    r = f('thucydides.peloponnesian_war.part.2', 'thuc. pele. 2.57.1', 'thuc. pele. 2.57.1')
    assert r['locus'] == '2.57.1'
    assert 'thuc.' not in r['citation']


def test_range_uses_an_en_dash_and_shortens_both_ends():
    r = f('thucydides.peloponnesian_war.part.2', 'thuc. pele. 2.57.1', 'thuc. pele. 2.58.3')
    assert r['locus'] == '2.57.1–2.58.3'
    assert r['locus_start'] == '2.57.1' and r['locus_end'] == '2.58.3'


def test_tag_with_no_numeric_tail_is_not_mangled():
    r = f('some.work', 'frag.alpha', 'frag.alpha')
    assert r['locus'] == 'frag.alpha'


def test_empty_ref_does_not_raise():
    r = f('some.work', None, None)
    assert r['locus'] == '' and r['locus_start'] == '' and r['locus_end'] == ''
    assert isinstance(r['citation'], str)


def test_no_end_means_a_single_locus():
    assert f('vergil.aeneid', 'verg. aen. 6.268', None)['locus'] == '6.268'


def test_export_agrees_with_the_helper():
    from backend.blueprints.passages import _export_rows
    rows = _export_rows([{'work': 'thucydides.peloponnesian_war.part.2', 'score': 0.5,
                          'ref_start': 'thuc. pele. 2.57.1', 'ref_end': 'thuc. pele. 2.58.3'}], {})
    assert rows[0]['locus'] == '2.57.1–2.58.3'
    rows = _export_rows([{'work': 'x', 'score': 0.5, 'locus': '9.9',
                          'ref_start': 'x 9.9', 'ref_end': 'x 9.9'}], {})
    assert rows[0]['locus'] == '9.9'


def test_density_cache_hit_gains_the_locus(tmp_path, monkeypatch):
    import json
    cache = tmp_path / 'd.json'
    cache.write_text(json.dumps({'work': 'vergil.aeneid', 'windows': [
        {'id': 1, 'ref_start': 'verg. aen. 1.1', 'ref_end': 'verg. aen. 1.30'}]}))
    monkeypatch.setattr(passage_index, '_density_cache_path', lambda w, s: str(cache))
    out = passage_index.connection_density('vergil.aeneid')
    assert out['windows'][0]['locus'] == '1.1–1.30'


def test_a_roman_numeral_act_is_part_of_the_locus():
    """Hamlet is tagged act.scene.line with a Roman act: the card read "1.66"
    for III.1.66 (2026-10-18). A Roman level ahead of numeric ones stays."""
    from backend.utils import format_short_locus
    assert format_short_locus('hamlet III.1.66') == 'III.1.66'
    assert format_short_locus('Spenser F.Q. 3.9.359') == '3.9.359'
    assert format_short_locus('hebrew_bible.isaiah.34.11') == '34.11'
    assert format_short_locus('CIL VI 1234') == '1234'
    assert format_short_locus('thuc. pele. 2.57.1') == '2.57.1'
