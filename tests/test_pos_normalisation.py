"""Every part-of-speech tag the corpus stores lands in the right class.

The part-of-speech boost compares the class of a shared word in the source
with its class in the target. Three tag schemes reach it, and until this test
existed nothing checked how any of them fell through the normaliser:

  Hebrew           Universal Dependencies tags: NOUN, PROPN, AUX, ADP ...
  English          Penn Treebank tags where tagged: NN, VBD, PRP$, JJ ...
  Greek and Latin  the nine-position Perseus treebank code where tagged:
                   'N-S---MA-', 'V3SPIA---', 'A-P---NA-'. Position one is
                   the word class.

The old normaliser told them apart by prefix. 'PROPN' starts with 'PR', so
every proper noun was filed with the pronouns and a name matched a pronoun
but not a noun (#487). Worse for Greek, where 58 percent of stored tags are
real: only the N and V prefixes were recognised, so adjectives, adverbs,
pronouns, prepositions, conjunctions, articles and participles all became
OTHER, and OTHER matched OTHER. The boost is off by default, so no live
result was affected. These figures come from sampling 25 cached files per
language on 2026-09-25.

Untagged words are a separate fault. 'UNK' also fell to OTHER, and OTHER
matched OTHER, so two words nobody had tagged counted as agreeing. In Latin,
where 82 percent of stored tags are 'UNK', the boost would have said yes to
almost everything. An untagged word now says nothing either way.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.feature_extractor import FeatureExtractor, UNKNOWN_POS  # noqa: E402

CLASSES = {'NOUN', 'VERB', 'ADJ', 'ADV', 'PREP', 'CONJ', 'PRON', 'DET',
           'OTHER', UNKNOWN_POS}


def norm(tag):
    return FeatureExtractor()._normalize_pos(tag)


class TestUniversalTags:
    """What Hebrew stores. Sampled from Isaiah: NOUN 4309, VERB 3124,
    ADP 2224, CCONJ 1873, PRON 1333, PROPN 1255, ADV 944, DET 776,
    SCONJ 665, ADJ 318, AUX 143, NUM 59, X 2."""

    def test_a_proper_noun_is_a_noun_not_a_pronoun(self):
        assert norm('PROPN') == 'NOUN'
        assert norm('PROPN') == norm('NOUN')
        assert norm('PROPN') != norm('PRON')

    def test_an_auxiliary_is_a_verb(self):
        assert norm('AUX') == 'VERB'

    def test_the_rest_of_the_scheme(self):
        assert norm('NOUN') == 'NOUN'
        assert norm('VERB') == 'VERB'
        assert norm('ADJ') == 'ADJ'
        assert norm('ADV') == 'ADV'
        assert norm('ADP') == 'PREP'
        assert norm('CCONJ') == 'CONJ'
        assert norm('SCONJ') == 'CONJ'
        assert norm('PRON') == 'PRON'
        assert norm('DET') == 'DET'
        assert norm('NUM') == 'NOUN'
        for tag in ('PART', 'INTJ', 'PUNCT', 'SYM', 'X'):
            assert norm(tag) == 'OTHER', tag


class TestPennTags:
    """What English stores where it is tagged at all."""

    def test_proper_nouns_and_common_nouns_agree(self):
        assert norm('NNP') == norm('NN') == 'NOUN'
        assert norm('NNPS') == norm('NNS') == 'NOUN'

    def test_the_rest_of_the_scheme(self):
        for tag in ('VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ', 'MD'):
            assert norm(tag) == 'VERB', tag
        for tag in ('JJ', 'JJR', 'JJS'):
            assert norm(tag) == 'ADJ', tag
        for tag in ('RB', 'RBR', 'RBS', 'WRB'):
            assert norm(tag) == 'ADV', tag
        assert norm('IN') == 'PREP'
        assert norm('TO') == 'PREP'
        assert norm('CC') == 'CONJ'
        for tag in ('PRP', 'PRP$', 'WP', 'WP$'):
            assert norm(tag) == 'PRON', tag
        for tag in ('DT', 'WDT', 'PDT'):
            assert norm(tag) == 'DET', tag
        assert norm('CD') == 'NOUN'
        for tag in ('UH', 'RP', 'FW', 'EX', 'POS', 'LS', 'SYM'):
            assert norm(tag) == 'OTHER', tag


class TestPerseusTags:
    """What Greek stores, and Latin where it is tagged. These are real tags
    from the cached Epistles of Crates and the sampled Latin files."""

    def test_position_one_is_the_class(self):
        assert norm('N-S---MA-') == 'NOUN'
        assert norm('N-P---MG-') == 'NOUN'
        assert norm('V3SPIA---') == 'VERB'
        assert norm('V--PNA---') == 'VERB'
        assert norm('A-P---NA-') == 'ADJ'
        assert norm('A-S---NA-') == 'ADJ'
        assert norm('D--------') == 'ADV'
        assert norm('P-S---MD-') == 'PRON'
        assert norm('P-S---MN-') == 'PRON'
        assert norm('R--------') == 'PREP'
        assert norm('C--------') == 'CONJ'
        assert norm('L-P---NA-') == 'DET'
        assert norm('L--------') == 'DET'

    def test_a_participle_goes_with_the_verb(self):
        assert norm('T-SPPAMN-') == 'VERB'

    def test_a_numeral_goes_with_the_noun(self):
        assert norm('M--------') == 'NOUN'

    def test_particles_interjections_and_punctuation_are_other(self):
        for tag in ('G--------', 'I--------', 'E--------', 'U--------',
                    'X--------'):
            assert norm(tag) == 'OTHER', tag

    def test_a_blank_code_is_unknown(self):
        assert norm('---------') == UNKNOWN_POS

    def test_case_does_not_matter(self):
        assert norm('n-s---ma-') == 'NOUN'


class TestUnknown:
    def test_nothing_and_the_unknown_markers(self):
        for tag in (None, '', 'UNK', 'Unk', 'unk'):
            assert norm(tag) == UNKNOWN_POS, repr(tag)

    def test_a_tag_from_no_scheme_is_unknown_not_other(self):
        # OTHER is a class that can match itself. Unknown must not be.
        assert norm('ZZZ') == UNKNOWN_POS
        assert norm('PR') == UNKNOWN_POS

    def test_every_answer_is_one_of_the_named_classes(self):
        tags = ['PROPN', 'AUX', 'NNP', 'PRP$', 'N-S---MA-', 'T-SPPAMN-',
                'G--------', '---------', 'UNK', '', 'nonsense']
        for tag in tags:
            assert norm(tag) in CLASSES, tag


class TestTheScoreItself:
    """calculate_pos_score with the feature switched on."""

    def make(self):
        fe = FeatureExtractor()
        fe.weights = dict(fe.weights)
        fe.weights['enabled_features'] = ['lemma', 'pos']
        return fe

    def test_the_issue_case_a_name_matches_a_noun(self):
        fe = self.make()
        src = {'lemmas': ['ישראל', 'ראה'], 'pos_tags': ['PROPN', 'VERB']}
        tgt = {'lemmas': ['ישראל', 'ראה'], 'pos_tags': ['NOUN', 'VERB']}
        assert fe.calculate_pos_score(src, tgt, ['ישראל', 'ראה']) == 1.0

    def test_a_name_does_not_match_a_pronoun(self):
        fe = self.make()
        src = {'lemmas': ['x'], 'pos_tags': ['PROPN']}
        tgt = {'lemmas': ['x'], 'pos_tags': ['PRON']}
        assert fe.calculate_pos_score(src, tgt, ['x']) == 0.0

    def test_untagged_words_are_left_out_of_the_count(self):
        fe = self.make()
        src = {'lemmas': ['a', 'b'], 'pos_tags': ['UNK', 'NOUN']}
        tgt = {'lemmas': ['a', 'b'], 'pos_tags': ['UNK', 'VERB']}
        # One comparable pair, and it disagrees. The untagged pair used to
        # count as agreeing and would have made this 0.5.
        assert fe.calculate_pos_score(src, tgt, ['a', 'b']) == 0.0

    def test_all_untagged_says_nothing(self):
        fe = self.make()
        src = {'lemmas': ['a', 'b'], 'pos_tags': ['UNK', 'UNK']}
        tgt = {'lemmas': ['a', 'b'], 'pos_tags': ['UNK', 'UNK']}
        assert fe.calculate_pos_score(src, tgt, ['a', 'b']) == 0.0

    def test_greek_across_the_scheme(self):
        fe = self.make()
        src = {'lemmas': ['ἀνήρ', 'λέγω', 'καλός'],
               'pos_tags': ['N-S---MN-', 'V3SPIA---', 'A-S---MN-']}
        tgt = {'lemmas': ['ἀνήρ', 'λέγω', 'καλός'],
               'pos_tags': ['N-P---MA-', 'T-SPPAMN-', 'D--------']}
        # noun/noun agree, verb/participle agree, adjective/adverb do not
        score = fe.calculate_pos_score(src, tgt, ['ἀνήρ', 'λέγω', 'καλός'])
        assert abs(score - 2 / 3) < 1e-9

    def test_off_by_default(self):
        fe = FeatureExtractor()
        assert 'pos' not in fe.weights.get('enabled_features', [])
        src = {'lemmas': ['x'], 'pos_tags': ['NOUN']}
        assert fe.calculate_pos_score(src, src, ['x']) == 0.0
