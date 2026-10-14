"""Characterization tests for backend/feature_extractor.py.

These record what the code does today on fixed inputs, so that later cleaning
cannot change the scoring core unnoticed. Each expected value was taken from a
run of the current code and then read for plausibility; the comment beside it
says why it is plausible.

Nothing here needs an index, a database, the network or a data file. The
syntax matcher and the scanner are replaced by stubs, and the weights file is
pointed at a temporary path.
"""
import json

import pytest

from backend import feature_extractor as fx


@pytest.fixture
def fe(monkeypatch, tmp_path):
    """A FeatureExtractor with the shipped default weights, never the file on disk."""
    monkeypatch.setattr(fx, 'WEIGHTS_FILE', str(tmp_path / 'weights.json'))
    ex = fx.FeatureExtractor()
    ex.weights = dict(fx.DEFAULT_FEATURE_WEIGHTS)
    ex.weights['enabled_features'] = ['lemma', 'pos', 'edit_distance', 'sound']
    return ex


# Units shaped as text_processor.process_line makes them: text, ref, tokens,
# lemmas and pos_tags, all lists in step.
SRC = {'text': 'arma virumque cano', 'ref': '<verg. aen. 1.1>',
       'tokens': ['arma', 'virumque', 'cano'],
       'lemmas': ['arma', 'uir', 'cano'],
       'pos_tags': ['N-P---NA-', 'N-S---MA-', 'V1SPIA---']}
TGT = {'text': 'arma uiri canit', 'ref': '<luc. 1.1>',
       'tokens': ['arma', 'uiri', 'canit'],
       'lemmas': ['arma', 'uir', 'cano'],
       'pos_tags': ['N-P---NA-', 'N-S---MG-', 'V3SPIA---']}
MATCHED = ['arma', 'uir', 'cano']


# ---- calculate_pos_score ---------------------------------------------------

def test_pos_score_same_classes(fe):
    # Three matched lemmas, all noun/noun, noun/noun, verb/verb: classes agree.
    assert fe.calculate_pos_score(SRC, TGT, MATCHED) == 1.0


def test_pos_score_half_agree(fe):
    tgt = dict(TGT, pos_tags=['N-P---NA-', 'V3SPIA---', 'V3SPIA---'])
    # 2 of 3 matched lemmas share a class.
    assert fe.calculate_pos_score(SRC, tgt, MATCHED) == pytest.approx(2 / 3)


def test_pos_score_untagged_word_says_nothing(fe):
    tgt = dict(TGT, pos_tags=['N-P---NA-', '', 'V3SPIA---'])
    # The blank tag is skipped, so 2 of 2 counted lemmas agree.
    assert fe.calculate_pos_score(SRC, tgt, MATCHED) == 1.0


def test_pos_score_empty_inputs(fe):
    assert fe.calculate_pos_score({}, TGT, MATCHED) == 0.0   # no tags at all
    assert fe.calculate_pos_score(SRC, TGT, []) == 0.0       # nothing matched


def test_pos_score_disabled_feature(fe):
    fe.weights['enabled_features'] = ['lemma']
    assert fe.calculate_pos_score(SRC, TGT, MATCHED) == 0.0  # feature off


# ---- _normalize_pos --------------------------------------------------------

@pytest.mark.parametrize('tag,expected', [
    ('NOUN', 'NOUN'),           # universal
    ('PROPN', 'NOUN'),          # proper nouns go with nouns, not pronouns (#487)
    ('AUX', 'VERB'),
    ('nn', 'NOUN'),             # lower case is upper-cased first
    ('VBZ', 'VERB'),            # Penn
    ('PRP$', 'PRON'),
    ('N-S---MA-', 'NOUN'),      # nine-position Perseus code, first letter N
    ('V3SPIA---', 'VERB'),
    ('L-S---MN-', 'DET'),       # article goes with determiners
    ('', 'UNK'),                # nobody tagged it
    (None, 'UNK'),
    ('xx', 'UNK'),              # unknown scheme
    ('-S---MA--', 'UNK'),       # blank class position
    ('UNK', 'UNK'),
])
def test_normalize_pos(fe, tag, expected):
    assert fe._normalize_pos(tag) == expected


# ---- edit distance, fuzzy matches -----------------------------------------

