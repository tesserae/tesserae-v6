"""scripts/reuse/build_reuse_table.py: find_pairs's rare-single-ngram rule.

Diagnosing why only two works showed as reusing Aen. 1.1 ("arma virumque
cano") found that banality was not the obstacle -- none of that line's
n-grams come close to the max-df=200 cutoff in the live corpus (worst case
9 lines; see research notes for the full measurement). The obstacle was
min_shared: Seneca (Ep. 113.25) quotes only the three words "arma virumque
cano" inside an unrelated sentence about grammar, so it shares exactly ONE
n-gram with Aen. 1.1 and never reached shared>=2 (nor shared>=4 for the
containment override, since the denominator is pinned to Aen. 1.1's own
short n-gram count and a single shared n-gram there is a small fraction of
it). This exercises find_pairs directly against a small hand-built index db
so it runs without the real corpus or lemma cache.
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'reuse'))

from build_reuse_table import build_index, gen_ngrams, hash_ngram, find_pairs  # noqa: E402

VERGIL = ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris']
# A short, isolated quotation of just the first three words, buried in an
# otherwise unrelated ~40-word sentence -- the real shape of Seneca's
# quotation (Ep. 113.25), simplified to keep the fixture legible.
SENECA = ('sublata controuersia convenit nobis sermo animal est ita arma uirumque cano '
          'animal est quod non possunt rotundum dicere cum sex pedes habeat').split()
UNRELATED = 'nihil hic simile omnino est ceterum aliud plane argumentum de re alia'.split()


def _build_index_db(path, lines):
    """lines: {line_id: (work, ref, tokens)}."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE lines (line_id INTEGER PRIMARY KEY, work TEXT, line_ref TEXT, "
                 "token_count INTEGER, seq_in_work INTEGER)")
    conn.execute("CREATE TABLE postings (ngram_hash INTEGER, line_id INTEGER)")
    for lid, (work, ref, toks) in lines.items():
        conn.execute("INSERT INTO lines VALUES (?,?,?,?,?)", (lid, work, ref, len(toks), 0))
        seen = set()
        for gram in gen_ngrams(toks):
            h = hash_ngram(gram)
            if h in seen:
                continue
            seen.add(h)
            conn.execute("INSERT INTO postings VALUES (?,?)", (h, lid))
    conn.commit()
    conn.close()


def _fixture_db(tmp_path, lines):
    path = os.path.join(str(tmp_path), 'idx.db')
    _build_index_db(path, lines)
    return path


def _pairs_between(pair_info, work_a, work_b):
    out = []
    for wa, ra, sa, wb, rb, sb, shared, jaccard, span in pair_info:
        if {wa, wb} == {work_a, work_b}:
            out.append((shared, jaccard))
    return out


def _cache_data(works):
    """{work_id: [(ref, tokens), ...]} -> the {tess_basename: cache_dict}
    shape build_index expects from discover_corpus."""
    return {
        f'{work_id}.tess': {
            'text_id': f'{work_id}.tess',
            'units_line': [{'ref': ref, 'tokens': toks, 'text': ' '.join(toks)}
                            for ref, toks in lines],
        }
        for work_id, lines in works.items()
    }


def test_build_index_flags_a_commonplace_word_only_ngram(tmp_path):
    """A trigram whose every token is individually common (here, 'et', 'in',
    'ista' -- padded into most lines of a small fixture corpus so their
    line-df is high) belongs in commonplace_hashes; a trigram containing a
    word that appears in only one line does not, even though most of that
    trigram's other words are common too -- only ONE distinctive word is
    needed to keep an n-gram out of the commonplace set (see build_index's
    docstring). Passes an explicit, generous ratio: this tests the
    mechanism, not the specific default (0.08) tuned against the live
    corpus, which this tiny fixture is far too small to reproduce."""
    works = {f'filler{i}': [(f'f{i}.1', ['et', 'in', 'ista', 'res', 'alia'])] for i in range(10)}
    works['distinctive'] = [('dist.1', ['et', 'in', 'ista', 'chrysolithus', 'gemma'])]
    cache_data = _cache_data(works)
    index_db = os.path.join(str(tmp_path), 'idx.db')
    stats, commonplace_hashes = build_index(cache_data, index_db, max_df=200, commonplace_ratio=0.45)
    assert hash_ngram(('et', 'in', 'ista')) in commonplace_hashes
    assert hash_ngram(('ista', 'chrysolithus', 'gemma')) not in commonplace_hashes


