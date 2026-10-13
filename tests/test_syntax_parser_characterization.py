"""Characterization tests for backend/syntax_parser.py.

Expected values come from running the current code, then reading each one.
Left out on purpose: StanzaParser (it downloads and loads a model), the
Stanza branch of SyntaxMatcher.get_syntax_score (treebank_only=False),
SyntaxMatcher.get_sentence_info (falls back to Stanza), and the sqlite syntax
databases (data/inverted_index/syntax_latin.db is not in CI), apart from the
pure helper methods around them.
"""
import os

import pytest

from backend import syntax_parser as sp

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'syntax', 'mini.conllu')


def tok(i, form, lemma, upos, deprel, feats='_', head=0):
    return sp.SyntaxToken(i, form, lemma, upos, '_', feats, head, deprel, '_', '_')


def sent(sid, text, *tokens):
    return sp.SyntaxSentence(sid, text, list(tokens))


# ---- small pure functions --------------------------------------------------

@pytest.mark.parametrize('deprel,cat', [
    ('nsubj', 'core'),
    ('nsubj:pass', 'core'),        # the subtype after ':' is dropped
    ('obl', 'non_core'),
    ('amod', 'nominal'),
    ('conj', 'coordination'),
    ('flat', 'mwe'),
    ('parataxis', 'loose'),
    ('root', 'special'),
    ('advmod', 'modifier'),
    ('', 'other'),                 # blank relation is in no list
    ('zzz', 'other'),
])
def test_get_deprel_category(deprel, cat):
    assert sp.get_deprel_category(deprel) == cat


@pytest.mark.parametrize('text,expected', [
    ('Arma, uirum-que CANO!', 'arma uirumque cano'),   # punctuation stripped, hyphen removed
    ('  a   b\tc ', 'a b c'),                          # whitespace collapsed
    ('', ''),
    (None, ''),
    ('Ἄνδρα μοι ἔννεπε.', 'ἄνδρα μοι ἔννεπε'),          # Greek letters count as word characters
])
def test_normalize_text_for_lookup(text, expected):
    assert sp.normalize_text_for_lookup(text) == expected


@pytest.mark.parametrize('rel,expected', [
    ('nsubj', 'subject'), ('csubj', 'subject'), ('nsubj:pass', 'subject'),
    ('obj', 'object'), ('iobj', 'object'),
    ('case', 'case/mark'), ('mark', 'case/mark'),
    ('acl:relcl', 'clause'),
    ('amod', 'amod'),               # not in the table: unchanged
    ('', ''),
])
def test_normalize_deprel(rel, expected):
    assert sp.normalize_deprel(rel) == expected


def test_features_match():
    nom = {'Case': 'Nom', 'Number': 'Sing', 'Gender': 'Masc'}
    assert sp.features_match(nom, dict(nom)) is True
    # one of three differs: still agrees (matches >= comparisons - 1)
    assert sp.features_match(nom, {'Case': 'Acc', 'Number': 'Sing', 'Gender': 'Masc'}) is True
    # two of three differ: disagrees
    assert sp.features_match(nom, {'Case': 'Acc', 'Number': 'Plur', 'Gender': 'Masc'}) is False
    # only one comparable feature: not enough to say
    assert sp.features_match({'Case': 'Nom'}, {'Case': 'Nom'}) is False
    assert sp.features_match({}, nom) is False
    assert sp.features_match(nom, None) is False


def test_token_parsing_of_fields():
    t = sp.SyntaxToken(1, 'Arma', 'ARMA', 'NOUN', '_', 'Case=Acc|Number=Plur|junk', '3', '_', '_', '_')
    assert t.lemma == 'arma'                       # lemma lower-cased
    assert t.feats == {'Case': 'Acc', 'Number': 'Plur'}   # a pair with no '=' is dropped
    assert t.head == 3 and t.deprel == ''          # '_' deprel becomes blank
    blank = sp.SyntaxToken(1, 'x', None, 'X', '_', '_', '_', 'root', '_', '_')
    assert blank.lemma == '' and blank.feats == {} and blank.head == 0


# ---- compute_syntax_similarity on hand-built sentences ---------------------

def _pair():
    a = sent('a', 'Arma cano', tok(1, 'Arma', 'arma', 'NOUN', 'obj', 'Case=Acc|Number=Plur|Gender=Neut', 2),
             tok(2, 'cano', 'cano', 'VERB', 'root'))
    b = sent('b', 'Arma gero', tok(1, 'Arma', 'arma', 'NOUN', 'obj', 'Case=Acc|Number=Plur|Gender=Neut', 2),
             tok(2, 'gero', 'gero', 'VERB', 'root'))
    return a, b


def test_similarity_identical_sentences_is_one():
    a, _ = _pair()
    assert sp.compute_syntax_similarity(a, a) == 1.0