def test_edit_distance_score(fe):
    # arma/arma 1.0, uiri/virumque... lemma positions: arma 1.0, uiri vs virumque, canit vs cano
    assert fe.calculate_edit_distance_score(SRC, TGT, MATCHED) == pytest.approx(0.6666666666666666)


def test_edit_distance_identical_and_empty(fe):
    assert fe.calculate_edit_distance_score(SRC, SRC, MATCHED) == 1.0  # same tokens
    assert fe.calculate_edit_distance_score({}, TGT, MATCHED) == 0.0   # no tokens
    assert fe.calculate_edit_distance_score(SRC, TGT, ['zzz']) == 0.0  # lemma absent


def test_edit_distance_disabled(fe):
    fe.weights['enabled_features'] = ['lemma']
    assert fe.calculate_edit_distance_score(SRC, TGT, MATCHED) == 0.0


def test_fuzzy_matches_default_threshold(fe):
    # Identical tokens are excluded; nothing else is 80% alike.
    assert fe.find_fuzzy_matches(SRC['tokens'], TGT['tokens']) == []


def test_fuzzy_matches_lower_threshold_and_short_tokens(fe):
    out = fe.find_fuzzy_matches(['cano', 'ab'], ['canit', 'ab'], threshold=50)
    # cano/canit share 'can' and one more letter; 'ab' is under three characters.
    assert out == [{'source_token': 'cano', 'target_token': 'canit',
                    'similarity': pytest.approx(0.6666666666666666)}]
    assert fe.find_fuzzy_matches([], ['cano']) == []


# ---- trigrams --------------------------------------------------------------

def test_get_trigrams(fe):
    assert fe.get_trigrams('arma') == {'arm', 'rma'}
    assert fe.get_trigrams('ARMA') == {'arm', 'rma'}   # lower-cased
    assert fe.get_trigrams('ab') == set()              # under three characters
    assert fe.get_trigrams('') == set()


def test_get_unit_trigrams(fe):
    idx = fe.get_unit_trigrams(['arma', 'ar', 'rma'])
    assert dict(idx) == {'arm': ['arma'], 'rma': ['arma', 'rma']}  # 'ar' skipped


def test_trigram_similarity(fe):
    # virumque has 6 trigrams, virum 3, all of virum's inside: 3/6.
    assert fe.calculate_trigram_similarity('virumque', 'virum') == 0.5
    assert fe.calculate_trigram_similarity('arma', 'arma') == 1.0
    assert fe.calculate_trigram_similarity('arma', 'xyz') == 0.0
    assert fe.calculate_trigram_similarity('ab', 'arma') == 0.0   # too short


def test_find_sound_matches(fe):
    out = fe.find_sound_matches(SRC['tokens'], TGT['tokens'])
    assert len(out) == 1                                  # only arma/arma reaches 0.3
    assert out[0]['source_token'] == 'arma' and out[0]['target_token'] == 'arma'
    assert out[0]['similarity'] == 1.0
    assert sorted(out[0]['shared_trigrams']) == ['arm', 'rma']


def test_find_sound_matches_threshold_and_empty(fe):
    assert fe.find_sound_matches(['virumque'], ['virum'], threshold=0.6) == []
    assert len(fe.find_sound_matches(['virumque'], ['virum'], threshold=0.5)) == 1
    assert fe.find_sound_matches([], ['virum']) == []


def test_sound_score(fe):
    # best trigram match per source token: arma 1.0, virumque 0.25 or 0, cano 0 -> mean over matched
    assert fe.calculate_sound_score(SRC, TGT) == pytest.approx(0.625)


def test_sound_score_empty_and_short(fe):
    assert fe.calculate_sound_score({}, TGT) == 0.0
    assert fe.calculate_sound_score({'tokens': ['ab', 'cd']}, TGT) == 0.0  # all under 3 chars


# ---- syntax, with the syntax matcher stubbed -------------------------------

class _Sent:
    def get_structure_signature(self):
        return ('nsubj', 'root')

    def get_lemma_roles(self):
        return {'uir': {'deprel': 'obj'}}

    def get_all_word_roles(self):
        return {'virum': {'deprel': 'obj'}}

    def get_roles_set(self):
        return {'obj', 'root'}


class _Matcher:
    def __init__(self, from_db, from_tb):
        self.from_db, self.from_tb, self.calls = from_db, from_tb, []

    def get_syntax_score_by_ref(self, *a, **k):
        self.calls.append('ref')
        return 0.8, _Sent(), _Sent(), self.from_db

    def get_syntax_score(self, *a, **k):
        self.calls.append('text')
        return 0.4, _Sent(), None, self.from_tb


