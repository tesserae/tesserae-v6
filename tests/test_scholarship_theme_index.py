"""Splitter and sidecar writer of the scholarship Theme Search prototype."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'scholarship'))

import build_scholarship_theme_index as b  # noqa: E402


def unit(text, ref='1.1', lemma='', ref_end=None):
    u = {'ref': ref, 'lemma': lemma, 'text': text}
    if ref_end:
        u['ref_end'] = ref_end
    return u


def test_short_notes_are_joined_up_to_the_limit():
    units = [unit('word ' * 30, ref=f'1.{i}') for i in range(1, 8)]
    wins = b.split_notes(units)
    assert sum(w['n_notes'] for w in wins) == 7
    assert all(b.words(w['text']) <= b.MAX_WORDS for w in wins)
    assert wins[0]['ref_start'] == '1.1' and wins[0]['ref_end'] == '1.3'


def test_long_note_is_cut_at_sentence_ends():
    sent = 'This is a sentence of exactly eight words long. '
    wins = b.split_notes([unit(sent * 60, ref='2.5')])
    assert len(wins) >= 3
    assert all(b.words(w['text']) <= b.MAX_WORDS for w in wins)
    assert all(w['text'].rstrip().endswith('.') for w in wins)
    assert all(w['ref_start'] == '2.5' for w in wins)


def test_empty_notes_dropped_and_order_kept():
    wins = b.split_notes([unit('', ref='1'), unit('alpha ' * 80, ref='2'), unit('beta ' * 80, ref='3')])
    assert [w['ref_start'] for w in wins] == ['2', '3']


def test_one_giant_sentence_is_cut_by_words():
    wins = b.split_notes([unit('x ' * 500)])
    assert len(wins) > 1 and all(b.words(w['text']) <= b.MAX_WORDS for w in wins)


def test_lemma_is_prefixed():
    wins = b.split_notes([unit('explains the word', lemma='arma')])
    assert wins[0]['text'].startswith('arma: ')


def test_sidecar_layout_matches_window_texts(tmp_path):
    recs = [{'id': 'a:b:0', 'language': 'en', 'work': 'vergil.aeneid', 'ref_start': '1.1', 'ref_end': '1.2',
             'text': 'note', 'commentator': 'X', 'source': 'commentary'}]
    p = tmp_path / 'window_texts.db'
    b.write_sidecar(str(p), recs)
    con = sqlite3.connect(p)
    assert con.execute('SELECT id, language, work, ref_start, ref_end, text FROM window_texts').fetchall() == \
        [('a:b:0', 'en', 'vergil.aeneid', '1.1', '1.2', 'note')]
    assert con.execute('SELECT count(*) FROM lines').fetchone()[0] == 0


def test_description_record_has_nonempty_gist_and_embed_text_prefix():
    r = {'id': 'i', 'language': 'en', 'work': 'homer.odyssey', 'ref_start': '1.1', 'ref_end': '1.1',
         'text': 'hospitality note', 'commentator': 'Merry', 'source': 'commentary'}
    assert b.description_record(r)['desc']['gist'] == 'hospitality note'
    t = b.embed_text(r)
    assert t.startswith('query: Merry on homer odyssey 1.1.') and len(t) <= b.EMBED_CHARS
    json.dumps(b.description_record(r))
