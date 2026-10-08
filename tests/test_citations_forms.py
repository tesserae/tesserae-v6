"""Citation grammar forms: the four defects found 2026-09-17 on the finished
JSTOR Early Journal Content index (book lists, bare numbers, book spans,
"ff."/"f."/"sqq." open-ended ranges), plus the recall forms added after
sampling 60 pre-1923 Classics articles that mentioned Vergil/Virgil/Aeneid
but yielded no Aeneid citation. See ejc_index_2026-09-14/REPORT_v2.md for the
sample, the tally, and the before/after Cited Loci numbers.

Modeled on tests/test_scholarship.py's `_cites` tests: each assertion checks
one citation FORM against `backend.citations.extract`, not the whole
pipeline.

Needs data/citations/abbreviations.json (built from Romanello's hucitlib
data, GPL-3.0), which is deliberately not in this repository or in CI --
see backend/citations/__init__.py and research/threads/
SCHOLARSHIP_PORT_NOTES.md. Skipped as a whole when that file is absent,
rather than failing on every assertion the table would have resolved.
"""
import pytest

from backend import citations as C

pytestmark = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


def _one(text):
    """The single resolved hit from extract(text), or None."""
    hits = [h for h in C.extract(text) if h['resolved']]
    return hits[0] if hits else None


def _all_resolved(text):
    return [h for h in C.extract(text) if h['resolved']]


# --- Defect 1: book lists -------------------------------------------------

def test_comma_roman_list_is_separate_book_citations_not_one_locus():
    hits = _all_resolved('Aeneid I, II')
    assert [h['locus_start'] for h in hits] == ['1', '2']
    assert all(h['locus_end'] is None for h in hits)
    assert all(h['work_id'] == 'vergil.aeneid' for h in hits)


def test_comma_roman_list_lowercase_abbreviated():
    hits = _all_resolved('Verg. Aen. i, ii')
    assert [h['locus_start'] for h in hits] == ['1', '2']


def test_comma_roman_list_three_books():
    hits = _all_resolved('Aeneid i, ii, iii')
    assert [h['locus_start'] for h in hits] == ['1', '2', '3']


def test_whitespace_joined_roman_sequence_stays_one_multilevel_locus():
    # "Serm. II i, i" (book.poem.line, all Roman) is NOT a comma-only run --
    # the first separator is whitespace -- so it stays a single locus, not a
    # book list. This is Horace Satires (Sermones) 2.1.1.
    hit = _one('Hor. Serm. II i, i')
    assert hit is not None
    assert hit['locus_start'] == '2.1.1'


# --- Defect 2: bare numbers with no work token ----------------------------

def test_bare_number_with_no_work_anywhere_is_not_a_citation():
    assert C.extract('24. 1. transtris') == []


def test_semicolon_chain_does_not_extend_past_a_bare_number_continuation():
    # A footnote marker or list number riding a semicolon after a real
    # citation must not itself become a citation just because a work was
    # named earlier in the chain.
    hits = _all_resolved('Val. Max. 3. 4. 2 ; 1 Neue-Wagener p. 880')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '3.4.2'
    assert hits[0]['surface'] == 'Val. Max. 3. 4. 2'


def test_semicolon_chain_bare_number_ends_the_citation_not_the_sentence():
    hits = _all_resolved('Cic. Leg. 3. 6; 11; and 2. 19.')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '3.6'


def test_multilevel_semicolon_continuation_still_works():
    # A continuation ref with its OWN work is unaffected: two or more
    # levels (not a bare single number) still resolves normally even when
    # it inherits its work from an earlier ref in the chain.
    hits = _all_resolved('Hom. Il. 1,12-20; 2.240')
    assert len(hits) == 2
    assert hits[1]['surface'] == '2.240'
    assert hits[1]['locus_start'] == '2.240'


def test_bare_number_with_its_own_explicit_work_is_still_a_citation():
    hit = _one('Val. Max. 6')
    assert hit is not None
    assert hit['locus_start'] == '6'


# --- Defect 3: range depth mismatch (book span) ---------------------------

def test_book_range_with_trailing_advertisement_number_is_a_book_span():
    hit = _one('Aen. i-vi, 296')
    assert hit is not None
    assert hit['locus_start'] == '1'
    assert hit['locus_end'] == '6'
    # the trailing ", 296" (an edition's price/page count) is not folded
    # into the citation's own matched surface
    assert hit['surface'] == 'Aen. i-vi'


def test_ordinary_range_still_works():
    hit = _one('Aen. 6.847-853')
    assert hit is not None
    assert hit['locus_start'] == '6.847'
    assert hit['locus_end'] == '6.853'


def test_range_borrowing_shorthand_unaffected():
    # end has FEWER levels than start (existing borrowing rule) must still
    # work: this is the opposite case from the depth-mismatch defect.
    hit = _one('Aen. 1.124-125')
    assert hit is not None
    assert hit['locus_start'] == '1.124'
    assert hit['locus_end'] == '1.125'


# --- Defect 4: "ff."/"f."/"sqq." record only the start, open-ended --------

def test_ff_marker_records_start_only_open_ended():
    hit = _one('Aen. 1.1 ff.')
    assert hit['locus_start'] == '1.1'
    assert hit['locus_end'] is None
    assert hit['open_ended'] is True
    assert hit['open_ended_marker'] == 'ff.'


def test_f_marker_records_start_only_open_ended():
    hit = _one('Aen. 1.1 f.')
    assert hit['locus_end'] is None
    assert hit['open_ended'] is True


