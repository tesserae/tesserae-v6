"""The default cross-language path builds the same rows as before (2026-10-17).

A small fixture goes through _fuse_pairs and the shared row builder under the default
setting, and every row is compared field for field with tests/fixtures/
crosslingual_fuse_pairs_expected.json, which was recorded from the code as it stood before
the row builder was moved out of _fuse_pairs. A change to the builder that alters a row
fails here. To record again after an intended change:
    python tests/test_crosslingual_row_builder.py --record
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXPECTED = ROOT / 'tests' / 'fixtures' / 'crosslingual_fuse_pairs_expected.json'


def _unit(ref, text, tokens, lemmas):
    return {'ref': ref, 'text': text, 'tokens': tokens, 'original_tokens': list(tokens),
            'lemmas': lemmas}


def _fixture():
    grc = [
        _unit('hom. il. 1.1', 'μῆνιν ἄειδε θεὰ', ['μῆνιν', 'ἄειδε', 'θεὰ'], ['μῆνις', 'ἀείδω', 'θεά']),
        _unit('hom. il. 1.2', 'οὐλομένην ἣ μυρί', ['οὐλομένην', 'ἣ', 'μυρί'], ['οὐλόμενος', 'ὅς', 'μυρίος']),
        _unit('hom. il. 1.3', 'πολλὰς δ ἰφθίμους ψυχὰς', ['πολλὰς', 'δ', 'ἰφθίμους', 'ψυχὰς'],
              ['πολύς', 'δέ', 'ἴφθιμος', 'ψυχή']),
    ]
    lat = [
        _unit('verg. aen. 1.1', 'arma virumque cano', ['arma', 'virumque', 'cano'], ['arma', 'vir', 'cano']),
        _unit('verg. aen. 1.2', 'dea mens ira', ['dea', 'mens', 'ira'], ['dea', 'mens', 'ira']),
        _unit('verg. aen. 1.3', 'anima multa canit', ['anima', 'multa', 'canit'], ['anima', 'multus', 'cano']),
    ]

    def wm(gl, ll, gi, li):
        return {'greek_lemma': gl, 'latin_lemma': ll, 'greek_indices': gi, 'latin_indices': li,
                'source_lemma': gl, 'target_lemma': ll, 'source_indices': gi, 'target_indices': li}
    # Source is Greek, target Latin.
    dict_by_pair = {
        (0, 1): [wm('θεά', 'dea', [2], [0]), wm('μῆνις', 'ira', [0], [2])],
        (0, 0): [wm('ἀείδω', 'cano', [1], [2])],
        (2, 2): [wm('πολύς', 'multus', [0], [1]), wm('ψυχή', 'anima', [3], [0])],
        (1, 1): [wm('μυρίος', 'mens', [2], [1])],
    }
    sem_by_pair = {(0, 1): 0.71, (0, 0): 0.42, (2, 2): 0.66, (1, 2): 0.35, (1, 0): 0.2}
    syntax_by_pair = {(0, 1): 0.4}
    phonetic_by_pair = {(0, 0): [{'source_original': 'ἄειδε', 'target_original': 'cano',
                                  'similarity': 0.62}]}
    return grc, lat, sem_by_pair, dict_by_pair, syntax_by_pair, phonetic_by_pair


def build_rows(gate, search_module=None):
    from backend.blueprints import search as sm
    sm = search_module or sm
    grc, lat, sem, dct, syn, pho = _fixture()
    params = {'source_id': 'a.tess', 'target_id': 'b.tess', 'language': 'grc',
              'source_language': 'grc', 'target_language': 'la'}
    settings = {'crosslingual_lemma_gate': gate, 'min_matches': 1}
    cs = sm._cross_settings(params, settings)
    idf = sm._local_idf(grc, lat, cs, None)
    merged = sm._merge_keys(sem, dct, syn, {}, settings, cs)
    rows = sm._fuse_pairs(merged, copy.deepcopy(sem), copy.deepcopy(dct), syn, pho, {},
                          idf, grc, lat, cs, None)
    rows = sm._cap(rows, {'max_results': 0})
    return json.loads(json.dumps(rows, sort_keys=True))


def _expected_all():
    return {gate: build_rows(gate) for gate in ('exclude', 'penalty', 'off')}


def test_default_path_rows_equal_the_recorded_rows():
    expected = json.loads(EXPECTED.read_text(encoding='utf-8'))
    for gate in ('exclude', 'penalty', 'off'):
        got = build_rows(gate)
        assert len(got) == len(expected[gate]) > 0
        for g, e in zip(got, expected[gate]):
            assert g == e


if __name__ == '__main__' and '--record' in sys.argv:
    EXPECTED.write_text(json.dumps(_expected_all(), sort_keys=True, indent=1, ensure_ascii=False),
                        encoding='utf-8')
    print('recorded', EXPECTED)