def test_build_index_uses_lemmas_not_surface_forms(tmp_path):
    """'amat', 'amabat' and 'amauit' are three different surface forms of
    the ordinary verb 'amo' -- individually rarer by raw surface count than
    the word actually is. Commonality is judged on the lemma, so spreading
    an otherwise-common lemma over several inflected surface forms must not
    make it look distinctive."""
    forms = ['amat', 'amabat', 'amauit', 'amabit', 'amauerat', 'amaret',
             'amauisset', 'amando', 'amatus', 'amans', 'amaturus']
    works = {}
    for i, form in enumerate(forms):
        works[f'work{i}.tess'] = {
            'text_id': f'work{i}.tess',
            'units_line': [{
                'ref': f'w{i}.1', 'text': f'{form} res alia',
                'tokens': [form, 'res', 'alia'],
                'lemmas': ['amo', 'res', 'alia'],
            }],
        }
    index_db = os.path.join(str(tmp_path), 'idx.db')
    stats, commonplace_hashes = build_index(works, index_db, max_df=200, commonplace_ratio=0.45)
    # Every surface form of 'amo' pairs with the SAME common words, so each
    # of the eleven distinct surface trigrams should be flagged commonplace
    # -- eleven lines is a small corpus, but 'amo' the lemma is common in
    # all of them, which is the point being tested.
    for form in forms:
        assert hash_ngram((form, 'res', 'alia')) in commonplace_hashes, form


def test_a_short_isolated_quotation_is_recovered_by_the_rare_single_rule(tmp_path):
    db = _fixture_db(tmp_path, {
        0: ('vergil.aeneid', 'verg. aen. 1.1', VERGIL),
        1: ('seneca.ad_lucilium_epistulae_morales', 'sen.ep. 113.25', SENECA),
    })
    pair_info, line_to_other_works, stats = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20)
    pairs = _pairs_between(pair_info, 'vergil.aeneid', 'seneca.ad_lucilium_epistulae_morales')
    assert pairs, "Seneca's isolated quotation should be kept via the rare-single rule"
    assert pairs[0][0] == 1
    assert stats['pairs_kept_via_rare_single_ngram'] == 1


def test_disabled_with_rare_max_df_zero(tmp_path):
    db = _fixture_db(tmp_path, {
        0: ('vergil.aeneid', 'verg. aen. 1.1', VERGIL),
        1: ('seneca.ad_lucilium_epistulae_morales', 'sen.ep. 113.25', SENECA),
    })
    pair_info, line_to_other_works, stats = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=0)
    pairs = _pairs_between(pair_info, 'vergil.aeneid', 'seneca.ad_lucilium_epistulae_morales')
    assert pairs == []
    assert stats['pairs_kept_via_rare_single_ngram'] == 0


def test_a_shared_ngram_that_is_not_rare_is_not_kept_via_the_new_rule(tmp_path):
    """The rare-single rule requires the ONE shared n-gram to be corpus-rare
    (line-df under rare_max_df). Padding the corpus with enough OTHER lines
    repeating the exact same trigram pushes its line-df at or over the
    threshold, and the pair must then fall back to being excluded (same as
    before this change) rather than let a now-common n-gram through."""
    lines = {
        0: ('vergil.aeneid', 'verg. aen. 1.1', VERGIL),
        1: ('seneca.ad_lucilium_epistulae_morales', 'sen.ep. 113.25', SENECA),
    }
    # 25 more lines (>= rare_max_df=20) repeating "arma uirumque cano" so
    # that n-gram's line-df is no longer rare.
    for i in range(25):
        lines[2 + i] = (f'filler.work{i}', f'filler. {i}.1', ['arma', 'uirumque', 'cano'])
    db = _fixture_db(tmp_path, lines)
    pair_info, line_to_other_works, stats = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20)
    pairs = _pairs_between(pair_info, 'vergil.aeneid', 'seneca.ad_lucilium_epistulae_morales')
    assert pairs == []
    assert stats['pairs_kept_via_rare_single_ngram'] == 0