def test_sqq_marker_records_start_only_open_ended():
    hit = _one('Aen. 1.1 sqq.')
    assert hit['locus_end'] is None
    assert hit['open_ended'] is True


def test_ff_after_an_explicit_range_does_not_reopen_it():
    # when a real range end is already given, a trailing "ff." is a caveat
    # marker, not a reason to blank out the already-parsed end.
    hit = _one('Aen. 1.1-1.30 ff.')
    assert hit['locus_start'] == '1.1'
    assert hit['locus_end'] == '1.30'


# --- Abbreviation-table fixes, 2026-09-18 ---------------------------------
# See HOMER_DIAGNOSIS.md section 4: three abbreviations ("Rep.", "Her.",
# "Ach.") were silently resolving to the wrong author because only one
# (wrong) candidate was registered under that key, so the resolver's own
# ambiguity guard (two candidates tied at the same priority -> unresolved)
# never had a chance to fire. Fixed by registering the right work as a
# second candidate (Rep., Ach.) or, when the right work isn't in the
# corpus at all (Her. -- the Rhetorica ad Herennium isn't a Tesserae text),
# by dropping the bare form so only the combined author+work abbreviation
# resolves.

def test_rep_bare_is_ambiguous_between_cicero_and_plato():
    assert C.extract('Rep. 1') == [] or not any(h['resolved'] for h in C.extract('Rep. 1'))


def test_rep_with_plato_author_context_resolves_to_plato():
    hit = _one('Plat. Rep. 1')
    assert hit is not None
    assert hit['work_id'] == 'plato.respublica'


def test_rep_with_cicero_author_context_resolves_to_cicero():
    hit = _one('Cic. Rep. 1')
    assert hit is not None
    assert hit['work_id'] == 'cicero.de_republica'


def test_her_bare_no_longer_resolves_to_philostratus():
    # Rhetorica ad Herennium is not in the corpus, so "Her." alone is
    # simply not recognized any more -- it used to resolve, unguarded, to
    # Philostratus' Heroicus (the only work registered under this key).
    assert not any(h['resolved'] for h in C.extract('Her. 601'))


def test_her_with_philostratus_author_context_still_resolves():
    hit = _one('Philostr. Her. 601')
    assert hit is not None
    assert hit['work_id'] == 'philostratus_the_athenian.heroicus'


def test_ach_bare_is_ambiguous_between_aristophanes_and_statius():
    assert not any(h['resolved'] for h in C.extract('Ach. 1128'))


def test_ach_with_aristophanes_author_context_resolves_to_acharnians():
    for prefix in ('Ar. Ach.', 'Aristoph. Ach.'):
        hit = _one(f'{prefix} 1128')
        assert hit is not None, prefix
        assert hit['work_id'] == 'aristophanes.acharnians'


def test_ach_with_statius_author_context_still_resolves_to_achilleid():
    hit = _one('Stat. Ach. 1')
    assert hit is not None
    assert hit['work_id'] == 'statius.achilleid'


def test_pindar_bare_forms_resolve_to_odes():
    for abbr in ('Ol.', 'Pyth.', 'Py.', 'Nem.', 'Ne.', 'Isth.'):
        hit = _one(f'{abbr} 1.1')
        assert hit is not None, abbr
        assert hit['work_id'] == 'pindar.odes'


def test_pindar_is_collides_with_isaeus_and_needs_context():
    # "Is." was already registered, unguarded, to Isaeus/Dionysius on
    # Isaeus; adding Pindar's Isthmians under the same bare key makes it
    # ambiguous instead of silently wrong.
    assert not any(h['resolved'] for h in C.extract('Is. 1'))
    hit = _one('Pind. Is. 1')
    assert hit is not None
    assert hit['work_id'] == 'pindar.odes'


def test_sophocles_aj_resolves_to_ajax():
    hit = _one('Aj. 1')
    assert hit is not None
    assert hit['work_id'] == 'sophocles.ajax'


def test_aristophanes_new_plays_resolve():
    cases = {
        'Av.': 'aristophanes.birds',
        'Ra.': 'aristophanes.frogs',
        'Ran.': 'aristophanes.frogs',
        'Nub.': 'aristophanes.clouds',
        'Eq.': 'aristophanes.knights',
        'Vesp.': 'aristophanes.wasps',
        'Pax': 'aristophanes.peace',
        'Thesm.': 'aristophanes.thesmophoriazusae',
        'Eccl.': 'aristophanes.ecclesiazusae',
    }
    for abbr, work_id in cases.items():
        hit = _one(f'{abbr} 1')
        assert hit is not None, abbr
        assert hit['work_id'] == work_id, (abbr, hit)


def test_arist_ach_recall_gap_found_by_sample_hand_check():
    # "Arist." (already a heavily ambiguous author abbreviation elsewhere
    # in the table, for ~35 Aristotle works) combined with "Ach." was a
    # real recall gap found hand-checking the 2000-article sample run
    # (article jstor id in ejc_index's citations.db, "cannot be inferred
    # from Arist. Ach. 1155, where the choregus is attacked..."): only
    # "Ar."/"Aristoph." were registered as Acharnians' disambiguators.
    hit = _one('Arist. Ach. 1155')
    assert hit is not None
    assert hit['work_id'] == 'aristophanes.acharnians'


