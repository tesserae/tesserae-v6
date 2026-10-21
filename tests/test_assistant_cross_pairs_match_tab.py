"""Tessa's list of the pairs the Cross-Language tab offers matches the tab itself."""
import os
import re

from backend.assistant import actions

TAB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'client', 'src', 'components', 'search', 'CrossLingualSearch.jsx')


def test_tab_pairs_equal_the_tab_less_the_held_back_arabic():
    src = open(TAB, encoding='utf-8').read()
    block = src[src.index('const LANG_PAIRS'):]
    block = block[:block.index('];')]
    pairs = {frozenset((a, b)) for a, b in re.findall(r"source: '(\w+)', target: '(\w+)'", block)}
    shown = {p for p in pairs if 'ar' not in p}
    assert shown == actions.TAB_PAIRS


def test_coptic_and_greek_is_reachable():
    assert actions.cross_pair('cop', 'grc') == ('Coptic and Greek', True)