def _stub_matcher(monkeypatch, m):
    import backend.syntax_parser as sp
    monkeypatch.setattr(sp, 'get_syntax_matcher', lambda: m)


def test_syntax_score_from_database_for_latin(fe, monkeypatch):
    m = _Matcher(True, False)
    _stub_matcher(monkeypatch, m)
    score, a, b = fe.calculate_syntax_score(SRC, TGT, MATCHED, 'la', 'a.tess', 'b.tess')
    assert score == 0.8 and m.calls == ['ref']       # the database path answered
    assert a == {'structure': ['nsubj', 'root'], 'roles': {'uir': 'obj'},
                 'word_roles': {'virum': 'obj'}, 'roles_set': a['roles_set'],
                 'from_treebank': True}
    assert sorted(a['roles_set']) == ['obj', 'root'] and b['roles'] == {'uir': 'obj'}


def test_syntax_score_falls_back_to_treebank(fe, monkeypatch):
    m = _Matcher(False, True)
    _stub_matcher(monkeypatch, m)
    score, a, b = fe.calculate_syntax_score(SRC, TGT, MATCHED, 'la', 'a.tess', 'b.tess')
    assert score == 0.4 and m.calls == ['ref', 'text']
    assert a['from_treebank'] is True and b is None   # target sentence missing -> None


def test_syntax_score_greek_skips_database(fe, monkeypatch):
    m = _Matcher(True, True)
    _stub_matcher(monkeypatch, m)
    fe.calculate_syntax_score(SRC, TGT, MATCHED, 'grc', 'a.tess', 'b.tess')
    assert m.calls == ['text']                         # the by-ref path is Latin only


def test_syntax_score_no_treebank_and_empty_text(fe, monkeypatch):
    _stub_matcher(monkeypatch, _Matcher(False, False))
    assert fe.calculate_syntax_score(SRC, TGT, MATCHED, 'en') == (0.0, None, None)
    assert fe.calculate_syntax_score({'text': ''}, TGT, MATCHED) == (0.0, None, None)


# ---- meter, with the scanner stubbed ---------------------------------------

def test_meter_score_with_stubbed_scansion(fe, monkeypatch):
    import backend.metrical_scanner as ms
    seen = []

    def fake_scan(author_work, line_num, text):
        seen.append((author_work, line_num))
        return {'pattern': 'DSSDSSDSSDSSDSS'}

    monkeypatch.setattr(ms, 'get_scansion_for_line', fake_scan)
    score, a, b = fe.calculate_meter_score(SRC, TGT, 'vergil.aeneid.part.1.tess', 'lucan.pharsalia.tess')
    assert score == 1.0                                 # identical patterns
    assert a == b == {'pattern': 'DSSDSSDSSDSSDSS'}
    # ref "<verg. aen. 1.1>" -> last word "1.1"; "part" cuts the file name at the work
    assert seen == [('vergil.aeneid', '1.1'), ('lucan.pharsalia', '1.1')]


def test_meter_score_no_scansion_or_text(fe, monkeypatch):
    import backend.metrical_scanner as ms
    monkeypatch.setattr(ms, 'get_scansion_for_line', lambda *a: None)
    assert fe.calculate_meter_score(SRC, TGT, 'a.b.tess', 'c.d.tess') == (0.0, None, None)
    assert fe.calculate_meter_score({'text': ''}, TGT) == (0.0, None, None)
    # no ref, or no usable file name, means no lookup at all
    assert fe._get_scansion_with_mqdq('', 'x', 'a.b.tess') is None
    assert fe._get_scansion_with_mqdq('1.1', 'x', '') is None


# ---- extract_features and boost_score --------------------------------------

def test_extract_features_defaults(fe):
    f = fe.extract_features(SRC, TGT, MATCHED)
    # defaults: edit distance and sound on, the rest off
    assert f['lemma_count'] == 3 and f['pos_score'] == 0.0
    assert f['edit_distance_score'] == pytest.approx(0.6666666666666666)
    assert f['sound_score'] == pytest.approx(0.625)
    # (1*0.6 + 0.3*0.667 + 0.4*0.625) / 1.7 : three lemmas of five give lemma score 0.6
    assert f['combined_score'] == pytest.approx(0.6176470588235292)


