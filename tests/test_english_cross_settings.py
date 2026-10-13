"""The English cross-language settings reach the two English pairs only (2026-10-13)."""
import numpy as np

from backend.blueprints import search as sm
from backend import semantic_similarity as ss


class _Cs:
    def __init__(self, has_english):
        self.has_english = has_english


def test_overrides_are_read_for_english_pairs_only():
    assert sm._english_cross(_Cs(True), 'lemma_gate', 'exclude') == sm.ENGLISH_CROSS_SETTINGS['lemma_gate']
    assert sm._english_cross(_Cs(False), 'lemma_gate', 'exclude') == 'exclude'
    assert sm._english_cross(None, 'hubness_k', 0) == 0
    assert sm._english_cross(_Cs(False), 'semantic_top_n', 20) == 20


def test_cross_settings_gate_default_depends_on_the_pair():
    settings = {}
    en = sm._cross_settings({'source_id': 'a', 'target_id': 'b', 'language': 'la',
                             'source_language': 'la', 'target_language': 'en'}, settings)
    gl = sm._cross_settings({'source_id': 'a', 'target_id': 'b', 'language': 'grc',
                             'source_language': 'grc', 'target_language': 'la'}, settings)
    assert gl.crosslingual_lemma_gate == 'exclude'
    assert en.crosslingual_lemma_gate == sm.ENGLISH_CROSS_SETTINGS['lemma_gate']
    explicit = sm._cross_settings({'source_id': 'a', 'target_id': 'b', 'language': 'la',
                                   'source_language': 'la', 'target_language': 'en'},
                                  {'crosslingual_lemma_gate': 'exclude'})
    assert explicit.crosslingual_lemma_gate == 'exclude'


def test_early_modern_forms():
    f = sm._early_modern_forms
    assert 'change' in f("chang'd") and 'hurl' in f('hurld')
    assert 'wolf' in f('wolfe') and 'bee' in f('bees')
    assert f('the') == set()


def test_hubness_correction_removes_a_hub():
    rng = np.random.RandomState(0)
    src = rng.randn(40, 16).astype('float32')
    tgt = rng.randn(50, 16).astype('float32')
    tgt[0] = src.mean(0) * 5 + 0.1 * rng.randn(16)   # target 0 sits near every source line
    plain = [(i, j) for i, j, _ in ss.top_pairs_by_block(src, tgt, 1, -1.0)]
    corrected = [(i, j) for i, j, _, _ in ss.top_pairs_hubness_corrected(src, tgt, 1, -9.0, k=5)]
    assert sum(1 for _, j in plain if j == 0) > sum(1 for _, j in corrected if j == 0)
    off_s, off_t = ss.hubness_offsets(src, tgt, 5)
    assert off_s.shape == (40,) and off_t.shape == (50,)
