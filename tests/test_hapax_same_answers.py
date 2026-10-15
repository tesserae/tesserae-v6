"""The Rare Words speed changes (2026-10-15) leave every answer as it was.

The reference functions below are the code as it stood before the change.
"""
import re
import unicodedata

from backend.blueprints import hapax as H


def _old_strip_punctuation(word):
    word = re.sub(r'^[,;:.·!?\'\"\[\]\(\)«»]+|[,;:.·!?\'\"\[\]\(\)«»]+$', '', word)
    while word and unicodedata.combining(word[-1]):
        word = word[:-1]
    while word and unicodedata.combining(word[0]):
        word = word[1:]
    return word


def _old_word_matches_lemma(word, lemma, language):
    if not word or not lemma:
        return False
    w = word.lower()
    lm = H.clean_lemma_key(lemma).lower()
    if language == 'la':
        w = w.replace('v', 'u').replace('j', 'i')
        lm = lm.replace('v', 'u').replace('j', 'i')
        if w == lm:
            return True
        w_stripped = H.strip_latin_enclitics(word).lower().replace('v', 'u').replace('j', 'i')
        if w_stripped != w and w_stripped == lm:
            return True
        min_stem = min(4, len(lm))
        if len(lm) >= 3:
            if len(w) >= min_stem and w[:min_stem] == lm[:min_stem]:
                return True
            if len(w_stripped) >= min_stem and w_stripped[:min_stem] == lm[:min_stem]:
                return True
    elif language == 'grc':
        w_base = ''.join(c for c in unicodedata.normalize('NFD', w) if not unicodedata.combining(c))
        l_base = ''.join(c for c in unicodedata.normalize('NFD', lm) if not unicodedata.combining(c))
        w_base = w_base.replace('ς', 'σ')
        l_base = l_base.replace('ς', 'σ')
        if w_base == l_base:
            return True
        min_stem = min(4, len(l_base))
        if len(l_base) >= 3 and len(w_base) >= min_stem and w_base[:min_stem] == l_base[:min_stem]:
            return True
    else:
        if w == lm:
            return True
        min_stem = min(4, len(lm))
        if len(lm) >= 3 and len(w) >= min_stem and w[:min_stem] == lm[:min_stem]:
            return True
    return False


TOKENS = ['', 'arma', 'Arma,', '(virum)', '«cano»', 'Troiae.', 'quí', '́abc',
          'abć', '..', 'ἄνδρα', 'ἀνδρός;', 'μῆνιν', 'Μῆνιν,', 'ἔπεά', 'νόστος.',
          'ἀνήρ', 'Achates!', 'uirumque', 'virumque', 'iuuenis', 'juvenis', 'the', 'The.', "'tis", 'ab\n']


def test_strip_punctuation_unchanged():
    for t in TOKENS:
        assert H.strip_punctuation(t) == _old_strip_punctuation(t), repr(t)


def test_word_matches_lemma_unchanged():
    lemmas = ['arma', 'uir', 'vir', 'troia', 'cano1', 'de_-suesco', 'ἀνήρ', 'ἀνδρός', 'μῆνις', 'νόστος',
              'ἔπος', 'achates', 'the', 'iuuenis', 'ad-pello', '']
    for lang in ('la', 'grc', 'en'):
        for t in TOKENS + lemmas:
            for lem in lemmas:
                assert H.word_matches_lemma(t, lem, lang) == _old_word_matches_lemma(t, lem, lang), (t, lem, lang)


def test_location_memo_gives_the_same_location():
    row = {'text_id': 'vergil.aeneid.part.1.tess', 'ref': 'verg. aen. 1.1', 'positions_json': '[0]',
           'language': 'la'}
    memo = {}
    plain = H._location_from_row(row, 'arma uirumque cano')
    assert H._location_from_row(row, 'arma uirumque cano', memo) == plain
    assert H._location_from_row(row, 'arma uirumque cano', memo) == plain
    row2 = dict(row, ref='')
    assert H._location_from_row(row2, 'x', memo) == H._location_from_row(row2, 'x')