def test_plut_bare_dropped_after_sample_hand_check_found_plutarch_collision():
    # Registering bare "Plut." for Aristophanes' Plutus looked safe (no
    # OTHER candidate shares that key in the table), but hand-checking the
    # sample run found a real citation ("Plut. X Orat. 1. c. Cornel.",
    # next to "Alcib." -- a Plutarch Lives footnote) that would have been
    # silently mis-attributed. Plutarch has no bare "Plut." entry of his
    # own (he has ~80 works, so a real citation always names one), which
    # is exactly why the table-only ambiguity check missed this. Dropped
    # to the same "combined form only" fix as Her.; "Arist. Plut." is kept
    # (a real, correct citation from the same sample: "on Arist. Plut.
    # 1101: ...").
    assert not any(h['resolved'] for h in C.extract('Plut. X'))
    for prefix in ('Ar. Plut.', 'Aristoph. Plut.', 'Arist. Plut.'):
        hit = _one(f'{prefix} 1101')
        assert hit is not None, prefix
        assert hit['work_id'] == 'aristophanes.plutus'


# --- Homer forms, 2026-09-18 (HOMER_DIAGNOSIS.md) -------------------------

def test_il_with_roman_book_and_arabic_line_no_hom_needed():
    hit = _one('Il. ii. 100')
    assert hit is not None
    assert hit['work_id'] == 'homer.iliad'
    assert hit['locus_start'] == '2.100'


def test_il_with_greek_letter_book_resolves():
    hit = _one('Il. Β 100')
    assert hit is not None
    assert hit['work_id'] == 'homer.iliad'
    assert hit['locus_start'] == '2.100'


def test_od_with_greek_letter_book_resolves_without_hom():
    hit = _one('Od. λ 90')
    assert hit is not None
    assert hit['work_id'] == 'homer.odyssey'
    assert hit['locus_start'] == '11.90'


def test_odyssey_spelled_out_resolves_without_hom():
    hit = _one('Odyssey xi. 90')
    assert hit is not None
    assert hit['work_id'] == 'homer.odyssey'
    assert hit['locus_start'] == '11.90'


def test_od_book_1_4_rejected_without_context_accepted_with_hom():
    assert not any(h['resolved'] for h in C.extract('Od. ii. 10'))
    hit = _one('Hom. Od. ii. 10')
    assert hit is not None
    assert hit['work_id'] == 'homer.odyssey'
    assert hit['locus_start'] == '2.10'


def test_od_book_5_to_24_accepted_without_context():
    hit = _one('Od. xi. 90')
    assert hit is not None
    assert hit['work_id'] == 'homer.odyssey'
    assert hit['locus_start'] == '11.90'


# --- Depth-aware loci, 2026-09-18 (COMMA_CHAIN_DIAGNOSIS.md) -------------
# backend/citations/work_depth.json (built by
# scripts/citations/derive_work_depth.py from the corpus's own .tess tags)
# lets the parser tell a genuine comma-separated chain of several
# citations apart from noise (a footnote number, a publication year, a
# Stephanus/edition-page letter) accidentally swept into one fabricated
# multi-level locus. See extractor.py's _apply_work_depth.

def test_comma_chain_two_pairs_splits_into_two_citations():
    # vergil.aeneid depth 2 (book.line): "2, 283, 10, 327" is book.line,
    # book.line -- two citations, not one four-level locus.
    hits = _all_resolved('Aen. 2, 283, 10, 327')
    assert [(h['locus_start'], h['locus_end']) for h in hits] == [
        ('2.283', None), ('10.327', None),
    ]


def test_comma_chain_three_pairs_splits_into_three_citations():
    hits = _all_resolved('Aen. 3.296, 7.433, 11.270')
    assert [h['locus_start'] for h in hits] == ['3.296', '7.433', '11.270']
    assert all(h['locus_end'] is None for h in hits)


def test_trailing_bare_roman_numeral_is_dropped_not_split():
    # The remainder ("I") is a single level but the work's depth is 2 --
    # not a multiple of depth, so it's dropped, not split into its own
    # citation (and a lone Roman letter would be a suspect level even if
    # the count worked out, see _is_clean_split_level).
    hits = _all_resolved('Aen. III. 581, I')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '3.581'
    assert hits[0]['locus_end'] is None


def test_trailing_four_digit_year_is_dropped_not_split():
    # cicero.pro_archia is a depth-1 work; "1913" is a publication year,
    # not a second citation. Updated 2026-09-18 (the "Ar. Ach. 1 1 24"
    # panel fault): a depth-1 work never keeps a truncated first level at
    # all outside the OCR-digit-join case (XXII is a Roman numeral, so
    # "XXII, 1913" doesn't qualify for that) -- the whole citation is
    # dropped, not kept as a bare "22" that was never an independent
    # citation to begin with.
    assert not any(h['resolved'] for h in C.extract('Arch. XXII, 1913'))


def test_dot_joined_over_depth_locus_is_left_alone():
    # A citation that reaches past the work's depth using ONLY dots (never
    # a comma) is left untouched -- this is the corpus-resolution-gap
    # case (a work conventionally cited more precisely than this corpus's
    # tagging supports), not a fabricated chain. Also guards against a
    # real regression: "Cic. Leg." resolves (via a pre-existing, unrelated
    # abbreviation-table entry) to the depth-1 cicero.de_amicitia, so a
    # naive "always truncate when over depth" rule would mangle this bare-
    # number-continuation test case.
    hits = _all_resolved('Cic. Leg. 3. 6; 11; and 2. 19.')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '3.6'