def test_similarity_sharing_one_head_relation():
    a, b = _pair()
    # only 'arma' is shared, same relation (1.0), same structure signature (+0.5 of 0.5)
    assert sp.compute_syntax_similarity(a, b) == 1.0
    assert sp.compute_syntax_similarity(a, b, ['arma']) == 1.0
    # matched_lemmas names a lemma not in both sentences: nothing to compare
    assert sp.compute_syntax_similarity(a, b, ['cano']) == 0.0


def test_similarity_sharing_no_lemma_is_zero():
    a = sent('a', 'x', tok(1, 'x', 'x', 'NOUN', 'obj'))
    b = sent('b', 'y', tok(1, 'y', 'y', 'NOUN', 'obj'))
    assert sp.compute_syntax_similarity(a, b) == 0.0


def test_similarity_empty_sentence_objects():
    a, _ = _pair()
    assert sp.compute_syntax_similarity(None, a) == 0.0
    assert sp.compute_syntax_similarity(a, None) == 0.0


@pytest.mark.parametrize('rel1,rel2,feats1,feats2,upos2,expected', [
    ('obj', 'obj', '_', '_', 'NOUN', 1.0),                  # same relation
    ('nsubj', 'csubj', '_', '_', 'NOUN', 0.95),             # same normalised relation
    ('conj', 'cc', 'Case=Nom|Number=Sing', 'Case=Nom|Number=Sing', 'NOUN', 0.9),   # features agree
    ('conj', 'cc', '_', '_', 'NOUN', 0.7),                  # same category (coordination)
    ('conj', 'amod', '_', '_', 'NOUN', 0.4),                # same part of speech only
    ('conj', 'amod', '_', '_', 'ADJ', 0.0),                 # nothing in common
])
def test_similarity_fallback_ladder(rel1, rel2, feats1, feats2, upos2, expected):
    # No core relations in either sentence for the last four, so no structure term.
    a = sent('a', 'x', tok(1, 'x', 'w', 'NOUN', rel1, feats1))
    b = sent('b', 'x', tok(1, 'x', 'w', upos2, rel2, feats2))
    got = sp.compute_syntax_similarity(a, b)
    if rel1 == 'obj':
        # both have a core signature ('obj',): the structure term adds 0.5 to both sides
        assert got == pytest.approx(1.0)
    elif rel1 == 'nsubj':
        # signatures ('nsubj',) and ('csubj',): disjoint, so 0.95 of a possible 1.5
        assert got == pytest.approx(0.95 / 1.5)
    else:
        assert got == pytest.approx(expected)


# ---- CoNLL-U fixture -------------------------------------------------------

def test_parse_conllu_file():
    sents = sp.parse_conllu_file(FIXTURE)
    assert [s.sent_id for s in sents] == ['s1', 's2']
    assert sents[0].text == 'Arma uirum cano.'
    assert [t.form for t in sents[0].tokens] == ['Arma', 'uirum', 'cano', '.']
    # the multiword-range row "1-2" in s2 is skipped
    assert [t.form for t in sents[1].tokens] == ['Arma', 'gerit', 'uir', 'fortis', '.']
    assert sents[1].tokens[1].head == 0 and sents[1].tokens[1].deprel == 'root'
    assert sents[0].normalized_text == 'arma uirum cano'


def test_sentence_views_on_fixture():
    s1, s2 = sp.parse_conllu_file(FIXTURE)
    # punctuation is left out of the pattern
    assert s1.dependency_pattern == (('NOUN', 'obj', 'core'), ('NOUN', 'conj', 'coordination'),
                                     ('VERB', 'root', 'special'))
    assert s1.get_roles_set() == {'obj', 'conj', 'root'}
    assert s1.get_structure_signature() == ('obj',)
    assert s2.get_structure_signature() == ('nsubj', 'obj')       # sorted
    assert s1.get_lemma_roles()['uir']['deprel'] == 'conj'
    assert s1.get_all_word_roles()['uirum']['lemma'] == 'uir'     # surface form key
    assert s2.get_lemma_roles()['gero']['upos'] == 'VERB'         # lemma, not the form 'gerit'


def test_similarity_on_fixture_sentences():
    s1, s2 = sp.parse_conllu_file(FIXTURE)
    assert sp.compute_syntax_similarity(s1, s2) == pytest.approx(0.86)   # arma 1.0, uir 0.9, structure 0.25
    assert sp.compute_syntax_similarity(s1, s2, ['arma']) == pytest.approx(0.8333333333333334)


def test_parse_conllu_file_without_trailing_blank_line(tmp_path):
    p = tmp_path / 'x.conllu'
    p.write_text('# sent_id = z\n# text = Cano.\n1\tCano\tcano\tVERB\t_\t_\t0\troot\t_\t_\n', encoding='utf-8')
    out = sp.parse_conllu_file(str(p))
    assert len(out) == 1 and out[0].sent_id == 'z'
    empty = tmp_path / 'e.conllu'
    empty.write_text('', encoding='utf-8')
    assert sp.parse_conllu_file(str(empty)) == []


