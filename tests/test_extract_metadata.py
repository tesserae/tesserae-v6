"""Unit tests for scripts/documents/extract_metadata.py against the small
real EpiDoc samples in tests/fixtures/epidoc/ (stage 1's own fixtures,
reused here: this stage reads the same raw TEI files, just more of each).

These tests exercise the extractor only. They do not touch the search
index, the backend app, any file under /var/www, or the full (not
committed) tesserae-docs corpus; the one full-corpus run lives in the
coverage report, not here.
"""
import csv
import os
import sys

import pytest
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "epidoc")
EAGLE_CSV = os.path.join(ROOT, "data", "documents", "eagle_labels.csv")

sys.path.insert(0, os.path.join(ROOT, "scripts", "documents"))
import extract_metadata as em  # noqa: E402


@pytest.fixture(scope="module")
def eagle():
    return em.EagleLabels(EAGLE_CSV)


def parse(source, filename):
    return etree.parse(os.path.join(FIXTURES, source, filename)).getroot()


def eagle_csv_label(vocabulary, uri):
    """The committed English label for one EAGLE vocabulary URI, read
    straight from the CSV (not hardcoded), so a test only checks that the
    extractor matches what the mapping table actually says."""
    with open(EAGLE_CSV, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    for row in csv.DictReader(lines):
        if row["vocabulary"] == vocabulary and row["uri"] == uri:
            return row["english_label"]
    raise AssertionError(f"{vocabulary} {uri} not in {EAGLE_CSV}")


# ---------------------------------------------------------------------------
# Tier 1: licence + source link, per source
# ---------------------------------------------------------------------------

def test_edh_licence_present():
    root = parse("edh", "HD000001.xml")
    name, url = em.extract_licence(root)
    assert "Creative Commons" in name
    assert url == "http://creativecommons.org/licenses/by-sa/4.0/"


def test_edh_source_url_uses_canonical_pattern_not_file_domain(eagle):
    """HD000001.xml's own <idno type="URI"> points at the old
    edh-www.adw.uni-heidelberg.de domain; build_credit must use the
    canonical https://edh.ub.uni-heidelberg.de pattern instead (per the
    stage 3a spec), not whatever the file itself happens to carry."""
    root = parse("edh", "HD000001.xml")
    fields = em.extract_from_root(root, eagle, "edh")
    assert "edh-www.adw" in fields["source_uri"]  # the file's own (stale) idno
    rec = {"id": "edh:HD000001", "tm_id": 251193, "edh_id": "HD000001"}
    credit = em.build_credit("edh", rec, None, None, fields, "HD000001")
    assert credit["source_url"] == "https://edh.ub.uni-heidelberg.de/edh/inschrift/HD000001"
    assert credit["source_name"] == "Epigraphic Database Heidelberg"


def test_edr_licence_and_source_url(eagle):
    root = parse("edr", "aEDR000006.xml")
    fields = em.extract_from_root(root, eagle, "edr")
    assert fields["licence_name"]
    rec = {"id": "edr:aEDR000006", "tm_id": 261496, "edr_id": "EDR000006"}
    credit = em.build_credit("edr", rec, None, None, fields, "EDR000006")
    assert credit["source_url"] == (
        "http://www.edr-edr.it/edr_programmi/res_complex_comune.php?id_nr=EDR000006"
    )
    assert credit["source_name"] == "Epigraphic Database Roma"


def test_isicily_licence_and_source_url(eagle):
    root = parse("isicily", "ISic000005.xml")
    fields = em.extract_from_root(root, eagle, "isicily")
    assert fields["licence_url"] == "http://creativecommons.org/licenses/by/4.0/"
    rec = {"id": "isicily:ISic000005", "tm_id": 491502}
    credit = em.build_credit("isicily", rec, None, None, fields, "ISic000005")
    assert credit["source_url"] == "http://sicily.classics.ox.ac.uk/inscription/ISic000005"
    assert credit["source_name"] == "I.Sicily"


def test_papyri_licence_from_ddbdp_and_source_url_from_hgv_pattern(eagle):
    ddbdp_root = parse("papyri", "8666.xml")
    fields = em.extract_from_root(ddbdp_root, eagle, "papyri")
    assert "Creative Commons" in fields["licence_name"]
    rec = {"id": "papyri:8666", "tm_id": 8666, "hgv_id": 8666}
    credit = em.build_credit("papyri", rec, None, None, fields, 8666)
    assert credit["source_url"] == "https://papyri.info/hgv/8666"


def test_trismegistos_url_from_tm_id():
    rec = {"id": "edh:HD000001", "tm_id": 251193}
    credit = em.build_credit("edh", rec, None, None, {}, "HD000001")
    assert credit["trismegistos_url"] == "https://www.trismegistos.org/text/251193"


# ---------------------------------------------------------------------------
# Tier 1: principal edition citation, per source
# ---------------------------------------------------------------------------

def test_edh_principal_edition():
    root = parse("edh", "HD000001.xml")
    pe = em.extract_principal_edition_plain(root)
    assert pe  # the first <bibl> under div[@type='bibliography']


def test_edr_principal_edition():
    root = parse("edr", "aEDR000006.xml")
    pe = em.extract_principal_edition_plain(root)
    assert pe


def test_isicily_principal_edition_prefers_corpus_bibl():
    root = parse("isicily", "ISic000001.xml")
    pe = em.extract_principal_edition_isicily(root)
    assert pe == "CIL 7190"


def test_papyri_principal_edition_from_hgv_principal_edition_div():
    hgv_root = parse("papyri", "hgv_8666.xml")
    pe = em.extract_principal_edition_hgv(hgv_root)
    assert pe == "SB 18 13224"


def test_papyri_principal_edition_falls_back_to_ddbdp_bibl_when_hgv_missing():
    # hgv_99999.xml (synthetic fixture) carries no principalEdition div;
    # 99999.xml's own sourceDesc/bibl is the fallback the caller must use.
    hgv_root = parse("papyri", "hgv_99999.xml")
    assert em.extract_principal_edition_hgv(hgv_root) is None
    ddbdp_root = parse("papyri", "99999.xml")
    pe = em.extract_principal_edition_ddbdp(ddbdp_root)
    assert pe == "P.Test. 99 9999"


# ---------------------------------------------------------------------------
# Tier 2: EAGLE vocabulary term mapped to English
# ---------------------------------------------------------------------------

def test_eagle_typeins_term_mapped_to_english_edh(eagle):
    root = parse("edh", "HD000001.xml")
    label, native, uri = em.extract_text_type(root, eagle)
    # native is always THIS document's own term text (German, for EDH),
    # never the CSV's single representative spelling for the URI (which
    # happens to be EDR's Latin "sepulcralis": the two sources tag the
    # very same EAGLE concept in different languages).
    assert native == "Grabinschrift"
    assert uri == "http://www.eagle-network.eu/voc/typeins/lod/92"
    assert label == eagle_csv_label("typeins", uri)
    assert label == "Epitaph"


def test_eagle_typeins_term_mapped_to_english_edr(eagle):
    root = parse("edr", "aEDR000006.xml")
    label, native, uri = em.extract_text_type(root, eagle)
    assert native == "sepulcralis"  # EDR's own (Latin) term text, kept as given
    assert label == "Epitaph"  # same EAGLE concept (lod/92) as EDH's Grabinschrift


def test_isicily_text_type_is_already_english_not_eagle(eagle):
    """I.Sicily tags text type from its OWN ontology
    (ontology.inscriptiones.org), not EAGLE's; the term is already
    English and must be kept as the label without a lookup."""
    root = parse("isicily", "ISic000001.xml")
    label, native, uri = em.extract_text_type(root, eagle)
    assert native == "funerary"
    assert label == "funerary"
    assert "ontology.inscriptiones.org" in uri


def test_papyri_material_free_text_mapped_via_committed_table(eagle):
    """papyri.info/HGV's own `material` field is plain text with no ref
    at all (unlike EDH/EDR/I.Sicily's EAGLE-linked material); this is
    the by_label fallback path, fed by the hand_mapped_papyri_free_text
    rows added to eagle_labels.csv."""
    label, native, uri = eagle.lookup("material", None, "Papyrus")
    assert label == "papyrus"
    label2, native2, uri2 = eagle.lookup("material", None, "Ostrakon")
    assert label2 == "ostracon"


def test_papyri_text_type_free_text_mapped_via_committed_table(eagle):
    """papyri.info/HGV's own document-type keyword, same no-ref path,
    reusing the "typeins" vocabulary bucket EDH/EDR's own typeins
    uses."""
    label, native, uri = eagle.lookup("typeins", None, "Quittung")
    assert label == "receipt"


def test_non_eagle_vocab_ref_keeps_already_english_native_text(eagle):
    """I.Sicily tags some objectType values against OTHER open
    vocabularies instead of EAGLE's (kerameikos.org pottery-shape ids,
    Getty AAT): already-English terms with no EAGLE URI to look up.
    `extract_vocab_field` must use the native text as the label rather
    than leaving it unmapped."""
    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/>'
        '<text><body><div><objectType ref="http://kerameikos.org/id/kylix">'
        'kylix</objectType></div></body></text></TEI>'
    )
    root = etree.fromstring(xml.encode("utf-8"))
    label, native, uri = em.extract_vocab_field(root, "objectType", "objtyp", eagle)
    assert label == "kylix"
    assert native == "kylix"


