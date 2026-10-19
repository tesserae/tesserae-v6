"""The Greek numeral adverbs pair with their Latin equivalents in the Greek-Latin
dictionary (2026-10-18). Od. 5.306 against Aen. 1.94, the best-known Knauer
parallel, shared one dictionary word (μάκαρ = beatus) and the two-word gate
dropped it; with τρίς = ter and τετράκις = quater it has three."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.synonym_dict import CURATED_GREEK_LATIN, _normalize_greek  # noqa: E402


def _latin(greek):
    return CURATED_GREEK_LATIN.get(_normalize_greek(greek).replace('ς', 'σ')) or []


def test_numeral_adverbs_are_paired():
    assert 'ter' in _latin('τρίς')
    assert 'quater' in _latin('τετράκις')
    assert 'bis' in _latin('δίς')
    assert 'decies' in _latin('δεκάκις')
    assert 'quotiens' in _latin('ὁσάκις')


def test_the_storm_parallel_now_shares_three_dictionary_words():
    greek = ['τρίς', 'μάκαρ', 'τετράκις']
    latin = {'ter', 'beatus', 'quater'}
    shared = {l for g in greek for l in _latin(g) if l in latin}
    assert shared == latin
