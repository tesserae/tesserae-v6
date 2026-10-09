"""scripts/events/build_event_dossier.py: the parts that need no name recogniser and no
production data: date conversion and overlap, distance, reference parsing and overlap,
ranking, overlap suppression, name keys. Loaded via importlib, as scripts/ is not a package."""
import importlib.util
import os

_P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "events", "build_event_dossier.py")
_spec = importlib.util.spec_from_file_location("build_event_dossier", _P)
bed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bed)


def test_wikidata_year_is_astronomical():
    # Wikidata stores 424 BC as -0423 (there is a year 0), 31 BC as -0030, AD 9 as 0009
    assert bed.wikidata_year("-0423-01-01T00:00:00Z") == -424
    assert bed.wikidata_year("-0030-08-31T00:00:00Z") == -31
    assert bed.wikidata_year("0009-09-01T00:00:00Z") == 9
    assert bed.wikidata_year("0000-01-01T00:00:00Z") == -1
    assert bed.wikidata_year("junk") is None


def test_event_span_uses_all_dates():
    rec = {"point_in_time": [], "start": ["-0051-07-01T00:00:00Z"], "end": ["-0051-09-01T00:00:00Z"]}
    assert bed.event_span(rec) == (-52, -52)
    rec = {"point_in_time": [], "start": ["-0414-01-01T00:00:00Z"], "end": ["-0412-01-01T00:00:00Z"]}
    assert bed.event_span(rec) == (-415, -413)
    assert bed.event_span({"point_in_time": [], "start": [], "end": []}) is None


def test_ranges_overlap_with_margin():
    assert bed.ranges_overlap(-424, -424, -430, -401)
    assert not bed.ranges_overlap(-424, -424, -400, -300)
    assert bed.ranges_overlap(-424, -424, -414, -300, margin=10)       # -434..-414 reaches -414
    assert not bed.ranges_overlap(-424, -424, -413, -300, margin=10)
    assert bed.ranges_overlap(-424, -424, -424, -424)                   # closed interval


def test_haversine_known_distances():
    athens, sparta = (37.9838, 23.7275), (37.0733, 22.4297)
    assert 150 < bed.haversine_km(athens, sparta) < 156
    assert bed.haversine_km(athens, athens) == 0
    rome, carthage = (41.9, 12.5), (36.85, 10.32)
    assert 585 < bed.haversine_km(rome, carthage) < 600


def test_min_distance_and_parse_point():
    assert bed.parse_point("Point(23.66 38.34)") == (38.34, 23.66)
    assert bed.parse_point("nonsense") is None
    near = bed.min_distance_km((38.34, 23.66), [(38.0, 23.0), (38.35, 23.67)])
    assert near < 2
    assert bed.min_distance_km((0, 0), []) is None


def test_name_key_matches_index_algorithm():
    assert bed.name_key("Ἀθηναῖος") == "atena"
    assert bed.name_key("Athenae") == "atena"
    assert bed.name_key("Boeotia") == bed.name_key("Βοιωτία") == "boiot"
    assert bed.name_key("Abc") is None            # under four letters
    assert bed.label_keys("Battle of Delium") == {"deliu"}        # "battle" and "of" are stop words; Greek Δήλιον keys to "delio"
    assert "pelop" in bed.label_keys("Peloponnesian War")


def test_label_variants_drop_praenomina():
    v = bed.label_variants(["Gaius Terentius Varro"])
    assert v == [frozenset({"teren", "uarro"})]


def test_parse_ref_and_overlap():
    assert bed.parse_ref("thuc. pele. 4.89.1") == (4, 89, 1)
    assert bed.parse_ref("plut. ant. 62.1") == (62, 1)
    assert bed.parse_ref("livy. urbe. 1.pr.1") == (1, 0, 1)
    assert bed.parse_ref("no locus here") == ()
    # a book.chapter range matches a book.chapter.section window on the shared prefix
    assert bed.loci_overlap((4, 89), (4, 101), (4, 90, 1), (4, 93, 2))
    assert not bed.loci_overlap((4, 89), (4, 101), (4, 102, 1), (4, 110, 1))
    assert not bed.loci_overlap((4, 89), (4, 101), (), ())
    # a range crossing a book boundary
    assert bed.loci_overlap((3, 10), (4, 5), (4, 1, 1), (4, 3, 1))