def test_eagle_vocab_normalize_uri_handles_source_variants():
    norm = em.EagleLabels.normalize_uri
    # https scheme (I.Sicily) must key the same as http (EDH/EDR)
    assert norm("https://www.eagle-network.eu/voc/objtyp/lod/259.html") == (
        "http://www.eagle-network.eu/voc/objtyp/lod/259"
    )
    # missing slash before the numeric id
    assert norm("http://www.eagle-network.eu/voc/material/lod6") == (
        "http://www.eagle-network.eu/voc/material/lod/6"
    )
    # a stray internal space
    assert norm("http://www.eagle-network.eu/voc/typeins/l od/112") == (
        "http://www.eagle-network.eu/voc/typeins/lod/112"
    )


# ---------------------------------------------------------------------------
# Tier 3: translation (I.Sicily only), image links, dimensions, museum
# ---------------------------------------------------------------------------

def test_isicily_translation_captured():
    root = parse("isicily", "ISic000014.xml")
    translation = em.extract_div_text(root, "translation")
    assert translation
    assert "Julia Augusta" in translation


def test_isicily_translation_empty_when_source_left_it_blank():
    """ISic000046's <div type="translation"> is present but carries only
    a comment placeholder, no text (common in I.Sicily before a
    translation is added): this is a miss, not a crash."""
    root = parse("isicily", "ISic000046.xml")
    translation = em.extract_div_text(root, "translation")
    assert translation is None