def test_range_over_depth_is_truncated_never_split():
    # A range is never split into further citations, even when its start
    # is over-depth by the same comma-boundary shape that would split an
    # ordinary chain -- checked directly against _apply_work_depth, since
    # a real over-deep range is rare enough that no naturally-occurring
    # corpus example was worth constructing a test string around.
    from backend.citations.extractor import _apply_work_depth

    out_dict = {
        'resolved': True, 'work_id': 'vergil.aeneid',
        'locus_start': '1.124.5', 'locus_end': '1.130.9',
        'reason': None,
    }

    class _FakeRef:
        start_levels = ['1', '124', '5']
        start_seps = ['DOT', 'COMMA']  # depth is 2, boundary (index 1) is a comma

    results = _apply_work_depth(out_dict, _FakeRef())
    assert len(results) == 1
    assert results[0]['locus_start'] == '1.124'
    assert results[0]['locus_end'] == '1.130'


# --- Rep. locus-shape disambiguation, 2026-09-18 (follow-up) --------------
# REPORT_v3.md's rebuild confirmed a real cost of registering plato.
# respublica as a second candidate for "Rep.": bare "Rep." with no nearby
# author name now resolves to neither work, including genuine Plato
# citations the resolver has no author-context signal for. Stephanus
# pagination (a page number in Plato's own printed range, 327-621, plus a
# subdivision letter a-e) is a positive signal that needs no author name
# at all: Cicero's own six-book De Republica is never cited that way.

def test_rep_stephanus_locus_resolves_to_plato_without_author_context():
    hit = _one('Rep. 511 D')
    assert hit is not None
    assert hit['work_id'] == 'plato.respublica'


def test_rep_stephanus_locus_with_book_number_resolves_to_plato():
    hit = _one('Rep. VI. 511 D')
    assert hit is not None
    assert hit['work_id'] == 'plato.respublica'
    assert hit['locus_start'].startswith('6.511')


def test_rep_book_section_shape_stays_unresolved():
    # Cicero's own six-book De Republica shape: small book/section
    # numbers, no Stephanus letter. No positive signal either way, so
    # this is left unresolved, same as the plain ambiguity case.
    for text in ('Rep. 4, 7', 'Rep. 2. 1', 'Rep. 605', 'Rep. 427'):
        assert not any(h['resolved'] for h in C.extract(text)), text


def test_rep_stephanus_page_out_of_platos_range_stays_unresolved():
    # A subdivision letter alone isn't enough -- the page number must
    # actually fall in Plato's own printed Stephanus range.
    assert not any(h['resolved'] for h in C.extract('Rep. 100 A'))


def test_rep_letter_outside_a_to_e_stays_unresolved():
    assert not any(h['resolved'] for h in C.extract('Rep. 511 F'))


# --- Stephanus letters not misread as Roman numerals, 2026-09-18 ---------
# REPORT_v4.md/v5.md: Plato rows like "Rep. 514 D" and "Plato Rep. 8, 548
# C" were resolving with the Stephanus subdivision letter misread as a
# Roman numeral (D=500, C=100) and folded in as a fabricated extra locus
# level. Every plato.* work is now flagged "stephanus": true in the
# abbreviation table; resolver.py's levels_to_locus_string folds a
# trailing subdivision letter (a-e) that directly follows a plain Arabic
# page number into a lowercase suffix on that page instead of running it
# through level_to_arabic. Only applies to a stephanus-flagged work, and
# only to the letters that actually risk being misread this way (C/D are
# Roman-numeral-shaped; A/B/E aren't, so they were already being dropped
# safely -- see REPORT_v4.md's own account -- and still are).

def test_stephanus_d_not_misread_as_roman_500():
    hit = _one('Rep. 514 D')
    assert hit is not None
    assert hit['work_id'] == 'plato.respublica'
    assert hit['locus_start'] == '514d'


def test_stephanus_c_not_misread_as_roman_100_with_book_number():
    hit = _one('Plato Rep. 8, 548 C')
    assert hit is not None
    assert hit['work_id'] == 'plato.respublica'
    assert hit['locus_start'] == '8.548c'


def test_stephanus_with_leading_roman_book_number():
    hit = _one('Rep. VI. 511 D')
    assert hit is not None
    assert hit['work_id'] == 'plato.respublica'
    assert hit['locus_start'] == '6.511d'


def test_stephanus_letters_a_and_e_still_drop_safely():
    # Unaffected by this fix (they aren't Roman-numeral-shaped, so they
    # were never misread) -- confirms no regression from REPORT_v4.md's
    # own already-correct behavior.
    hit = _one('Plato Rep. 4, 425A')
    assert hit is not None
    assert hit['locus_start'] == '4.425'
    hit2 = _one('Plat. Rep. 391E')
    assert hit2 is not None
    assert hit2['locus_start'] == '391'


def test_stephanus_flag_does_not_affect_cicero():
    # cicero.de_republica has no "stephanus" flag -- a citation resolved
    # there (via explicit author context, bypassing the Rep. ambiguity)
    # is unaffected by the letter-suffix logic.
    hit = _one('Cic. Rep. 1')
    assert hit is not None
    assert hit['work_id'] == 'cicero.de_republica'
    assert hit['locus_start'] == '1'


