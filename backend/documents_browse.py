"""Documents collection browse facets (Browse Corpus > Documents).

Builds a normalized, in-memory facet index over metadata.db's `documents`
table -- kind (inscriptions / papyri), region (province or Augustan region
for inscriptions; nome or findspot for papyri), and century (from
date_not_before/date_not_after) -- plus the flat filters (text type,
material, object type, language), so GET /api/documents/browse can answer
fast without a fresh full-table scan on every request. Behind
TESSERAE_DOCUMENTS=1 like the rest of this feature (see backend/documents.py
for the switch and the metadata.db connection pattern this module reuses);
nothing here is imported, let alone run, with the switch off.

Region and century are computed here in Python rather than in SQL because
the source data (EDH, EDR, I.Sicily, HGV via papyri.info) label the same
place or an uncertain date in several different ways -- a plain SQL
GROUP BY would just multiply the facet list by every spelling variant. See
normalize_inscription_region / normalize_papyri_region / century_bucket for
exactly what gets merged and why; OPEN_LABELS below lists the handful this
pass could not merge cleanly.

Papyri get a SECOND region level, findspot under nome (2026-10-09): HGV
records a document's Egyptian nome as its own structured field
(<placeName type="ancient" subtype="nome">) separate from the town/village
findspot, but `extract_findspot` (scripts/documents/epidoc_convert.py) never
read it, so metadata.db's one `ancient_place` column holds only a free-text
mix -- "Karanis (Arsinoites)" for a document naming both, or just
"Oxyrhynchos" / just "Oxyrhynchites" for one naming only the town or only
the nome. Treating that column as a single flat region, as before, put the
same nome's town and the nome itself in separate top-level buckets (e.g.
Oxyrhynchus, 4,171 documents, beside Oxyrhynchites, 791). PAPYRI_NOME_MAP
(data/documents/papyri_nome_map.json, loaded by _papyri_nome_map below) is
the fix at the data layer: every (town, nome) pair HGV's own structured
field recorded anywhere in the raw papyri.info EpiDoc corpus
(scripts/documents/extract_metadata.py's source), by majority vote where a
town's nome varies across its documents (573 towns, checked 2026-10-09
against the full 68,022-file HGV_meta_EpiDoc set). normalize_papyri_region
now returns (nome, findspot) -- the nome from the document's own
parenthetical when it carries one, else looked up for the town it names via
this map, else UNKNOWN_NOME when neither resolves. See
research/threads/2026-10-09_papyri_nome_grouping.md for the full before/
after count of the top 20 groups (not checked into the public repo; the
same numbers are in this PR's description and CHANGELOG.md).

The facet cache (a plain Python list of lightweight per-document records,
one normalization pass over the `documents` table) is built once per
process and rebuilt only when metadata.db's mtime changes (the same check
backend.documents.get_corpus_version uses for its own index files), so a
request after the first on a given build pays no normalization cost -- see
_FacetCache and get_cache().
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Optional

import backend.documents as docs
from backend.logging_config import get_logger

logger = get_logger('documents_browse')


# ---------------------------------------------------------------------------
# Kind
# ---------------------------------------------------------------------------

KIND_LABELS = {
    'inscriptions': 'Inscriptions (Latin, Greek)',
    'papyri': 'Papyri and ostraca',
}
KIND_ORDER = ('inscriptions', 'papyri')

_INSCRIPTION_SOURCES = {'edh', 'edr', 'edh+edr', 'isicily'}


def _kind_for_source(source):
    source = (source or '').strip().lower()
    if source == 'papyri':
        return 'papyri'
    if source in _INSCRIPTION_SOURCES:
        return 'inscriptions'
    return None  # an unrecognized source never enters the browse tree


# ---------------------------------------------------------------------------
# Region: inscriptions (province / Italy's Augustan regions, EDH + EDR)
# ---------------------------------------------------------------------------

UNKNOWN_REGION = 'Unknown region'
UNKNOWN_FINDSPOT = 'Unknown findspot'

# EDH marks an uncertain region/place with a trailing "?" (e.g. "Dalmatia?").
_TRAILING_UNCERTAIN_RE = re.compile(r'\?+\s*$')
_TRAILING_UNCERTAIN_PAREN_RE = re.compile(r'\(\s*\?\s*\)\s*$')

# Spelling/naming variants for the SAME Augustan region of Italy seen across
# EDH and EDR (and EDH's own German "unknown" marker), merged to one label
# each -- checked against the full distinct `region` list for source in
# (edh, edr, edh+edr) on the production metadata.db, 2026-10-08. Matched
# case-insensitively after the trailing "?" is stripped; the ORIGINAL value
# is kept on every document record regardless (see DocRecord.region_raw).
_REGION_ALIASES = {
    'unbekannt': UNKNOWN_REGION,
    'bruttium et lucania (regio iii)': 'Bruttii et Lucania (Regio III)',
    'latium et campania cum insulis (regio i)': 'Latium et Campania (Regio I)',
    'samnium (regio iv)': 'Sabina et Samnium (Regio IV)',
    'sardinia cum insulis': 'Sardinia',
    'sicilia cum insulis': 'Sicilia',
}

# Combined/dual-province labels found in the data that are NOT a spelling
# variant of a single region -- a document genuinely spans two provinces.
# Left as their own bucket rather than folded into either side; reported
# rather than silently normalized.
UNNORMALIZED_REGION_LABELS = (
    'Tuscia et Umbria', 'Macedonia, Epirus', 'Sicilia, Melita',
)


def normalize_inscription_region(source, region):
    """(canonical label, original value) for one inscription's region."""
    original = region
    source_l = (source or '').strip().lower()
    if source_l == 'isicily':
        # I.Sicily carries no `region` column at all -- every one of its
        # inscriptions is Sicilian by construction of the source itself.
        return 'Sicilia', original
    if not region or not region.strip():
        return UNKNOWN_REGION, original
    cleaned = _TRAILING_UNCERTAIN_RE.sub('', region.strip()).strip()
    canonical = _REGION_ALIASES.get(cleaned.lower(), cleaned)
    return canonical, original