def test_isicily_image_links_captured():
    # ISic000001's <graphic> elements are live; ISic000005's equivalents
    # are present in the fixture but inside an XML comment (the source
    # withheld them pending a later addition), so they must NOT surface.
    root = parse("isicily", "ISic000001.xml")
    images = em.extract_images(root)
    assert len(images) >= 1
    assert any(url.endswith(".jpg") or url.endswith(".tif") for url in images)
    assert em.extract_images(parse("isicily", "ISic000005.xml")) == []


def test_edr_image_link_from_facsimile():
    root = parse("edr", "aEDR000006.xml")
    images = em.extract_images(root)
    assert images  # aEDR000006 carries a <facsimile><graphic url=...>


def test_edh_museum_and_dimensions_present_when_source_fills_them():
    root = parse("edh", "HD000003.xml")
    assert em.extract_museum(root)
    dims = em.extract_dimensions(root)
    assert dims
    assert "height" in dims


def test_isicily_letter_height_per_line():
    root = parse("isicily", "ISic000001.xml")
    lh = em.extract_letter_height(root)
    assert lh  # ISic000001 carries per-line letterHeight dimensions


# ---------------------------------------------------------------------------
# A missing field never drops the record
# ---------------------------------------------------------------------------

def test_missing_raw_file_still_produces_a_documents_row():
    """A merged-corpus record whose raw file cannot be found must still
    get a `documents` row (built from the merged-corpus fields alone),
    with tier 1-3 fields left None/empty and the miss counted, not an
    exception and not a dropped document."""
    indices = {
        "edh": {}, "edr": {}, "isicily": {},
        "papyri_ddbdp": {}, "papyri_hgv": {},
    }
    eagle = em.EagleLabels(EAGLE_CSV)
    stats = em.Stats()
    rec = {
        "id": "edh:HD999999", "source": "edh", "tm_id": 999999,
        "edh_id": "HD999999", "hgv_id": None, "edr_id": None, "edcs_id": None,
        "languages": ["la"], "bilingual": False,
        "date_not_before": 100, "date_not_after": 200,
        "findspot": {"ancient_place": None, "modern_place": None,
                     "region": None, "pleiades_id": None},
    }
    result = em.process_record(rec, indices, eagle, stats)
    row = result["row"]
    assert row["id"] == "edh:HD999999"
    assert row["date_not_before"] == 100
    # tier 2/3 fields that only the (unreachable) raw file could supply
    # are left None, not fabricated or defaulted:
    assert row["text_type_label"] is None
    assert row["principal_edition"] is None
    assert result["display_rows"] == []
    # tier 1 credit still gets the source's own constant licence/URL
    # pattern (known statically, from SOURCES.md, independent of
    # reading this document's own file):
    assert row["licence_name"] == "CC BY-SA 4.0"
    assert row["source_url"] == "https://edh.ub.uni-heidelberg.de/edh/inschrift/HD999999"
    assert stats.misses[("edh", "raw_file_missing")] == 1