def test_a_rare_shared_ngram_between_two_long_unrelated_lines_is_not_kept(tmp_path):
    """Rarity alone floods: built against the live corpus, "shared==1 and
    rare" with no containment floor kept 6.4 MILLION pairs, almost all of
    them unrelated prose paragraphs that happen to share one obscure
    trigram (2026-09-19 measurement). Containment is pinned to the SHORTER
    side, so two long, otherwise-unrelated lines sharing a single rare
    n-gram have a low containment (unlike a short famous line quoted in a
    longer one, e.g. Aen. 1.1 in Seneca, containment=0.0625) and must stay
    excluded even though the shared n-gram is rare."""
    long_a = ('nihil hic simile omnino est ceterum aliud plane argumentum de re alia prorsus '
              'diversa quod nemo umquam ante hoc tempus tam copiose disseruit neque disserere '
              'potuit sine multa praeparatione atque doctrina longa et continua meditatione '
              'conquisita per multos annos ac summo labore parta').split() + ['spurios', 'ngramus', 'raris']
    long_b = ('aliud omnino argumentum hic tractatur quod ad rem prorsus diversam pertinet nec '
              'quisquam id ante nos tam diligenter exposuit quantum nos hodie exponimus multa cum '
              'cura et diligentia summaque doctrina per longum tempus adquisita').split() + ['spurios', 'ngramus', 'raris']
    db = _fixture_db(tmp_path, {
        0: ('some.work_a', 'a. 1.1', long_a),
        1: ('some.work_b', 'b. 1.1', long_b),
    })
    pair_info, line_to_other_works, stats = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20, rare_min_containment=0.06)
    pairs = _pairs_between(pair_info, 'some.work_a', 'some.work_b')
    assert pairs == [], "a low-containment rare-single match between two long lines must stay excluded"
    assert stats['pairs_kept_via_rare_single_ngram'] == 0


def test_a_rare_but_commonplace_word_shape_is_excluded_even_with_good_containment(tmp_path):
    """Containment alone still isn't enough: a fresh sample after adding the
    containment floor was still mostly noise like ('ut','in','ista') --
    three ordinary function words whose SPECIFIC ordered combination just
    doesn't come up often, which makes the SHAPE corpus-rare without either
    word meaning anything (2026-09-19 measurement). build_index's
    commonplace_hashes flags an n-gram as commonplace when every one of its
    tokens is individually common; find_pairs must reject a shared==1 match
    on such an n-gram even when containment is high, because the fixture
    below pairs it with a short line specifically to make containment look
    good."""
    # "et in ista" -- three ordinary function words -- as the ONLY connection
    # between a short line (so containment is high) and an unrelated one.
    a = ['et', 'in', 'ista', 'raralonga', 'aliudverbumraro']
    b = ['diversum', 'plane', 'argumentum', 'et', 'in', 'ista']
    commonplace = {hash_ngram(('et', 'in', 'ista'))}
    db = _fixture_db(tmp_path, {
        0: ('some.work_a', 'a. 1.1', a),
        1: ('some.work_b', 'b. 1.1', b),
    })
    pair_info, line_to_other_works, stats = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20, rare_min_containment=0.06, commonplace_hashes=commonplace)
    pairs = _pairs_between(pair_info, 'some.work_a', 'some.work_b')
    assert pairs == [], "a commonplace-word-only n-gram must be excluded even with high containment"