# --- Journal-vs-corpus depth, 2026-09-18 (follow-up) -----------------------
# REPORT_v3.md's rebuild found the depth rule itself harms works whose
# scholarly citation convention is genuinely DEEPER than this corpus's own
# .tess tags: Tacitus' Annales (tagged book.chapter, cited book.chapter.
# section) had its section number silently truncated off; Plautus'
# Stichus (tagged as one flat run of line numbers, cited act.scene.line)
# had "Stich. II, 2, 31" fragmented into three separate, individually-
# wrong single-level rows. work_depth_journal.json (derive_work_depth_
# journal.py) was meant to fix this automatically, but a single-value
# mode cannot surface a genuine-but-minority deeper convention (Tacitus
# and Plautus's deeper form is real but only 14-25% of their citations),
# so the auto-derived table does not, on its own, come out above corpus
# depth for either. work_depth_overrides.json is the hand-curated fix:
# every plautus.* and terence.* work (act.scene.line, the universal
# convention for Roman comedy) and tacitus.annales/tacitus.historiae
# (book.chapter.section) at depth 3, confirmed by direct reading rather
# than derived. It is loaded after the journal table and takes
# precedence over both it and the corpus depth -- including that table's
# own "inconsistent, don't trust" exclusion (5 of the 6 Terence plays are
# flagged inconsistent in work_depth.json; the override re-enables
# truncation/split cleanup for them at the confirmed depth 3, rather than
# leaving them with no depth enforcement at all).

def _with_overrides_removed(work_ids, fn):
    """Run fn() with extractor._WORK_DEPTH_OVERRIDES temporarily patched
    to drop `work_ids`, restoring the original afterward either way --
    used to show the REAL override is what's responsible for a behavior,
    by checking it reverts when the override is taken away."""
    import backend.citations.extractor as E
    E._load_work_depth_overrides()
    original = E._WORK_DEPTH_OVERRIDES
    patched = {k: v for k, v in (original or {}).items() if k not in work_ids}
    E._WORK_DEPTH_OVERRIDES = patched
    try:
        return fn()
    finally:
        E._WORK_DEPTH_OVERRIDES = original


def test_overrides_file_has_plautus_terence_and_tacitus_at_depth_3():
    import backend.citations.extractor as E
    overrides = E._load_work_depth_overrides()
    plautus_and_terence = [k for k in overrides if k.startswith(('plautus.', 'terence.'))]
    assert len(plautus_and_terence) >= 20  # every play in the corpus, not a subset
    assert all(overrides[k] == 3 for k in plautus_and_terence)
    assert overrides['tacitus.annales'] == 3
    assert overrides['tacitus.historiae'] == 3


# --- Hand-reviewed >=50% candidates, 2026-09-18 follow-up ------------------
# From DEPTH_OVERRIDE_CANDIDATES.md, every work at >=50% share was read in
# full (not just its 3 listed examples) and judged against whether the
# second/third level reads as a genuine chapter(.section) citation
# convention or as noise (an implausibly large "chapter" number, a
# footnote marker, a pre-existing unrelated mis-resolution, or a work
# with no chapters to begin with). Six were added; the rest of that band
# were left out -- see list_depth_override_candidates.py's own docstring
# for the full reasoning on each.

def test_hand_reviewed_additions_are_in_the_overrides_file():
    import backend.citations.extractor as E
    overrides = E._load_work_depth_overrides()
    added = {
        'cicero.in_catilinam': 3,
        'athenaeus.deipnosophists': 2,
        'cicero.philippicae': 3,
        'rufus_of_ephesus.de_renum_et_vesicae_affectionibus': 3,
        'cicero.pro_a_cluentio': 2,
        'cicero.de_lege_agraria_contra_rullum': 3,
    }
    for work_id, depth in added.items():
        assert overrides.get(work_id) == depth, work_id


def test_cicero_in_catilinam_kept_whole_book_chapter_section():
    hits = _all_resolved('Cic. Cat. I 13, 31')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '1.13.31'


def test_athenaeus_kept_whole_book_page():
    hits = _all_resolved('Ath. 10, 411')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '10.411'


def test_cicero_philippicae_kept_whole_speech_chapter_section():
    hits = _all_resolved('Cic. Phil. I 6, 15')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '1.6.15'


def test_rufus_de_renum_kept_whole_book_chapter_section():
    hits = _all_resolved('Ruf. 5, 2, 21')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '5.2.21'


def test_cicero_pro_cluentio_kept_whole_chapter_section():
    hits = _all_resolved('Cluent. 32, 87')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '32.87'


def test_cicero_de_lege_agraria_kept_whole_speech_chapter_section():
    hits = _all_resolved('leg. agr. i. 5. 16')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '1.5.16'


def test_cicero_pro_sestio_left_out_of_the_overrides_file():
    # Excluded: one of the three given examples ("Sest. 34. \n\n6") carries
    # the double-newline-before-a-bare-number shape this task has already
    # identified elsewhere as a footnote marker, not a citation level.
    import backend.citations.extractor as E
    assert 'cicero.pro_sestio' not in E._load_work_depth_overrides()


def test_cicero_pro_sestio_over_deep_locus_now_dropped_not_split():
    # Updated 2026-09-18 (the "Ar. Ach. 1 1 24" panel fault, see the
    # depth-1 tests below): pro_sestio is a depth-1 work with no override,
    # so "Sest. 34, 6" -- two short digit runs -- is tried as an OCR-
    # digit-join ("346"), which falls outside pro_sestio's own line range
    # (147), so it's dropped rather than kept as two fabricated one-level
    # citations the way an earlier version of this rule would have.
    assert not any(h['resolved'] for h in C.extract('Sest. 34, 6'))