def test_eagle_labels_csv_has_no_duplicate_keys():
    """Caught once by PR review: a malformed double-scheme-prefix ref
    (objtyp/lod/259) got normalized into a SECOND row for a (vocabulary,
    uri) key that already had a correctly-fetched SKOS row, and
    EagleLabels.by_uri's last-row-wins loading silently let the weaker
    hand-mapped label shadow the real one for every document tagged
    with that URI. This asserts the committed CSV can never have two
    rows for the same key again."""
    with open(EAGLE_CSV, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    rows = list(csv.DictReader(lines))
    keys = [(r["vocabulary"], r["uri"]) for r in rows]
    assert len(keys) == len(set(keys)), (
        "duplicate (vocabulary, uri) rows in eagle_labels.csv silently "
        "shadow each other when EagleLabels loads the file"
    )


def test_eagle_lookup_resolves_known_duplicate_uri_to_the_skos_label(eagle):
    label, native, uri = eagle.lookup(
        "objtyp", "http://www.eagle-network.eu/voc/objtyp/lod/259", "plaque")
    assert label == "Inscribed plaque"


def test_eagle_lookup_unmapped_eagle_uri_keeps_native_text(eagle):
    """An EAGLE-network ref this corpus never saw (so it is not in the
    CSV at all) must degrade to the document's own native text, not
    None and not an exception -- this is the "never drops a field"
    guarantee for a genuine EAGLE-vocabulary miss, as distinct from the
    non-EAGLE-vocabulary case (`extract_vocab_field`'s own fallback,
    tested separately via I.Sicily's kerameikos.org/Getty refs)."""
    label, native, uri = eagle.lookup(
        "objtyp", "http://www.eagle-network.eu/voc/objtyp/lod/999999", "invented term")
    assert label is None
    assert native == "invented term"


def test_missing_optional_field_within_a_found_file_does_not_raise(eagle):
    """HD000058.xml (fixture) has blank <dimensions> children; extracting
    it must return None, not raise."""
    root = parse("edh", "HD000058.xml")
    assert em.extract_dimensions(root) is None
    # the rest of extraction for the same file must still succeed
    fields = em.extract_from_root(root, eagle, "edh")
    assert fields["text_type_native"] == "unbestimmt"


# ---------------------------------------------------------------------------
# edh+edr merge preference (EDH wins on a tie; both licences kept)
# ---------------------------------------------------------------------------

def test_edh_edr_merge_prefers_edh_field_falls_back_to_edr():
    primary = {"museum": "EDH museum", "translation": None, "images": ["a.jpg"]}
    secondary = {"museum": None, "translation": "EDR translation", "images": ["b.jpg"]}
    merged = em.merge_prefer(primary, secondary)
    assert merged["museum"] == "EDH museum"       # primary wins when present
    assert merged["translation"] == "EDR translation"  # falls back when primary is None
    assert merged["images"] == ["a.jpg", "b.jpg"]  # images are unioned, not overwritten


def test_edh_edr_credit_carries_both_sources():
    edh_fields = {"licence_name": "CC BY-SA 4.0", "licence_url": "http://x/edh",
                  "source_uri": "http://edh-www/old", "principal_edition": "CIL VI 1"}
    edr_fields = {"licence_name": "CC BY 4.0", "licence_url": "http://x/edr",
                  "source_uri": "http://www.edr-edr.it/edr_programmi/res_complex_comune.php?id_nr=EDR000006",
                  "principal_edition": "AE 1999, 1"}
    rec = {"edh_id": "HD000001", "edr_id": "EDR000006", "tm_id": 251193}
    credit = em.build_credit("edh+edr", rec, edh_fields, edr_fields, None, None)
    assert credit["source_name"] == "Epigraphic Database Heidelberg"
    assert credit["source_url"] == "https://edh.ub.uni-heidelberg.de/edh/inschrift/HD000001"
    assert credit["source_name_secondary"] == "Epigraphic Database Roma"
    assert credit["source_url_secondary"] == edr_fields["source_uri"]
    assert credit["principal_edition"] == "CIL VI 1"  # EDH's, preferred