def test_base_work_strips_parts():
    assert bed.base_work("thucydides.peleponnesian_war.part.4") == "thucydides.peleponnesian_war"
    assert bed.base_work("livy.ab_urbe_condita.part.2.books_21-30") == "livy.ab_urbe_condita"
    assert bed.base_work("polybius.histories") == "polybius.histories"


def test_ranking_prefers_more_and_rarer_names():
    # count: two names beat one; a context-only match (0.5) ranks below a place match (1)
    two = bed.entity_score(["place", "participant"], [3.0, 3.0], "count")
    one = bed.entity_score(["place"], [9.0], "count")
    ctx = bed.entity_score(["context"], [9.0], "count")
    assert two > one > ctx
    # idf2: one very rare name outranks two common ones
    assert bed.entity_score(["place"], [10.0], "idf2") > bed.entity_score(["place", "participant"], [3.0, 3.0], "idf2")
    ranked = sorted([bed.rank_key(1.0, 5.0), bed.rank_key(2.0, 1.0), bed.rank_key(1.0, 9.0)])
    assert ranked == [bed.rank_key(2.0, 1.0), bed.rank_key(1.0, 9.0), bed.rank_key(1.0, 5.0)]


def test_suppress_overlaps_keeps_best_of_adjacent_windows():
    items = [("w1", (4, 89), (4, 95)), ("w1", (4, 92), (4, 99)), ("w2", (4, 90), (4, 96)), ("w1", (4, 120), (4, 126))]
    kept = bed.suppress_overlaps(items, lambda x: x)
    assert kept == [items[0], items[2], items[3]]       # the second overlaps the first in the same work only


def test_specific_locations_drop_country_only():
    rec = {"qid": "Q1", "locations": [{"qid": "Q41", "label": "Greece"}, {"qid": "Q2", "label": "Delium", "pleiades": "540000"}]}
    cs = {"Q1": {"p17": ["Q41"], "p276": ["Q2"]}}
    assert [l["label"] for l in bed.specific_locations(rec, cs)] == ["Delium"]
    # without a Pleiades id, a location listed under P276 is kept alongside
    rec2 = {"qid": "Q3", "locations": [{"qid": "Q41", "label": "Greece"}, {"qid": "Q9", "label": "Farsala"}]}
    cs2 = {"Q3": {"p17": ["Q41"], "p276": ["Q9"]}}
    assert [l["label"] for l in bed.specific_locations(rec2, cs2)] == ["Farsala"]


def test_score_of_names_weights_by_role_and_rarity():
    class P:
        n_windows = 1000
        name_df = {"a": 10, "b": 500}
    ents = [{"role": "place"}, {"role": "context"}]
    em = {0: {"a"}, 1: {"b"}}
    # idf2 default: place idf^2 + 0.5 * context idf^2
    import math
    expect = math.log(100) ** 2 + 0.5 * math.log(2) ** 2
    assert abs(bed.score_of_names(ents, em, P) - expect) < 1e-9


def test_norm_full_is_key_without_the_cut():
    assert bed.norm_full("Δήλιον") == "delion"
    assert bed.norm_full("Delium") == "delium"
    assert bed.name_key("Delium") == bed.norm_full("Delium")[:5] == "deliu"
    assert bed.name_key("Delio") == "delio"            # why the key cannot tell the cases of one name


def test_stem_matching_accepts_endings_but_not_other_stems():
    stem = lambda w: bed.stem_form(bed.norm_full(w))
    # Delium, Delio, Delii and Greek Δήλιον / Δηλίῳ share one stem
    assert {stem(w) for w in ["Delium", "Delio", "Delii", "Δήλιον", "Δηλίῳ"]} == {"deli"}
    # Delius (Apollo's epithet) and Germanicus are other stems
    assert stem("Delius") != stem("Delium")
    assert stem("Germanicus") != stem("Germani")
    assert stem("Germanos") == stem("Germani") == "german"
    # a stem that ends in a consonant takes -us
    assert {stem(w) for w in ["Varus", "Vari", "Varum"]} == {"uar"}
    # a stem is never cut below three letters
    assert stem("Roma") == "rom" and stem("Rus") == "rus"


def test_name_stems_ius_expansion_is_off_by_default_and_name_side_only():
    assert bed.name_stems("arminius") == {"arminius"}
    bed.IUS_EXPANSION = True
    try:
        assert bed.name_stems("arminius") == {"arminius", "armini", "armin"}
        assert bed.name_stems("delium") == {"deli"}         # no expansion for -um
        assert bed.stem_form(bed.norm_full("Delius")) not in bed.name_stems("delium")
    finally:
        bed.IUS_EXPANSION = False