def test_aristotle_de_memoria_left_out_stays_excluded_from_the_curated_file():
    # Excluded per COMMA_CHAIN_DIAGNOSIS.md's own earlier finding (depth
    # unreliable, real convention is Bekker-page) -- not added to
    # work_depth_overrides.json, whatever the separate, auto-derived
    # journal table happens to do with it.
    import backend.citations.extractor as E
    overrides = E._load_work_depth_overrides()
    assert 'aristotle.de_memoria_et_reminiscentia' not in overrides


def test_tacitus_annales_kept_whole_via_curated_override():
    hits = _all_resolved('Tac. Ann. XIII 25, 14')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '13.25.14'
    assert hits[0]['locus_end'] is None
    assert hits[0]['reason'] is None


def test_plautus_stichus_kept_whole_via_curated_override():
    hits = _all_resolved('Stich. II, 2, 31')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '2.2.31'


def test_override_takes_precedence_reverts_when_removed():
    # Removing tacitus.annales' override falls back to the journal/corpus
    # depth path, reproducing REPORT_v3.md's own finding (the section
    # number silently dropped) -- proves the override, not something
    # else, is what keeps the citation whole above.
    hits = _with_overrides_removed(
        {'tacitus.annales'},
        lambda: _all_resolved('Tac. Ann. XIII 25, 14'),
    )
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '13.25'


def test_override_bypasses_terence_inconsistent_corpus_depth_flag():
    # terence.eunuchus is flagged inconsistent in work_depth.json (5 of
    # the 6 Terence plays are), which normally disables the truncate/
    # split rule entirely for it (no trustworthy corpus depth). With the
    # curated override (depth 3), a fabricated 4th level (a publication
    # year riding a comma) is still cleaned up.
    hits = _all_resolved('Eun. 4, 7, 27, 1904')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '4.7.27'
    assert hits[0]['reason'] == 'truncated_to_work_depth'


def test_override_removed_falls_back_to_no_enforcement_for_inconsistent_work():
    # Without the override, terence.eunuchus's own corpus depth is
    # untrusted (inconsistent), so the rule doesn't fire at all -- the
    # fabricated year level is left in place, unlike with the override.
    hits = _with_overrides_removed(
        {'terence.eunuchus'},
        lambda: _all_resolved('Eun. 4, 7, 27, 1904'),
    )
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '4.7.27.1904'


def test_cicero_pro_archia_year_noise_still_truncated_with_real_tables():
    # Regression guard, unaffected by the override file (pro_archia isn't
    # in it): cicero.pro_archia's real journal depth must stay at its
    # corpus depth (1), not the naive raw-locus mode (2) an earlier,
    # unfiltered version of derive_work_depth_journal.py gave it -- which
    # would have silently let "Arch. XXII, 1913" (a fabricated 2-level
    # locus, a publication year riding a comma) through untouched. Since
    # the 2026-09-18 depth-1 fix, the citation is dropped entirely rather
    # than kept as a bare "22" (see test_trailing_four_digit_year_is_
    # dropped_not_split).
    assert not any(h['resolved'] for h in C.extract('Arch. XXII, 1913'))


# --- Depth-1 OCR-digit-join fix, 2026-09-18 -------------------------------
# Fault seen live in the preview: pre-1923 articles with surfaces "Ar.
# Ach. 1 1 24" and "Aristoph. Ach. 1 1 28" -- OCR put spaces inside
# "1124"/"1128" -- were read as three levels, truncated to just the first
# ("1") by the ordinary depth-1 truncate rule, and shown that way in the
# connection panel. Fix, in _apply_work_depth: a depth-1 work's over-deep
# locus is never truncated to its first level any more. If every level is
# a bare 1-2 digit run (never a Roman numeral), the digits are joined
# back into one number and kept only if it's inside the work's own line
# range (work_max_line.json); otherwise the whole citation is dropped.

def test_ocr_split_digits_join_to_the_real_line_number():
    hit = _one('Ar. Ach. 1 1 24')
    assert hit is not None
    assert hit['work_id'] == 'aristophanes.acharnians'
    assert hit['locus_start'] == '1124'
    assert hit['reason'] == 'joined_ocr_split_digits'


def test_ocr_split_digits_four_levels_still_join_correctly():
    # "Ach." bare is deliberately ambiguous (aristophanes.acharnians vs
    # statius.achilleid, see the earlier "Ach." abbreviation-table fix),
    # so this uses "Ar. Ach." for author context -- the point under test
    # is the join across FOUR short-digit-run levels, not the author
    # guard.
    hit = _one('Ar. Ach. 1 1 2 4')
    assert hit is not None
    assert hit['work_id'] == 'aristophanes.acharnians'
    assert hit['locus_start'] == '1124'


def test_plautus_stichus_override_unaffected_by_depth_1_join_rule():
    # plautus.stichus' effective depth is 3 (the curated override), not
    # 1 -- the new depth-1-only join/drop rule must not touch it.
    hits = _all_resolved('Stich. II, 2, 31')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '2.2.31'


def test_terence_eunuchus_override_still_truncates_normally():
    # terence.eunuchus' effective depth is 3 (the curated override), not
    # 1 -- the ordinary comma-boundary truncate/split path still applies,
    # unaffected by the new depth-1-only rule.
    hits = _all_resolved('Eun. 4, 7, 27, 1904')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '4.7.27'
    assert hits[0]['reason'] == 'truncated_to_work_depth'


