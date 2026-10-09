"""Unit tests for backend/documents_browse.py (Documents section of Browse
Corpus) and its route, GET /api/documents/browse.

Covers region normalization (inscriptions: province/Augustan-region alias
merging; papyri: nome-vs-findspot extraction from HGV's German-labeled
ancient_place), century bucketing (AD/BC, spanning centuries, undated),
the facet tree + paging the route returns, and the TESSERAE_DOCUMENTS gate.
No corpus data, no network: a tiny hand-written metadata.db fixture with
exactly the columns backend.documents_browse reads.
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.documents as docs
import backend.documents_browse as browse_mod
from backend.app import app


# ---------------------------------------------------------------------------
# Region normalization
# ---------------------------------------------------------------------------

def test_inscription_region_merges_spelling_variants():
    cases = [
        ("edh", "Dalmatia?", "Dalmatia"),
        ("edr", "Bruttium et Lucania (Regio III)", "Bruttii et Lucania (Regio III)"),
        ("edr", "Latium et Campania cum insulis (Regio I)", "Latium et Campania (Regio I)"),
        ("edh", "Latium et Campania (Regio I)?", "Latium et Campania (Regio I)"),
        ("edr", "Samnium (Regio IV)", "Sabina et Samnium (Regio IV)"),
        ("edr", "Sardinia cum insulis", "Sardinia"),
        ("edr", "Sicilia cum insulis", "Sicilia"),
        ("edh", "unbekannt", browse_mod.UNKNOWN_REGION),
        ("edh", "unbekannt?", browse_mod.UNKNOWN_REGION),
    ]
    for source, raw, expected in cases:
        label, original = browse_mod.normalize_inscription_region(source, raw)
        assert label == expected, f"{source}/{raw!r} -> {label!r}, expected {expected!r}"
        assert original == raw


def test_isicily_has_no_region_column_but_gets_sicilia():
    label, original = browse_mod.normalize_inscription_region("isicily", None)
    assert label == "Sicilia"
    assert original is None


def test_inscription_region_unknown_when_blank_or_missing():
    label, _ = browse_mod.normalize_inscription_region("edh", None)
    assert label == browse_mod.UNKNOWN_REGION
    label, _ = browse_mod.normalize_inscription_region("edh", "")
    assert label == browse_mod.UNKNOWN_REGION


def test_inscription_region_dual_province_labels_pass_through_unmerged():
    # These are genuine "spans two provinces" labels, not spelling variants
    # -- they must NOT collapse into either side.
    for raw in browse_mod.UNNORMALIZED_REGION_LABELS:
        label, _ = browse_mod.normalize_inscription_region("edr", raw)
        assert label == raw


@pytest.mark.parametrize("raw,expected_nome,expected_findspot", [
    # A document naming both a town and its nome: both come back, not one
    # swallowing the other (this is the 2026-10-09 fix -- Oxyrhynchos the
    # town and Oxyrhynchites the nome no longer collide into one bucket).
    ("Karanis (Arsinoites)", "Arsinoites", "Karanis"),
    ("Tebtynis (Arsinoites)", "Arsinoites", "Tebtynis"),
    ("Hermopolis (Hermopolites, Ägypten)", "Hermopolites", "Hermopolis"),
    ("Tholthis (Oxyrhynchites)", "Oxyrhynchites", "Tholthis"),
    ("Trimithis (Oasis Magna)", "Oasis Magna", "Trimithis"),
    ("Oxyrhynchos (Oxyrhynchites, Ägypten)", "Oxyrhynchites", "Oxyrhynchus"),
    ("Ta Memnoneia (Theben) oder Hermonthis", "Hermonthites", "Ta Memnoneia"),
    # A document naming only the nome: no town, findspot is None rather
    # than a copy of the nome.
    ("Arsinoites", "Arsinoites", None),
    ("Arsinoites (?)", "Arsinoites", None),
    ("Arsinoites, Ägypten", "Arsinoites", None),
    ("Arsinoites ?, Ägypten", "Arsinoites", None),
    # A document naming only a town: findspot is that town, and the nome
    # comes from PAPYRI_NOME_MAP (built from every document anywhere in the
    # corpus that DID record both -- see the module docstring), not from
    # this one document's own text.
    ("Theben", "Peri Thebas", "Thebes"),
    ("Theben (Ägypten)", "Peri Thebas", "Thebes"),
    ("Theben (?)", "Peri Thebas", "Thebes"),
    ("Theben (Ägypten) (?)", "Peri Thebas", "Thebes"),
    ("Oxyrhynchos", "Oxyrhynchites", "Oxyrhynchus"),
    ("Elephantine oder Syene", "Katarraktes Mikros", "Elephantine"),
    # A town the map has no nome for (it is outside the nome system
    # entirely, or no document in the corpus ever recorded its nome):
    # findspot still resolves, nome is "Unknown nome" -- not a lost
    # findspot, just no nome to attach it to.
    ("Masada (Palästina)", browse_mod.UNKNOWN_NOME, "Masada"),
    ("Chersonesos (Kreta)", browse_mod.UNKNOWN_NOME, "Chersonesos"),
    ("Golas (Africa proconsularis)", browse_mod.UNKNOWN_NOME, "Golas"),
    # Nothing recorded at all.
    ("unbekannt", browse_mod.UNKNOWN_NOME, browse_mod.UNKNOWN_FINDSPOT),
    (None, browse_mod.UNKNOWN_NOME, browse_mod.UNKNOWN_FINDSPOT),
])
def test_papyri_region_nome_and_findspot(raw, expected_nome, expected_findspot):
    nome, findspot, original = browse_mod.normalize_papyri_region(raw)
    assert nome == expected_nome, f"{raw!r} -> nome {nome!r}, expected {expected_nome!r}"
    assert findspot == expected_findspot, f"{raw!r} -> findspot {findspot!r}, expected {expected_findspot!r}"
    assert original == raw


def test_papyri_nome_map_resolves_site_without_its_own_parenthetical(monkeypatch):
    # Isolated from the real data file: a town the CURRENT document's text
    # does not itself pair with a nome still resolves, via the map, exactly
    # as it would if every one of that town's documents happened to carry
    # the parenthetical.
    monkeypatch.setattr(browse_mod, "_nome_map_cache", {"testopolis": "Testites"})
    nome, findspot, _ = browse_mod.normalize_papyri_region("Testopolis")
    assert nome == "Testites"
    assert findspot == "Testopolis"


def test_papyri_nome_map_missing_file_degrades_to_unknown_nome(monkeypatch, tmp_path):
    monkeypatch.setattr(browse_mod, "_nome_map_cache", None)
    monkeypatch.setattr(browse_mod, "_NOME_MAP_PATH", str(tmp_path / "does-not-exist.json"))
    nome, findspot, _ = browse_mod.normalize_papyri_region("Somewhereopolis")
    assert nome == browse_mod.UNKNOWN_NOME
    assert findspot == "Somewhereopolis"


# ---------------------------------------------------------------------------
# Century bucketing
# ---------------------------------------------------------------------------

def test_century_single_ad():
    century, date_label = browse_mod.century_bucket(101, 150)
    assert century.label == "2nd century AD"
    assert date_label == "101 AD - 150 AD"


def test_century_single_bc():
    century, date_label = browse_mod.century_bucket(-150, -101)
    assert century.label == "2nd century BC"
    assert date_label == "150 BC - 101 BC"


def test_century_boundary_year_100_is_first_century():
    century, _ = browse_mod.century_bucket(100, 100)
    assert century.label == "1st century AD"
    century, _ = browse_mod.century_bucket(-100, -100)
    assert century.label == "1st century BC"


def test_century_spanning_centuries_filed_under_earliest_and_label_says_so():
    century, date_label = browse_mod.century_bucket(-50, 60)
    assert century.label == "1st century BC (spans to 1st century AD)"
    assert date_label == "50 BC - 60 AD"


def test_century_undated_is_separate():
    century, date_label = browse_mod.century_bucket(None, None)
    assert century.label == "Undated"
    assert date_label is None


def test_century_one_bound_missing_uses_the_other():
    century, date_label = browse_mod.century_bucket(None, 250)
    assert century.label == "3rd century AD"
    assert date_label == "250 AD"


def test_century_ordinal_suffixes():
    century, _ = browse_mod.century_bucket(1101, 1101)
    assert century.label == "12th century AD"
    century, _ = browse_mod.century_bucket(2201, 2201)
    assert century.label == "23rd century AD"


# A source-data date_not_before this early is a data error, not a genuine
# find, for every collection this corpus holds -- see the long comment
# above _IMPOSSIBLE_DATE_FLOOR (checked 2026-10-09: an EDR epitaph stuck at
# -3030 and 7 O.Trim. ostraca stuck in the Bronze Age, both one-off
# mis-dates within collections whose other thousands of entries date
# correctly). century_bucket files these under "Date uncertain" instead of
# a century bucket, but keeps the real stored years in date_label.
def test_century_impossible_date_is_uncertain_not_a_century():
    century, date_label = browse_mod.century_bucket(-3030, 50)
    assert century.label == "Date uncertain"
    assert date_label == "3030 BC - 50 AD"


def test_century_impossible_date_floor_is_the_boundary():
    # Right at the floor: still a real (if early) century, not uncertain.
    century, _ = browse_mod.century_bucket(-1000, -1000)
    assert century.label == "10th century BC"
    # One year earlier: uncertain.
    century, _ = browse_mod.century_bucket(-1001, -1001)
    assert century.label == "Date uncertain"


def test_century_impossible_date_sorts_after_undated():
    uncertain, _ = browse_mod.century_bucket(-1539, -1077)
    undated, _ = browse_mod.century_bucket(None, None)
    assert uncertain.sort_key > undated.sort_key


# ---------------------------------------------------------------------------
# Facet cache / browse() / route, against a tiny fixture metadata.db
# ---------------------------------------------------------------------------

_DOC_COLUMNS = (
    "id", "source", "text_type_label", "object_type_label", "material_label",
    "date_not_before", "date_not_after", "ancient_place", "region",
    "languages", "principal_edition",
)


def _make_metadata_db(path, rows):
    conn = sqlite3.connect(path)
    cols_sql = ", ".join(f"{c} TEXT" if c not in
                          ("date_not_before", "date_not_after") else f"{c} INTEGER"
                          for c in _DOC_COLUMNS)
    conn.execute(f"CREATE TABLE documents ({cols_sql})")  # nosec B608
    conn.execute("CREATE TABLE display (id TEXT, field TEXT, value TEXT)")
    for row in rows:
        full = {c: row.get(c) for c in _DOC_COLUMNS}
        cols = ", ".join(full.keys())
        placeholders = ", ".join("?" for _ in full)
        conn.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})",  # nosec B608
                     list(full.values()))
    conn.commit()
    conn.close()


_FIXTURE_ROWS = [
    {"id": "edh:A1", "source": "edh", "text_type_label": "epitaph",
     "object_type_label": "stele", "material_label": "marble",
     "date_not_before": 101, "date_not_after": 150, "ancient_place": None,
     "region": "Dalmatia", "languages": "la",
     "principal_edition": "CIL III 0001"},
    {"id": "edh:A2", "source": "edh", "text_type_label": "epitaph",
     "object_type_label": "altar", "material_label": "limestone",
     "date_not_before": None, "date_not_after": None, "ancient_place": None,
     "region": "Dalmatia?", "languages": "la",
     "principal_edition": "CIL III 0002"},
    {"id": "edr:A3", "source": "edr", "text_type_label": "dedication",
     "object_type_label": "stele", "material_label": "marble",
     "date_not_before": -50, "date_not_after": 10, "ancient_place": None,
     "region": "Latium et Campania cum insulis (Regio I)", "languages": "la",
     "principal_edition": "EDR000003"},
    {"id": "isicily:A4", "source": "isicily", "text_type_label": "honorific",
     "object_type_label": "base", "material_label": "marble",
     "date_not_before": 201, "date_not_after": 250, "ancient_place": None,
     "region": None, "languages": "grc",
     "principal_edition": "ISic000004"},
    {"id": "papyri:P1", "source": "papyri", "text_type_label": "letter",
     "object_type_label": "papyrus sheet", "material_label": "papyrus",
     "date_not_before": 201, "date_not_after": 201,
     "ancient_place": "Karanis (Arsinoites)", "region": None,
     "languages": "grc", "principal_edition": "P.Mich. 1"},
    {"id": "papyri:P2", "source": "papyri", "text_type_label": "contract",
     "object_type_label": "papyrus sheet", "material_label": "papyrus",
     "date_not_before": 101, "date_not_after": 101,
     "ancient_place": "Tebtynis (Arsinoites)", "region": None,
     "languages": "grc", "principal_edition": "P.Tebt. 2"},
    {"id": "edh:A6", "source": "edh", "text_type_label": "epitaph",
     "object_type_label": "cinerary urn", "material_label": "stone",
     "date_not_before": -3030, "date_not_after": 50, "ancient_place": None,
     "region": "Samnium (Regio IV)", "languages": "la",
     "principal_edition": "CIL 09, 03008 (fixture)"},
    {"id": "other:X1", "source": "unknown-source", "text_type_label": "x",
     "object_type_label": "x", "material_label": "x",
     "date_not_before": 1, "date_not_after": 1, "ancient_place": None,
     "region": None, "languages": "la", "principal_edition": "excluded"},
]


@pytest.fixture
def fixture_env(tmp_path, monkeypatch):
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, _FIXTURE_ROWS)
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", metadata_db)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", str(tmp_path / "no_index_here"))
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", str(tmp_path / "restored"))
    docs.reset_caches()
    browse_mod.reset_cache()
    yield metadata_db
    docs.reset_caches()
    browse_mod.reset_cache()


def test_unrecognized_source_excluded_from_cache(fixture_env):
    records = browse_mod.get_records()
    ids = {r.doc_id for r in records}
    assert "other:X1" not in ids
    assert len(records) == len(_FIXTURE_ROWS) - 1


def test_browse_kind_counts(fixture_env):
    result = browse_mod.browse()
    kinds = {e['value']: e['count'] for e in result['kind_counts']}
    assert kinds == {'inscriptions': 5, 'papyri': 2}


def test_browse_region_counts_merge_variants_within_kind(fixture_env):
    result = browse_mod.browse(kind='inscriptions')
    regions = {e['value']: e['count'] for e in result['region_counts']}
    # Dalmatia and Dalmatia? merge to one bucket of 2.
    assert regions['Dalmatia'] == 2
    assert regions['Latium et Campania (Regio I)'] == 1
    assert regions['Sicilia'] == 1  # isicily's implicit region


def test_browse_papyri_region_counts_use_nome(fixture_env):
    result = browse_mod.browse(kind='papyri')
    regions = {e['value']: e['count'] for e in result['region_counts']}
    assert regions == {'Arsinoites': 2}


def test_browse_papyri_findspot_counts_nest_under_nome(fixture_env):
    result = browse_mod.browse(kind='papyri', region='Arsinoites')
    findspots = {e['value']: e['count'] for e in result['findspot_counts']}
    assert findspots == {'Karanis': 1, 'Tebtynis': 1}
    narrowed = browse_mod.browse(kind='papyri', region='Arsinoites', findspot='Karanis')
    assert narrowed['total'] == 1
    assert narrowed['documents'][0]['doc_id'] == 'papyri:P1'


def test_browse_inscriptions_have_no_findspot_level(fixture_env):
    result = browse_mod.browse(kind='inscriptions')
    assert result['findspot_counts'] == []
    assert all(d.get('findspot') is None for d in result['documents'])


def test_browse_century_counts_include_date_uncertain(fixture_env):
    result = browse_mod.browse(kind='inscriptions', region='Sabina et Samnium (Regio IV)')
    centuries = {e['label']: e['count'] for e in result['century_counts']}
    assert centuries == {'Date uncertain': 1}
    assert result['documents'][0]['doc_id'] == 'edh:A6'


def test_browse_century_counts_undated_separate(fixture_env):
    result = browse_mod.browse(kind='inscriptions', region='Dalmatia')
    centuries = {e['label']: e['count'] for e in result['century_counts']}
    assert centuries == {'2nd century AD': 1, 'Undated': 1}


def test_browse_filters_count_within_selection(fixture_env):
    result = browse_mod.browse(kind='inscriptions')
    materials = {e['value']: e['count'] for e in result['filters']['materials']}
    assert materials['marble'] == 3  # edh:A1, edr:A3, isicily:A4
    assert materials['limestone'] == 1


def test_browse_documents_page_and_total(fixture_env):
    result = browse_mod.browse(kind='papyri', page=1, page_size=1)
    assert result['total'] == 2
    assert len(result['documents']) == 1
    assert result['page'] == 1
    page2 = browse_mod.browse(kind='papyri', page=2, page_size=1)
    assert len(page2['documents']) == 1
    assert page2['documents'][0]['doc_id'] != result['documents'][0]['doc_id']


def test_browse_region_filter_narrows_documents(fixture_env):
    result = browse_mod.browse(kind='inscriptions', region='Dalmatia')
    ids = {d['doc_id'] for d in result['documents']}
    assert ids == {'edh:A1', 'edh:A2'}


def test_cache_rebuilds_when_metadata_db_changes(fixture_env, tmp_path):
    first = browse_mod.get_records()
    assert len(first) == len(_FIXTURE_ROWS) - 1
    metadata_db = os.environ["TESSERAE_DOCUMENTS_META"]
    # Rewrite with one extra row and a bumped mtime.
    rows = _FIXTURE_ROWS + [{
        "id": "edh:A5", "source": "edh", "text_type_label": "epitaph",
        "object_type_label": "stele", "material_label": "marble",
        "date_not_before": 300, "date_not_after": 300, "ancient_place": None,
        "region": "Dalmatia", "languages": "la", "principal_edition": "CIL III 0005",
    }]
    os.remove(metadata_db)
    _make_metadata_db(metadata_db, rows)
    os.utime(metadata_db, None)
    docs.reset_caches()  # metadata.py's own connection cache, keyed on "checked"
    second = browse_mod.get_records()
    assert len(second) == len(first) + 1


# ---------------------------------------------------------------------------
# Route: GET /api/documents/browse
# ---------------------------------------------------------------------------

def test_route_404_when_switch_off(monkeypatch):
    monkeypatch.delenv("TESSERAE_DOCUMENTS", raising=False)
    client = app.test_client()
    r = client.get('/api/documents/browse')
    assert r.status_code == 404


def test_route_returns_facet_tree_and_documents(fixture_env):
    client = app.test_client()
    r = client.get('/api/documents/browse?kind=inscriptions')
    assert r.status_code == 200
    data = r.get_json()
    assert 'kind_counts' in data
    assert 'region_counts' in data
    assert 'century_counts' in data
    assert 'filters' in data
    assert 'documents' in data
    assert data['total'] == 5


def test_route_paging_params(fixture_env):
    client = app.test_client()
    r = client.get('/api/documents/browse?kind=papyri&page=1&page_size=1')
    data = r.get_json()
    assert len(data['documents']) == 1
    assert data['page'] == 1
    assert data['page_size'] == 1


def test_route_first_line_best_effort_none_without_index(fixture_env):
    client = app.test_client()
    r = client.get('/api/documents/browse?kind=papyri')
    data = r.get_json()
    for doc in data['documents']:
        assert doc['first_line'] is None