def test_extract_features_with_pos_and_empty(fe):
    f = fe.extract_features(SRC, TGT, MATCHED, {'use_pos': True})
    assert f['pos_score'] == 1.0 and f['combined_score'] == pytest.approx(0.6285714285714287)
    e = fe.extract_features({}, {}, [])
    assert e['lemma_count'] == 0 and e['combined_score'] == 0.0


def test_extract_features_meter_and_syntax_on(fe, monkeypatch):
    import backend.metrical_scanner as ms
    monkeypatch.setattr(ms, 'get_scansion_for_line', lambda *a: {'pattern': 'DS'})
    _stub_matcher(monkeypatch, _Matcher(True, False))
    f = fe.extract_features(SRC, TGT, MATCHED, {'use_meter': True, 'use_syntax': True},
                            'a.b.tess', 'c.d.tess', 'la')
    assert f['meter_score'] == 1.0 and f['syntax_score'] == 0.8
    assert f['source_scansion'] == {'pattern': 'DS'} and f['source_syntax']['from_treebank']


def test_boost_score_defaults(fe):
    f = fe.extract_features(SRC, TGT, MATCHED)
    # edit 0.667 is under the 0.7 gate; sound 0.625 > 0.3 adds 0.15*0.625
    assert fe.boost_score(0.5, f) == pytest.approx(0.546875)
    assert fe.boost_score(0.9, f) == pytest.approx(0.984375)


def test_boost_score_with_sound_disabled(fe):
    f = fe.extract_features(SRC, TGT, MATCHED)
    assert fe.boost_score(0.5, f, {'use_sound': False}) == 0.5   # nothing else clears its gate


def test_boost_score_edge_cases(fe):
    assert fe.boost_score(0.5, None) == 0.5
    assert fe.boost_score(0.5, {}) == 0.5
    big = {'sound_score': 1.0}
    # Scores may pass 1.0 by default (backend/score_bounds.py, UNBOUNDED_DEFAULT);
    # only a request that sets unbounded_scoring False gets the ceiling.
    assert fe.boost_score(0.95, big) == pytest.approx(1.0925)
    assert fe.boost_score(0.95, big, {'unbounded_scoring': False}) == 1.0
    syn = {'lemma_count': 2, 'syntax_score': 1.0}
    assert fe.boost_score(0.5, syn, {'use_syntax': True, 'use_sound': False}) == pytest.approx(0.75)
    assert fe.boost_score(0.5, {'lemma_count': 1, 'syntax_score': 1.0}, {'use_syntax': True}) == 0.5


# ---- weights file ----------------------------------------------------------

def test_load_weights_missing_file_gives_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, 'WEIGHTS_FILE', str(tmp_path / 'nope.json'))
    assert fx.load_feature_weights() == fx.DEFAULT_FEATURE_WEIGHTS


def test_save_then_load_round_trip_and_fill_missing_keys(monkeypatch, tmp_path):
    path = tmp_path / 'w.json'
    monkeypatch.setattr(fx, 'WEIGHTS_FILE', str(path))
    assert fx.save_feature_weights({'lemma': 2.0}) is True
    assert json.loads(path.read_text()) == {'lemma': 2.0}
    loaded = fx.load_feature_weights()
    assert loaded['lemma'] == 2.0                                  # stored value kept
    assert loaded['sound'] == 0.4                                  # missing key filled from defaults


def test_load_weights_corrupt_file_gives_defaults(monkeypatch, tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{not json')
    monkeypatch.setattr(fx, 'WEIGHTS_FILE', str(path))
    assert fx.load_feature_weights() == fx.DEFAULT_FEATURE_WEIGHTS


def test_save_weights_unwritable_path(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, 'WEIGHTS_FILE', str(tmp_path / 'no_such_dir' / 'w.json'))
    assert fx.save_feature_weights({}) is False


def test_extractor_methods_get_set_reload(fe, tmp_path):
    assert fe.is_feature_enabled('sound') and not fe.is_feature_enabled('meter')
    copy = fe.get_weights()
    copy['sound'] = 9
    assert fe.weights['sound'] == 0.4                              # get_weights returns a copy
    assert fe.set_weights({'sound': 0.9}) is True                  # saved to the temp path
    fe.weights['sound'] = 0.1
    fe.reload_weights()
    assert fe.weights['sound'] == 0.9