def test_join_rejected_when_a_level_is_a_roman_numeral():
    from backend.citations.extractor import _join_short_digit_levels
    assert _join_short_digit_levels(['1', '1', '24']) == '1124'
    assert _join_short_digit_levels(['XXII', '1913']) is None
    assert _join_short_digit_levels(['1', '124']) is None  # '124' is 3 digits
    assert _join_short_digit_levels([]) is None


def test_join_out_of_range_is_dropped_not_kept():
    from backend.citations.extractor import _apply_work_depth

    out_dict = {
        'resolved': True, 'work_id': 'aristophanes.acharnians',
        'locus_start': '99.99', 'locus_end': None, 'reason': None,
    }

    class _FakeRef:
        start_levels = ['99', '99']  # joins to 9999, far outside Acharnians' 1234 lines
        start_seps = [None]

    assert _apply_work_depth(out_dict, _FakeRef()) == []


# --- Second override pass, 2026-09-18 (cicero.de_oratore + 30-50% band) ---
# cicero.de_oratore added as directed (book.chapter.section, confirmed by
# a very consistent "book I, increasing chapter, section" pattern in
# citations_v2.db -- "Cic. de Orat. I, 10, 41" through "Cic. De orat.
# i. 35. 164", chapters climbing steadily through book I). Scanning
# DEPTH_OVERRIDE_CANDIDATES.md's 30-50% band for other clean conventions
# (full citation lists read, not just the report's 3 examples each) added
# six more: cicero.de_officiis, cicero.academica, cicero.de_natura_deorum
# (all book.chapter.section, each with steadily climbing chapter numbers
# within a book -- a strong positive signal, not just a plausible shape);
# cicero.pro_publio_quinctio, cicero.pro_balbo, cicero.de_domo_sua (single-
# speech chapter.section, each with the same chapter cited at different,
# consecutive sections in the data, e.g. Quinctio "26, 80" / "26, 81" /
# "26, 82"). Left out: cicero.orator (one of its own 3 examples, "Orat.
# 839 d", is far too large to be a real section in a ~238-section work,
# and its first level is almost always the fixed placeholder "I"/"1", not
# a real varying chapter -- the same red flag that excluded aristotle.
# de_memoria_et_reminiscentia in the first pass) and claudius_ptolemaeus.
# musica (same fixed-"I"-placeholder pattern, plus a direct year example,
# "Mus., I (1897), 66" -- also flagged inconsistent in work_depth.json, so
# it was never going to be touched without an override anyway).
# plautus.cistellaria, also in this band, was already covered by the
# blanket plautus.* entry.

def test_cicero_de_oratore_and_second_pass_additions_are_in_the_overrides_file():
    import backend.citations.extractor as E
    overrides = E._load_work_depth_overrides()
    added = {
        'cicero.de_oratore': 3,
        'cicero.de_officiis': 3,
        'cicero.academica': 3,
        'cicero.de_natura_deorum': 3,
        'cicero.pro_publio_quinctio': 2,
        'cicero.pro_balbo': 2,
        'cicero.de_domo_sua': 2,
    }
    for work_id, depth in added.items():
        assert overrides.get(work_id) == depth, work_id


def test_cicero_de_oratore_kept_whole_book_chapter_section():
    hits = _all_resolved('Cic. de Or. I 22, 104')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '1.22.104'


def test_cicero_de_officiis_kept_whole():
    hits = _all_resolved('Cic. Off. I 16, 52')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '1.16.52'


def test_cicero_pro_balbo_kept_whole():
    hits = _all_resolved('Balb. 28, 64')
    assert len(hits) == 1
    assert hits[0]['locus_start'] == '28.64'


def test_cicero_orator_and_ptolemy_musica_left_out_of_overrides():
    import backend.citations.extractor as E
    overrides = E._load_work_depth_overrides()
    assert 'cicero.orator' not in overrides
    assert 'claudius_ptolemaeus.musica' not in overrides


# --- "Cri."/"Dom." collisions, 2026-09-18 (REPORT_v6.md hand check) -------
# "Cri." was resolving unguarded to plato.crito, but 3/15 sampled rows
# were Cynewulf's Old English poem "Christ" (Anglo-Saxon philology
# articles, alongside sibling abbreviations "Beo."/"Gu."/"Dan."/"Ex."/
# "Gen." for other Old English poems). Christ isn't in this corpus, so
# this is the same fix as "Her.": drop the bare form, keep only combined
# author+work forms. "Dom." was resolving unguarded to cicero.de_domo_sua,
# but 4/15 sampled rows were Suetonius's Domitian ("Dom. 8" explicitly
# "Suet. Dom. 8" in the sentence) plus unrelated Spanish/Hebrew noise.
# Suetonius's Domitian IS in this corpus (suetonius.de_vita_caesarum.
# part.12.domitian) -- same fix as "Rep."/"Ach.": register it as a second
# candidate so the resolver's own ambiguity guard applies to the bare
# form, disambiguated by "Suet. Dom." vs "Cic. Dom.".

def test_cri_bare_no_longer_resolves_to_plato():
    assert not any(h['resolved'] for h in C.extract('Cri. 44'))


def test_cri_with_plato_author_context_resolves():
    for prefix in ('Plat. Cri.', 'Plato. Cri.', 'Pl. Cri.'):
        hit = _one(f'{prefix} 44')
        assert hit is not None, prefix
        assert hit['work_id'] == 'plato.crito'


def test_dom_bare_is_ambiguous_between_cicero_and_suetonius():
    assert not any(h['resolved'] for h in C.extract('Dom. 8'))