def test_unrelated_lines_still_excluded(tmp_path):
    db = _fixture_db(tmp_path, {
        0: ('vergil.aeneid', 'verg. aen. 1.1', VERGIL),
        1: ('some.other_work', 'other. 1.1', UNRELATED),
    })
    pair_info, line_to_other_works, stats = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20)
    assert pair_info == []


def test_repair_surrogates_recovers_a_greek_file_name_and_leaves_clean_text_alone():
    # Eight Greek lemma caches on production (2026-09-19) hold text_id as the
    # surrogate-escaped bytes of a Greek file name, e.g. aeschylus.εὐμενίδες,
    # written under an ASCII locale; SQLite refuses lone surrogates.
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        'build_reuse_table', pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'reuse' / 'build_reuse_table.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    real = 'aeschylus.εὐμενίδες.tess'
    escaped = real.encode('utf-8').decode('ascii', 'surrogateescape')   # what an ASCII locale produced
    assert escaped != real and any(0xD800 <= ord(c) <= 0xDFFF for c in escaped)
    fixed, changed = mod._repair_surrogates(escaped, 'fallback')
    assert (fixed, changed) == (real, True)
    assert mod._repair_surrogates('vergil.aeneid', 'x') == ('vergil.aeneid', False)
    # a lone surrogate that is not an escaped byte cannot be decoded: fall back
    assert mod._repair_surrogates('bad\ud800id', 'fallback') == ('fallback', True)


def test_commonplace_only_ngrams_count_for_no_rule_and_no_total(tmp_path):
    """English table, 2026-09-19: Hamlet III.4.192 "What shall I do?" came out
    strictly "quoted" by eight Bible verses, because the run "what shall i do"
    gave shared >= 2 with a high Jaccard. N-grams made only of commonplace
    words must count toward nothing: neither the shared count nor the lines'
    n-gram totals."""
    run = ['what', 'shall', 'i', 'do']
    a = list(run)                                   # Hamlet's line IS the run
    b = ['pilate', 'saith', 'unto', 'them'] + run + ['with', 'jesus']
    commonplace = {hash_ngram(g) for g in gen_ngrams(run)}
    db = _fixture_db(tmp_path, {
        0: ('shakespeare.hamlet', 'hamlet III.4.192', a),
        1: ('world_english_bible.new_testament', 'WEB Matthew 27.22', b),
    })
    pair_info, _, _ = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20, rare_min_containment=0.06, commonplace_hashes=commonplace)
    assert _pairs_between(pair_info, 'shakespeare.hamlet', 'world_english_bible.new_testament') == []
    # Without the commonplace set the very same fixture IS kept, so the
    # exclusion, not the fixture, is what removes the pair.
    pair_info, _, _ = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20, rare_min_containment=0.06, commonplace_hashes=set())
    assert _pairs_between(pair_info, 'shakespeare.hamlet', 'world_english_bible.new_testament') != []


def test_part_files_of_one_work_do_not_quote_each_other(tmp_path):
    """spenser.faerie_queene.part.4 and .part.6 are one work: a formula the
    poem repeats across books is not reuse by another work. The same line in
    Bunyan still counts."""
    line = ['so', 'forth', 'he', 'rode', 'upon', 'his', 'steed', 'of', 'might']
    db = _fixture_db(tmp_path, {
        0: ('spenser.faerie_queene.part.4', 'Spenser F.Q. 4.4.354', line),
        1: ('spenser.faerie_queene.part.6', 'Spenser F.Q. 6.12.712', line),
        2: ('bunyan.pilgrims_progress', 'Bunyan P.P. 1.10', line),
    })
    pair_info, _, _ = find_pairs(
        db, min_shared=2, min_jaccard=0.15, min_shared_override=4, min_containment=0.5,
        rare_max_df=20)
    assert _pairs_between(pair_info, 'spenser.faerie_queene.part.4', 'spenser.faerie_queene.part.6') == []
    assert _pairs_between(pair_info, 'spenser.faerie_queene.part.4', 'bunyan.pilgrims_progress') != []
    assert _pairs_between(pair_info, 'spenser.faerie_queene.part.6', 'bunyan.pilgrims_progress') != []