# ---- SyntaxIndex -----------------------------------------------------------

@pytest.fixture
def index():
    ix = sp.SyntaxIndex()
    for s in sp.parse_conllu_file(FIXTURE):
        ix.add_sentence(s)
    return ix


def test_index_exact_lookup(index):
    assert len(index) == 2
    assert index.find_sentence('ARMA uirum, cano!').sent_id == 's1'   # punctuation and case ignored


def test_index_fuzzy_lookup(index):
    # four-letter words only count; 'arma' and 'gerit' and 'fortis' hit s2, which is above half
    assert index.find_sentence('Arma gerit uir fortis semper').sent_id == 's2'


def test_index_misses(index):
    assert index.find_sentence('') is None
    assert index.find_sentence('et in') is None               # no word of four letters
    assert index.find_sentence('Quo usque tandem abutere') is None


def test_index_ignores_sentence_without_text():
    ix = sp.SyntaxIndex()
    ix.add_sentence(sent('e', ''))
    assert len(ix) == 0


# ---- SyntaxMatcher on the fixture (no database, no Stanza) -----------------

@pytest.fixture
def matcher(tmp_path):
    d = tmp_path / 'UD_Latin-Perseus'
    d.mkdir()
    (d / 'mini.conllu').write_text(open(FIXTURE, encoding='utf-8').read(), encoding='utf-8')
    m = sp.SyntaxMatcher(treebank_dir=str(tmp_path))
    m.load_treebanks()
    return m


def test_matcher_loads_and_scores(matcher):
    assert matcher.loaded and len(matcher.index['la']) == 2 and len(matcher.index['grc']) == 0
    score, a, b, from_tb = matcher.get_syntax_score('Arma uirum cano', 'Arma gerit uir fortis', 'la')
    assert from_tb is True and a.sent_id == 's1' and b.sent_id == 's2'
    assert score == pytest.approx(0.86)


def test_matcher_unknown_language_uses_latin_index(matcher):
    assert matcher.get_syntax_score('Arma uirum cano', 'Arma gerit uir fortis', 'xx')[3] is True


def test_matcher_needs_both_sentences_in_treebank(matcher):
    assert matcher.get_syntax_score('Arma uirum cano', 'nothing known here', 'la') == (0.0, None, None, False)
    assert matcher.get_syntax_score('Arma uirum cano', 'Arma gerit uir fortis', 'grc') == (0.0, None, None, False)


def test_matcher_by_ref_without_database_returns_not_found(matcher):
    # English has no syntax database path; a Latin path that does not exist yields no parses
    assert matcher.get_syntax_score_by_ref('a', '1', 'b', '1', 'en') == (0.0, None, None, False)
    assert matcher._load_db_syntax_for_text('/nonexistent/x.db', 'a.tess') == {}
    assert matcher._load_db_syntax_for_text(None, 'a.tess') == {}


def test_matcher_missing_treebank_dir_loads_nothing(tmp_path):
    m = sp.SyntaxMatcher(treebank_dir=str(tmp_path / 'none'))
    m.load_treebanks()
    assert m.loaded and len(m.index['la']) == 0


def test_get_syntax_matcher_is_singleton():
    assert sp.get_syntax_matcher() is sp.syntax_matcher


def test_matcher_save_cache_without_stanza_is_noop(matcher):
    assert matcher.save_cache() is None


def test_expand_ref_candidates(matcher):
    f = matcher._expand_ref_candidates
    assert f('1.1-1.3') == ['1.1-1.3', '1.1', '1.3']       # a range gives both ends
    assert f('1.1', ['1.1', '1.2', None]) == ['1.1', '1.2']  # line_refs first, duplicates dropped
    assert f('') == [] and f(None) == []


def test_stringify_feats(matcher):
    f = matcher._stringify_feats
    assert f({'Number': 'Sing', 'Case': 'Nom'}) == 'Case=Nom|Number=Sing'   # sorted
    assert f({}) == '_' and f([]) == '_' and f(None) == '_' and f('') == '_'
    assert f(['Case=Nom', '', 'Number=Sing']) == 'Case=Nom|Number=Sing'
    assert f('Case=Acc') == 'Case=Acc'
    assert f([1, 2]) == '_'                                  # list of non-strings


def test_build_sentence_from_db_parse(matcher):
    s = matcher._build_sentence_from_db_parse('1.1', {
        'tokens': ['arma', 'cano'], 'lemmas': ['arma'], 'upos': ['NOUN', 'VERB'],
        'heads': [2, 0], 'deprels': ['obj', 'root'], 'feats': [{'Case': 'Acc'}]})
    assert s.sent_id == '1.1' and s.text == 'arma cano'
    assert [t.lemma for t in s.tokens] == ['arma', 'cano']       # a missing lemma falls back to the form
    assert s.tokens[0].feats == {'Case': 'Acc'} and s.tokens[1].feats == {}
    assert s.get_structure_signature() == ('obj',)