def test_dom_with_suetonius_author_context_resolves_to_domitian():
    hit = _one('Suet. Dom. 8')
    assert hit is not None
    assert hit['work_id'] == 'suetonius.de_vita_caesarum.part.12.domitian'


def test_dom_with_cicero_author_context_still_resolves_to_de_domo_sua():
    hit = _one('Cic. Dom. 8')
    assert hit is not None
    assert hit['work_id'] == 'cicero.de_domo_sua'


# --- "Pis."/"Mus." collisions, 2026-09-19 (ABBREVIATION_COLLISION_CANDIDATES.md) --
# The largest two candidates from the "over 100 citations, single
# candidate" scan turned out to be almost pure noise on a 20-surface hand
# read each: "Pis." (cicero.in_l_pisonem) is overwhelmingly bibliographic
# apparatus, "pis." for "pls."/"plates" (0/20 genuine); "Mus." (claudius_
# ptolemaeus.musica) is overwhelmingly "Rh. Mus."/"B. Metr. Mus." (the
# journal Rheinisches Museum, the Metropolitan Museum bulletin) or French
# "Musee" (0/20 genuine). Same fix as "Her."/"Cri.": drop the bare form,
# keep only the combined author+work forms already registered ("Cic.
# Pis.", "Ptol. Mus.").

def test_pis_bare_no_longer_resolves():
    assert not any(h['resolved'] for h in C.extract('Pis. 8'))


def test_pis_with_cicero_author_context_resolves():
    hit = _one('Cic. Pis. 8')
    assert hit is not None
    assert hit['work_id'] == 'cicero.in_l_pisonem'


def test_mus_bare_no_longer_resolves():
    assert not any(h['resolved'] for h in C.extract('Mus. I 104'))


def test_mus_with_ptolemy_author_context_resolves():
    hit = _one('Ptol. Mus. I 104')
    assert hit is not None
    assert hit['work_id'] == 'claudius_ptolemaeus.musica'


# --- Year-like single-level locus for a depth-1 work, 2026-09-19 ---------
# REPORT_v7.md section 5: a single-level, four-digit locus for a depth-1
# work was never checked by _apply_work_depth's over-deep guard at all
# (it matches the work's own depth exactly, so it's never "over-deep").
# "Arch. 1888" ("Archaeologischer Anzeiger 1888, pp. 193 ff.", a journal
# volume year) resolved to cicero.pro_archia -- a 32-section speech --
# exactly like a genuine section number would.

def test_arch_year_is_dropped():
    hits = C.extract('Arch. 1888, pp. 193 ff. and 281 ff.')
    assert not any(h['resolved'] for h in hits)


def test_arch_ordinary_section_number_still_resolves():
    hit = _one('Arch. 12')
    assert hit is not None
    assert hit['work_id'] == 'cicero.pro_archia'
    assert hit['locus_start'] == '12'


def test_aen_year_shaped_book_only_locus_is_unaffected():
    # vergil.aeneid is depth 2 (book.line): a bare "1888" here is an
    # ordinary UNDER-deep book-only citation (an existing, accepted class
    # this guard doesn't touch), not a single-level locus matching the
    # work's own depth -- this guard never even looks at it.
    hit = _one('Aen. 1888')
    assert hit is not None
    assert hit['work_id'] == 'vergil.aeneid'
    assert hit['locus_start'] == '1888'


def test_depth_1_work_with_long_line_range_keeps_a_genuine_in_range_locus():
    # lucretius.de_rerum_natura turns out to be depth 2 (book.line), not
    # depth 1 -- aristophanes.birds is an actual depth-1 work (one flat
    # run of line numbers) with more than 1700 lines
    # (work_max_line.json), so a plausible-year-shaped locus inside that
    # range, with no bibliographic context around it, is kept.
    hit = _one('Av. 1700')
    assert hit is not None
    assert hit['work_id'] == 'aristophanes.birds'
    assert hit['locus_start'] == '1700'


def test_in_range_locus_still_dropped_with_trailing_page_marker():
    assert not any(h['resolved'] for h in C.extract('Av. 1700, pp. 5'))


def test_out_of_range_locus_still_dropped_when_parenthesized():
    assert not any(h['resolved'] for h in C.extract('(Arch. 1888)'))


def test_in_range_parenthesized_locus_is_kept_not_dropped():
    # Regression guard: an earlier version of this guard also treated
    # "wrapped alone in parentheses" as bibliographic on its own, which
    # wrongly dropped genuine citations written the ordinary way -- "(Ar.
    # Av. 1714)" is a real line of Aristophanes' 1,765-line Birds, not a
    # publication year, and parenthesised citations are completely
    # routine in this genre. Only the range check (not parenthesization)
    # should decide this.
    hit = _one('cf. some phrase (Ar. Av. 1714).')
    assert hit is not None
    assert hit['work_id'] == 'aristophanes.birds'
    assert hit['locus_start'] == '1714'


def test_trailing_in_range_number_on_a_comma_is_kept_not_dropped():
    # Regression guard: "Aristoph. Av. 1745 ff., 1749 ff." is a genuine
    # list of two separate line citations to the same work (both well
    # within its 1,765-line range), not a list of bibliographic years --
    # an earlier version of this guard flagged ANY four-digit number
    # riding a trailing comma, which wrongly dropped this.
    hit = _one('Aristoph. Av. 1745 ff., 1749 ff.')
    assert hit is not None
    assert hit['work_id'] == 'aristophanes.birds'
    assert hit['locus_start'] == '1745'