# ---------------------------------------------------------------------------
# Region: papyri (nome or findspot, HGV via papyri.info's ancient_place)
# ---------------------------------------------------------------------------

# A single trailing parenthetical: "Site (Qualifier)". HGV uses this both
# for a village's owning nome ("Karanis (Arsinoites)") and for a plain
# disambiguator ("Masada (Palästina)", "Theben (?)") -- _looks_like_nome
# below tells the two apart.
_PAREN_RE = re.compile(r'^(?P<site>.*?)\s*\((?P<paren>[^()]*)\)\s*$')
# Egyptian nomes are named with the Greek adjectival "-ites"/"-ites" suffix
# ("Arsinoites", "Oxyrhynchites", "Hermopolites", ...); the handful of
# multi-word regional names HGV also uses for findspot grouping.
_NOME_LIKE_RE = re.compile(r'ites$', re.IGNORECASE)
_NOME_WHITELIST = {'oasis magna', 'oasis parva', 'thebais'}
# A parenthetical qualifier that names a country, province, or alternate
# site rather than a nome -- grouping should fall back to the site name in
# front of it, not treat the qualifier as the nome.
_PAREN_NON_NOME = {
    'ägypten', 'palästina', 'nubien', 'kreta', 'africa proconsularis',
    'tertia palaestina salutaris', '?', 'notos', 'charax',
}

# German HGV labels (and the uninformative "unknown") anglicized to the
# spelling the English-language secondary literature uses. Covers every
# standalone place name in the 80 most frequent papyri ancient_place values
# (85.7% of all papyri rows), checked 2026-10-08.
_PLACE_ALIASES = {
    'unbekannt': UNKNOWN_FINDSPOT,
    'theben': 'Thebes',
    'oxyrhynchos': 'Oxyrhynchus',
    'ägypten': 'Egypt',
    'oberägypten': 'Upper Egypt',
    'unterägypten': 'Lower Egypt',
    'nubien': 'Nubia',
    'palästina': 'Palestine',
    'kreta': 'Crete',
}

UNKNOWN_NOME = 'Unknown nome'

_NOME_MAP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'documents', 'papyri_nome_map.json')
_nome_map_lock = threading.Lock()
_nome_map_cache = None


def _papyri_nome_map():
    """Town (as HGV spells it in a document's own record, e.g. "Karanis")
    -> its nome (e.g. "Arsinoites"), built once from every (town, nome) pair
    HGV's own <placeName subtype="nome"> structured field records anywhere
    in the raw papyri.info EpiDoc corpus -- see the module docstring. Loaded
    once per process; a missing file (a worktree with no documents data at
    all) degrades to an empty map rather than raising, matching get_cache's
    own best-effort pattern below."""
    global _nome_map_cache
    with _nome_map_lock:
        if _nome_map_cache is None:
            try:
                with open(_NOME_MAP_PATH, encoding='utf-8') as f:
                    _nome_map_cache = {k.lower(): v for k, v in json.load(f).items()}
            except (OSError, ValueError):
                _nome_map_cache = {}
        return _nome_map_cache


def _clean_place_fragment(text):
    """Strip the uncertainty/alternate-reading noise HGV's findspot field
    carries, leaving the place name(s) a nome/findspot decision can be made
    from. Order matters: the ", Ägypten" country suffix must come off
    before the trailing "?" it often precedes."""
    text = (text or '').strip()
    for sep in (' oder ', ' bzw. ', ' bzw '):
        # "X oder Y" / "X bzw. Y" ("X or Y" / "X or rather Y"): an uncertain
        # alternative findspot. The first option groups the document; the
        # ORIGINAL string (both options) is kept in the data unchanged.
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    text = _TRAILING_UNCERTAIN_PAREN_RE.sub('', text).strip()
    if text.endswith(', Ägypten'):
        text = text[:-len(', Ägypten')].strip()
    text = _TRAILING_UNCERTAIN_RE.sub('', text).strip()
    return text


def _is_nome_name(text):
    text_l = (text or '').lower()
    return bool(text_l) and (_NOME_LIKE_RE.search(text) or text_l in _NOME_WHITELIST)


def normalize_papyri_region(ancient_place):
    """(nome, findspot, original value) for one papyrus -- two levels, not
    one: the nome (Egyptian administrative district, e.g. "Arsinoites") and,
    under it, the town or village within it a document actually names (e.g.
    "Karanis"). Either half can be missing: a document naming only a nome in
    general (no specific town known) gets findspot=None; one naming only a
    town looks that town up in the nome map (_papyri_nome_map) built from
    HGV's own structured data elsewhere in the corpus. Neither resolving
    falls back to UNKNOWN_NOME/UNKNOWN_FINDSPOT, same as before this
    (nome, findspot) split (2026-10-09; see the module docstring)."""
    original = ancient_place
    if not ancient_place or not ancient_place.strip():
        return UNKNOWN_NOME, UNKNOWN_FINDSPOT, original
    cleaned = _clean_place_fragment(ancient_place)
    match = _PAREN_RE.match(cleaned)
    if match:
        site = _clean_place_fragment(match.group('site'))
        paren = _clean_place_fragment(match.group('paren'))
        paren_l = paren.lower()
        looks_like_nome = paren_l not in _PAREN_NON_NOME and _is_nome_name(paren)
        if looks_like_nome:
            nome = _PLACE_ALIASES.get(paren_l, paren)
            if not site:
                return nome, None, original
            findspot = _PLACE_ALIASES.get(site.lower(), site)
            return nome, findspot, original
        cleaned = site  # the qualifier was a country/province/disambiguator
    if not cleaned:
        return UNKNOWN_NOME, UNKNOWN_FINDSPOT, original
    if _is_nome_name(cleaned):
        # The document names only the nome itself, no specific town.
        return _PLACE_ALIASES.get(cleaned.lower(), cleaned), None, original
    findspot = _PLACE_ALIASES.get(cleaned.lower(), cleaned)
    nome = _papyri_nome_map().get(cleaned.lower())
    return (nome or UNKNOWN_NOME), findspot, original


def normalize_region(kind, source, region, ancient_place):
    """(region, findspot, raw) -- findspot is always None for inscriptions
    (one level, as before); for papyri it is the town/village under the
    nome returned as `region` (see normalize_papyri_region)."""
    if kind == 'papyri':
        return normalize_papyri_region(ancient_place)
    region_label, original = normalize_inscription_region(source, region)
    return region_label, None, original


# ---------------------------------------------------------------------------
# Century, from date_not_before / date_not_after
# ---------------------------------------------------------------------------

_ORDINAL_SUFFIX = {1: 'st', 2: 'nd', 3: 'rd'}


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = _ORDINAL_SUFFIX.get(n % 10, 'th')
    return f'{n}{suffix}'


def _century_of_year(year):
    """(century number, era, sort key) for one astronomical year. sort key
    is a single ascending timeline: earlier is always a smaller number.

    The historical calendar has no year zero, but a handful of EDH/EDR
    records give date_not_before or date_not_after as literally 0 (an
    approximate "around the turn of the era" date, not a real year) --
    treated as the first year of the first century AD, the nearer of the
    two conventional choices, rather than producing a nonsensical "0th
    century"."""
    if year >= 0:
        century = -(-max(year, 1) // 100)  # ceil(year / 100), year 0 -> 1
        return century, 'AD', (century - 1) * 100
    magnitude = -year
    century = -(-magnitude // 100)
    return century, 'BC', -(century * 100)


@dataclass(frozen=True)
class Century:
    label: str
    sort_key: int


# Checked 2026-10-09 against the live documents indexes: the century
# facet's earliest buckets (31st, 16th, 13th century BC) each turned out to
# hold one EDR epitaph (CIL 09, 03008, an ordinary 1st-century cinerary-urn
# inscription with date_not_before stuck at -3030, three thousand years
# before any Latin or Greek alphabet existed) and 7 O.Trim. ostraca (a
# published, independently-dated 3rd/4th-century-AD Amheida excavation
# series -- 1,043 of its other 1,050 entries carry sane Roman/Late Antique
# dates; these 7 alone carry a date_not_before from the Bronze Age, one
# even spanning the full 7th century BC to the 4th century AD). No item in
# this corpus is genuine from before 1000 BC: no Latin or Greek alphabetic
# inscription predates roughly 800 BC, and this corpus's papyri are Greek/
# Demotic/Coptic documentary texts, not pharaonic administrative papyri.
# Below that floor the bound is a source-data error, not an early find --
# filed as "Date uncertain" rather than a century bucket so it does not
# misrepresent a genuine early document (real 7th/8th-century-BC epigraphy,
# e.g. archaic epitaphs from Praeneste and Selinus, keeps its own century
# bucket; only this specific implausible floor is excluded).
_IMPOSSIBLE_DATE_FLOOR = -1000


def _is_impossible_date(date_not_before):
    return date_not_before is not None and date_not_before < _IMPOSSIBLE_DATE_FLOOR


def century_bucket(date_not_before, date_not_after):
    """The Century a document belongs under (its EARLIEST bound), plus a
    date_label for display that names the full span when the two bounds
    fall in different centuries -- so a browse row never implies a
    multi-century document was confined to the bucket it is filed under.

    A date_not_before earlier than _IMPOSSIBLE_DATE_FLOOR is filed under
    "Date uncertain" instead of a century (see the comment above) -- the
    date_label is still computed from the real stored values, so a
    document's own page keeps showing what the source actually recorded."""
    if date_not_before is None and date_not_after is None:
        return Century('Undated', 10 ** 9), None
    if _is_impossible_date(date_not_before):
        return Century('Date uncertain', 10 ** 9 + 1), _date_label(date_not_before, date_not_after)
    before = date_not_before if date_not_before is not None else date_not_after
    after = date_not_after if date_not_after is not None else date_not_before
    c_before, era_before, sort_before = _century_of_year(before)
    c_after, era_after, sort_after = _century_of_year(after)
    # The earliest century is whichever bound sorts first on the shared
    # ascending timeline.
    if sort_before <= sort_after:
        century, era, sort_key = c_before, era_before, sort_before
    else:
        century, era, sort_key = c_after, era_after, sort_after
    label = f'{_ordinal(century)} century {era}'
    if (c_before, era_before) != (c_after, era_after):
        later_label = f'{_ordinal(c_after)} century {era_after}' if sort_after >= sort_before \
            else f'{_ordinal(c_before)} century {era_before}'
        label = f'{label} (spans to {later_label})'
    date_label = _date_label(date_not_before, date_not_after)
    return Century(label, sort_key), date_label


def _fmt_year(year):
    return f'{-year} BC' if year < 0 else (f'{year} AD' if year > 0 else '1 AD')


def _date_label(date_not_before, date_not_after):
    if date_not_before is None and date_not_after is None:
        return None
    if date_not_before is None:
        return _fmt_year(date_not_after)
    if date_not_after is None:
        return _fmt_year(date_not_before)
    if date_not_before == date_not_after:
        return _fmt_year(date_not_before)
    return f'{_fmt_year(date_not_before)} - {_fmt_year(date_not_after)}'


# ---------------------------------------------------------------------------
# Facet cache: one normalization pass over `documents`, kept in memory
# ---------------------------------------------------------------------------

_DOC_FIELDS = (
    "id, source, text_type_label, object_type_label, material_label, "
    "date_not_before, date_not_after, ancient_place, region, languages, "
    "principal_edition"
)


@dataclass(frozen=True)
class DocRecord:
    doc_id: str
    kind: str
    region: str
    region_raw: Optional[str]
    findspot: Optional[str]  # papyri only -- the town/village under `region` (its nome); always None for inscriptions
    century_label: str
    century_sort: int
    date_label: Optional[str]
    text_type: Optional[str]
    material: Optional[str]
    object_type: Optional[str]
    language: Optional[str]
    principal_edition: Optional[str]


def _primary_language(languages_field):
    if not languages_field:
        return None
    first = languages_field.split(',')[0].strip()
    return first or None


def _build_records(conn):
    records = []
    cur = conn.execute(f"SELECT {_DOC_FIELDS} FROM documents")  # nosec B608 - fixed column list
    for row in cur:
        (doc_id, source, text_type, object_type, material,
         date_not_before, date_not_after, ancient_place, region,
         languages, principal_edition) = row
        kind = _kind_for_source(source)
        if kind is None:
            continue
        region_label, findspot, region_raw = normalize_region(kind, source, region, ancient_place)
        century, date_label = century_bucket(date_not_before, date_not_after)
        records.append(DocRecord(
            doc_id=doc_id,
            kind=kind,
            region=region_label,
            region_raw=region_raw,
            findspot=findspot,
            century_label=century.label,
            century_sort=century.sort_key,
            date_label=date_label,
            text_type=text_type or None,
            material=material or None,
            object_type=object_type or None,
            language=_primary_language(languages),
            principal_edition=principal_edition or None,
        ))
    return records


class _FacetCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.mtime = None
        self.records = None

    def get(self):
        path = docs._metadata_db_path()  # noqa: SLF001 - same accessor backend.documents itself uses
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = None
        with self.lock:
            if self.records is None or mtime != self.mtime:
                conn = docs.get_meta_connection()
                if conn is None:
                    self.records = []
                else:
                    self.records = _build_records(conn)
                self.mtime = mtime
                logger.info(f"documents browse facet cache built: {len(self.records)} documents")
            return self.records


_cache = _FacetCache()


def reset_cache():
    """Drop the cached facet records, so a changed metadata.db or env var
    takes effect without a process restart. Also used by tests."""
    global _nome_map_cache
    with _cache.lock:
        _cache.records = None
        _cache.mtime = None
    with _nome_map_lock:
        _nome_map_cache = None


def get_records():
    return _cache.get()


# ---------------------------------------------------------------------------
# Browse: facet tree + a page of documents
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _matches(record, kind=None, region=None, findspot=None, century=None, text_type=None,
             material=None, object_type=None, language=None):
    if kind and record.kind != kind:
        return False
    if region and record.region != region:
        return False
    if findspot and record.findspot != findspot:
        return False
    if century and record.century_label != century:
        return False
    if text_type and record.text_type != text_type:
        return False
    if material and record.material != material:
        return False
    if object_type and record.object_type != object_type:
        return False
    if language and record.language != language:
        return False
    return True


def _counted(values):
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return counts


def browse(kind=None, region=None, findspot=None, century=None, text_type=None, material=None,
           object_type=None, language=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    """The facet tree (with counts) and one page of matching documents.

    The tree is cumulative: kind counts are over everything; region counts
    are over documents of the selected kind (every kind's regions if none is
    selected); for papyri, `region` is the nome and `findspot_counts` is a
    second level under it (the town/village a document names within that
    nome -- see normalize_papyri_region), empty for inscriptions, which have
    no second region level. Century counts are over the selected
    kind+region+findspot. The flat filters (text type, material, object
    type, language) each count over whatever kind/region/findspot/century
    is selected, so a filter dropdown's counts reflect the rest of the
    current selection, not the whole corpus.
    """
    page = max(1, page)
    page_size = max(1, min(MAX_PAGE_SIZE, page_size))
    records = get_records()

    kind_counts = _counted(r.kind for r in records)
    by_kind = [r for r in records if not kind or r.kind == kind]

    region_counts = _counted(r.region for r in by_kind)
    by_region = [r for r in by_kind if not region or r.region == region]

    findspot_counts = _counted(r.findspot for r in by_region if r.findspot)
    by_findspot = [r for r in by_region if not findspot or r.findspot == findspot]

    century_counts_raw = {}
    for r in by_findspot:
        key = (r.century_sort, r.century_label)
        century_counts_raw[key] = century_counts_raw.get(key, 0) + 1
    century_counts = sorted(
        [{'label': label, 'count': count, '_sort': sort_key}
         for (sort_key, label), count in century_counts_raw.items()],
        key=lambda e: e['_sort'],
    )
    for e in century_counts:
        del e['_sort']

    matching = [r for r in by_findspot if not century or r.century_label == century]

    filtered = [r for r in matching if _matches(
        r, text_type=text_type, material=material, object_type=object_type, language=language)]

    def _facet_counts(attr, exclude):
        pool = [r for r in matching if _matches(
            r,
            text_type=None if exclude == 'text_type' else text_type,
            material=None if exclude == 'material' else material,
            object_type=None if exclude == 'object_type' else object_type,
            language=None if exclude == 'language' else language)]
        counts = _counted(getattr(r, attr) for r in pool if getattr(r, attr))
        return sorted(({'value': v, 'count': c} for v, c in counts.items()),
                       key=lambda e: (-e['count'], e['value']))

    total = len(filtered)
    start = (page - 1) * page_size
    page_records = filtered[start:start + page_size]

    return {
        'kind_counts': sorted(
            ({'value': k, 'label': KIND_LABELS.get(k, k), 'count': c}
             for k, c in kind_counts.items()),
            key=lambda e: KIND_ORDER.index(e['value']) if e['value'] in KIND_ORDER else 99),
        'region_counts': sorted(
            ({'value': v, 'count': c} for v, c in region_counts.items()),
            key=lambda e: (-e['count'], e['value'])),
        'findspot_counts': sorted(
            ({'value': v, 'count': c} for v, c in findspot_counts.items()),
            key=lambda e: (-e['count'], e['value'])),
        'century_counts': century_counts,
        'filters': {
            'text_types': _facet_counts('text_type', 'text_type'),
            'materials': _facet_counts('material', 'material'),
            'objects': _facet_counts('object_type', 'object_type'),
            'languages': _facet_counts('language', 'language'),
        },
        'documents': [{
            'doc_id': r.doc_id,
            'kind': r.kind,
            'region': r.region,
            'findspot': r.findspot,
            'century': r.century_label,
            'date_label': r.date_label,
            'text_type': r.text_type,
            'material': r.material,
            'object_type': r.object_type,
            'language': r.language,
            'title': r.principal_edition or r.doc_id,
        } for r in page_records],
        'total': total,
        'page': page,
        'page_size': page_size,
    }


def first_line_for(doc_id, language):
    """A short snippet of the document's first line, for the leaf list --
    best-effort: returns None rather than raising when the documents index
    is unavailable, the id isn't found, or the language guess was wrong (a
    multi-language document's primary language isn't necessarily the one
    its own index lives under)."""
    languages_to_try = [language] if language in docs.SUPPORTED_LANGUAGES else list(docs.SUPPORTED_LANGUAGES)
    for lang in languages_to_try:
        if not docs.is_index_available(lang):
            continue
        try:
            data = docs.get_document_lines(lang, doc_id)
        except Exception:                                           # noqa: BLE001
            data = None
        if data and data.get('lines'):
            text = (data['lines'][0].get('text') or '').strip()
            if text:
                return text[:160]
    return None
