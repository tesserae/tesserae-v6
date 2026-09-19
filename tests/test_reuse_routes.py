"""GET /reuse/line and GET /reuse/marks: the corpus-wide verbatim reuse table
(backend/reuse_table.py, cache/reuse_pairs/<lang>.db) that backs the Reader's
"quoted in N works" marker and Reuse tab.

Builds a small fixture SQLite db (the same three-table shape
scripts/reuse/build_reuse_table.py writes) plus tiny lemma-cache JSON files,
so this runs in CI with no real reuse table or corpus present -- the pattern
tests/test_passages_works_route.py uses for the passage index.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import reuse_table  # noqa: E402
from backend.lemma_cache import get_cache_path  # noqa: E402


def _route(suffix):
    return next(str(r) for r in app.url_map.iter_rules() if str(r).endswith(suffix))


def _get(client, route, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items() if v not in (None, ''))
    return client.get(f'{route}?{qs}')


def _write_lemma_cache(lemmas_dir, language, work, refs_and_texts):
    lang_dir = os.path.join(lemmas_dir, language)
    os.makedirs(lang_dir, exist_ok=True)
    units = [{'ref': ref, 'text': text, 'tokens': text.lower().split()}
              for ref, text in refs_and_texts]
    data = {'text_id': work, 'language': language, 'units_line': units}
    with open(os.path.join(lang_dir, work + '.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _write_lemma_cache_with_tokens(lemmas_dir, language, work, entries):
    """Like _write_lemma_cache, but for tests of bold_spans (backend/
    reuse_table.py's _shared_word_mask/_bold_spans), which need precise
    control over `tokens` (normalized: lowercase, punctuation stripped,
    v->u/j->i) versus `original_tokens` (case-preserved, punctuation
    stripped) -- _write_lemma_cache's text.lower().split() gives neither
    (it keeps punctuation attached and has no original_tokens at all), so
    the two never come apart the way real cache files do.
    entries: [(ref, text, tokens, original_tokens), ...]."""
    lang_dir = os.path.join(lemmas_dir, language)
    os.makedirs(lang_dir, exist_ok=True)
    units = [{'ref': ref, 'text': text, 'tokens': tokens, 'original_tokens': original_tokens}
             for ref, text, tokens, original_tokens in entries]
    data = {'text_id': work, 'language': language, 'units_line': units}
    with open(os.path.join(lang_dir, work + '.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _write_hashed_lemma_cache(lemmas_dir, language, work, refs_and_texts):
    """Like _write_lemma_cache, but under the CURRENT production naming --
    <ascii_hint>-<md5(text_id)>.json, computed with the same
    backend.lemma_cache.get_cache_path production's cache builder uses --
    instead of the legacy plain <work>.json name. Some works ship with only
    this name and no legacy copy (Geoffrey of Vinsauf's Documentum is the
    real one that surfaced the bug: its Reuse tab entries carried a ref but
    no line text, because _load_work_lines only ever tried the plain name)."""
    lang_dir = os.path.join(lemmas_dir, language)
    os.makedirs(lang_dir, exist_ok=True)
    units = [{'ref': ref, 'text': text, 'tokens': text.lower().split()}
              for ref, text in refs_and_texts]
    data = {'text_id': work + '.tess', 'language': language, 'units_line': units}
    path = get_cache_path(work + '.tess', language, cache_dir=lemmas_dir)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _write_reuse_db(reuse_dir, language, pairs_rows, line_counts_rows, meta_rows):
    os.makedirs(reuse_dir, exist_ok=True)
    db_path = os.path.join(reuse_dir, f'{language}.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE pairs (
        work_a TEXT, line_a_ref TEXT, work_b TEXT, line_b_ref TEXT,
        shared INTEGER, jaccard REAL, span_len INTEGER
    )""")
    conn.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?,?)", pairs_rows)
    conn.execute("CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)")
    conn.executemany("INSERT INTO line_counts VALUES (?,?,?)", line_counts_rows)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO meta VALUES (?,?)", meta_rows)
    conn.commit()
    conn.close()


def _reset_reuse_table_state(monkeypatch, tmp_path):
    """Point reuse_table at a fixture directory and clear its cached state
    (open connections, the per-work lemma-cache memo) so tests don't bleed
    into each other or into a real cache/reuse_pairs directory."""
    monkeypatch.setattr(reuse_table, 'DB_DIR', str(tmp_path / 'reuse_pairs'))
    monkeypatch.setattr(reuse_table, 'CACHE_LEMMAS_DIR', str(tmp_path / 'lemmas'))
    monkeypatch.setattr(reuse_table, '_connections', {})
    reuse_table._load_work_lines.cache_clear()


def _build_fixture(tmp_path, language='la'):
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris'),
        ('verg. aen. 1.2', 'Italiam fato profugus'),
        ('verg. aen. 1.3', 'Lavinaque venit litora'),
    ])
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'macrobius.saturnalia', [
        ('macro. sat. 5.2.8', 'Troiae qui primus ab oris, quoted at length'),
    ])
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'servius.commentary', [
        ('serv. 1.1', 'a note on arma virumque'),
    ])
    # A line quoted only in the loose, single-rare-shared-word sense (tier
    # "possible" -- see reuse_table.line/marks): shared=1, the shape the
    # rare-single-ngram rule alone can produce (scripts/reuse/
    # build_reuse_table.py's find_pairs).
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'seneca.epistulae', [
        ('sen. ep. 1.1', 'arma uirumque cano, buried in an unrelated sentence'),
    ])
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'ovid.tristia', [
        ('ov. tr. 1.1', 'a line that reuses verg. aen. 1.3 strictly'),
    ])
    # A work that ships as parts only, with no base/whole-text file --
    # discover_corpus() in build_reuse_table.py never collapses these, so
    # the table keys them on their own full part id (e.g.
    # paschasius_radbertus.epitaphium_arsenii.part.2 in production).
    # _resolve_work must NOT strip .part.N off an id like this one, since
    # stripping it would look up a base id the table never had.
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'partonly.work.part.2', [
        ('partonly. work. 2.1', 'a line that only exists as a part file'),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), language,
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 'macrobius.saturnalia', 'macro. sat. 5.2.8', 10, 0.2, 1),
            ('servius.commentary', 'serv. 1.1', 'vergil.aeneid', 'verg. aen. 1.1', 4, 0.15, 1),
            ('macrobius.saturnalia', 'macro. sat. 5.2.8', 'partonly.work.part.2', 'partonly. work. 2.1', 5, 0.3, 1),
            # shared=1: tier "possible", reachable only via the rare-single
            # rule -- added alongside 1.1's two strict pairs above, so
            # n_works (strict) must stay 2 while n_possible_works becomes 1.
            ('vergil.aeneid', 'verg. aen. 1.1', 'seneca.epistulae', 'sen. ep. 1.1', 1, 0.03, 1),
            # Restores 1.3's reuse count (previously a line_counts-only
            # fixture row with no backing pair) now that marks() computes
            # counts from `pairs` directly rather than the precomputed table.
            ('vergil.aeneid', 'verg. aen. 1.3', 'ovid.tristia', 'ov. tr. 1.1', 3, 0.2, 1),
        ],
        line_counts_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 3),
            ('vergil.aeneid', 'verg. aen. 1.3', 1),
            ('partonly.work.part.2', 'partonly. work. 2.1', 1),
        ],
        meta_rows=[
            ('built_at', '2026-09-19T00:00:00+00:00'),
            ('corpus_version', '2026-08-16'),
            ('language', language),
        ],
    )


def test_line_finds_text_under_a_hashed_only_cache_filename(monkeypatch, tmp_path):
    """Reproduces the bug report: Quintilian's quotation of "arma virumque
    cano" showed its line text, but Geoffrey of Vinsauf's Documentum
    (geoffrey. document. 3.10.2) showed the reference with no text.
    Geoffrey's lemma cache exists only under its hashed name, with no
    legacy plain copy -- Quintilian's happens to have both, which is why
    only Geoffrey's was ever missing text."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _write_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris'),
    ])
    _write_hashed_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'geoffrey_of_vinsauf.documentum', [
        ('geoffrey. document. 3.10.2', 'Arma virumque cano Trojae qui prinus ab oris'),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), 'la',
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 'geoffrey_of_vinsauf.documentum',
             'geoffrey. document. 3.10.2', 4, 0.2, 1),
        ],
        line_counts_rows=[('vergil.aeneid', 'verg. aen. 1.1', 1)],
        meta_rows=[('corpus_version', '2026-08-16')],
    )
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    geoffrey = next(q for q in out['quotations'] if q['work'] == 'geoffrey_of_vinsauf.documentum')
    assert geoffrey['ref'] == 'geoffrey. document. 3.10.2'
    assert geoffrey['text'] == 'Arma virumque cano Trojae qui prinus ab oris'


def test_line_prefers_the_current_hashed_cache_over_a_stale_plain_one(monkeypatch, tmp_path):
    """Reproduces the bug report: Tertullian's Ad Nationes showed the
    "Tertullian, Ad Nationes Libri Duo ... 2.17" reference with no text,
    while the Apologeticum entry beside it showed text. The real work has
    TWO cache files: a stale plain-named one left from an old CTS-URN
    tagging scheme ("tertullian.ad_nationes_libri_duo
    urn:cts:latinLit:stoa0275.stoa002.opp-lat2.2.17"), and a current
    hashed one matching the live .tess file's own tag shape
    ("tertullian.ad_nationes_libri_duo 2.17", the full work id plus
    locus -- this work has no short abbreviation at all). _work_cache_path
    used to check plain first and never got past the stale file, so a ref
    in the CURRENT tag shape -- the only shape the reuse table (built from
    the live .tess file) ever actually stores -- was never in the cache it
    read. Hashed must now win whenever both exist."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _write_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'vergil.aeneid', [
        ('verg. aen. 1.18', 'hoc regnum dea gentibus esse, si qua fata sinant'),
    ])
    # Stale: plain-named, old CTS-URN loci -- must NOT be the one read.
    _write_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'tertullian.ad_nationes_libri_duo', [
        ('tertullian.ad_nationes_libri_duo urn:cts:latinLit:stoa0275.stoa002.opp-lat2.2.17',
         'a stale line under the old tagging scheme'),
    ])
    # Current: hashed name, tag shape matching the live .tess file (the
    # full work id plus locus -- no short abbreviation for this work).
    _write_hashed_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'tertullian.ad_nationes_libri_duo', [
        ('tertullian.ad_nationes_libri_duo 2.17',
         'hoc regnum dea gentibus esse, Si qua fata sinant, iam tunc tenditque fouetque'),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), 'la',
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.18', 'tertullian.ad_nationes_libri_duo',
             'tertullian.ad_nationes_libri_duo 2.17', 9, 0.0056, 1),
        ],
        line_counts_rows=[('vergil.aeneid', 'verg. aen. 1.18', 1)],
        meta_rows=[('corpus_version', '2026-08-16')],
    )
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.18', language='la')
    out = json.loads(r.get_data())
    tert = next(q for q in out['quotations'] if q['work'] == 'tertullian.ad_nationes_libri_duo')
    assert tert['ref'] == 'tertullian.ad_nationes_libri_duo 2.17'
    assert tert['text'] == 'hoc regnum dea gentibus esse, Si qua fata sinant, iam tunc tenditque fouetque'


# --- /reuse/line -------------------------------------------------------

def test_line_combines_both_directions_ordered_by_shared(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    works = [(q['work'], q['ref']) for q in out['quotations']]
    assert ('macrobius.saturnalia', 'macro. sat. 5.2.8') in works
    assert ('servius.commentary', 'serv. 1.1') in works
    # ordered by shared descending: macrobius (10) before servius (4)
    assert out['quotations'][0]['work'] == 'macrobius.saturnalia'
    assert out['quotations'][0]['shared'] == 10


def test_line_carries_the_actual_line_text_and_what_the_reader_needs(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    macro = next(q for q in out['quotations'] if q['work'] == 'macrobius.saturnalia')
    assert macro['text'] == 'Troiae qui primus ab oris, quoted at length'
    assert macro['ref'] == 'macro. sat. 5.2.8'
    assert macro['language'] == 'la'
    assert 'jaccard' in macro and 'span_len' in macro


def test_line_carries_meta(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    assert out['meta']['corpus_version'] == '2026-08-16'


def test_line_tags_strict_and_possible_tiers(monkeypatch, tmp_path):
    """macrobius (shared=10) and servius (shared=4) are tier 'strict' --
    kept by the jaccard rule or the containment override, both of which
    require shared>=2. seneca (shared=1) is tier 'possible' -- reachable
    only through the rare-single-ngram rule, which is why shared==1 alone
    is enough to know the tier without a rebuild (see reuse_table.line)."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    tiers = {q['work']: q['tier'] for q in out['quotations']}
    assert tiers['macrobius.saturnalia'] == 'strict'
    assert tiers['servius.commentary'] == 'strict'
    assert tiers['seneca.epistulae'] == 'possible'


def test_line_bolds_the_shared_triple_in_a_strict_quotation(monkeypatch, tmp_path):
    """Quintilian-shaped: "arma virumque cano" sits inside a longer prose
    sentence quoting Aen. 1.1. bold_spans must cover exactly those three
    words in the quotation's own text (case-preserved, comma un-bolded),
    found via the SAME word-triple (contiguous, here) find_pairs matches
    on, reconstructed at read time (backend/reuse_table.py
    _shared_word_mask/_bold_spans)."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _write_lemma_cache_with_tokens(str(tmp_path / 'lemmas'), 'la', 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris',
         ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris'],
         ['Arma', 'virumque', 'cano', 'Troiae', 'qui', 'primus', 'ab', 'oris']),
    ])
    quint_text = 'Suspenditur arma virumque cano, quia illud pertinet ad rem.'
    _write_lemma_cache_with_tokens(str(tmp_path / 'lemmas'), 'la', 'quintilian.institutio_oratoria', [
        ('Quint. Inst. 11.3.36', quint_text,
         ['suspenditur', 'arma', 'uirumque', 'cano', 'quia', 'illud', 'pertinet', 'ad', 'rem'],
         ['Suspenditur', 'arma', 'virumque', 'cano', 'quia', 'illud', 'pertinet', 'ad', 'rem']),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), 'la',
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 'quintilian.institutio_oratoria',
             'Quint. Inst. 11.3.36', 8, 0.0684, 1),
        ],
        line_counts_rows=[('vergil.aeneid', 'verg. aen. 1.1', 1)],
        meta_rows=[('corpus_version', '2026-08-16')],
    )
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    quint = next(q for q in out['quotations'] if q['work'] == 'quintilian.institutio_oratoria')
    assert quint['tier'] == 'strict'
    # One span per bolded word (not merged across the spaces between them):
    # arma, virumque, cano -- and nothing else in the sentence.
    expected = []
    pos = 0
    for word in ('arma', 'virumque', 'cano'):
        start = quint_text.index(word, pos)
        end = start + len(word)
        expected.append([start, end])
        pos = end
    assert quint['bold_spans'] == expected
    bolded_text = ' '.join(quint_text[s:e] for s, e in quint['bold_spans'])
    assert bolded_text == 'arma virumque cano'
    # Not swept into any bold span: the words right before and after.
    assert not any(s <= quint_text.index('Suspenditur') < e for s, e in quint['bold_spans'])
    assert not any(s <= quint_text.index('quia') < e for s, e in quint['bold_spans'])


def test_line_falls_back_to_bolding_a_shared_token_for_a_possible_echo(monkeypatch, tmp_path):
    """A quoting line too short to form any word-triple (here, two tokens)
    can never go through the primary triple reconstruction -- bold_spans
    must fall back to the plain shared-token it was matched on instead of
    coming back empty."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _write_lemma_cache_with_tokens(str(tmp_path / 'lemmas'), 'la', 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris',
         ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris'],
         ['Arma', 'virumque', 'cano', 'Troiae', 'qui', 'primus', 'ab', 'oris']),
    ])
    fragment_text = 'Cano nihil.'
    _write_lemma_cache_with_tokens(str(tmp_path / 'lemmas'), 'la', 'anonymus.fragmenta', [
        ('anon. frag. 1', fragment_text, ['cano', 'nihil'], ['Cano', 'nihil']),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), 'la',
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 'anonymus.fragmenta', 'anon. frag. 1', 1, 0.01, 1),
        ],
        line_counts_rows=[('vergil.aeneid', 'verg. aen. 1.1', 1)],
        meta_rows=[('corpus_version', '2026-08-16')],
    )
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    frag = next(q for q in out['quotations'] if q['work'] == 'anonymus.fragmenta')
    assert frag['tier'] == 'possible'
    start = fragment_text.index('Cano')
    end = start + len('Cano')
    assert frag['bold_spans'] == [[start, end]]
    assert 'nihil' not in fragment_text[start:end]


def test_line_does_not_bold_a_shared_token_inside_an_unshared_longer_word(monkeypatch, tmp_path):
    """A shared token found with plain substring search can land inside an
    unrelated word that merely contains its letters -- "arma" is a
    substring of "armatum" the same way "cano" is a substring of
    "canorum". The quoting line's own text puts an unshared "armatum"
    right before the real, standalone "arma virumque cano" it actually
    shares with the selected line; bold_spans must skip the embedded
    match and bold only the real word, found by scanning
    backend/reuse_table.py's _bold_spans with word boundaries."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _write_lemma_cache_with_tokens(str(tmp_path / 'lemmas'), 'la', 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris',
         ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris'],
         ['Arma', 'virumque', 'cano', 'Troiae', 'qui', 'primus', 'ab', 'oris']),
    ])
    quote_text = 'armatum tenens ait, arma virumque cano tandem.'
    _write_lemma_cache_with_tokens(str(tmp_path / 'lemmas'), 'la', 'anonymus.imitator', [
        ('anon. imit. 1', quote_text,
         ['arma', 'uirumque', 'cano', 'tandem'],
         ['arma', 'virumque', 'cano', 'tandem']),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), 'la',
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 'anonymus.imitator', 'anon. imit. 1', 9, 0.15, 1),
        ],
        line_counts_rows=[('vergil.aeneid', 'verg. aen. 1.1', 1)],
        meta_rows=[('corpus_version', '2026-08-16')],
    )
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    quote = next(q for q in out['quotations'] if q['work'] == 'anonymus.imitator')
    # The real, standalone "arma" (not the one embedded in "armatum").
    real_start = quote_text.index('arma', quote_text.index('armatum') + 1)
    real_end = real_start + len('arma')
    starts = [s for s, e in quote['bold_spans']]
    assert real_start in starts
    # Nothing bolded inside "armatum" itself.
    armatum_start = quote_text.index('armatum')
    armatum_end = armatum_start + len('armatum')
    assert not any(armatum_start <= s < armatum_end for s, e in quote['bold_spans'])


def test_line_no_matches_is_a_normal_empty_result_not_an_error(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.2', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    assert out['quotations'] == []


def test_line_missing_params_is_400(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', language='la')
    assert r.status_code == 400


def test_line_missing_language_table_is_404_plain_message(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='grc')
    assert r.status_code == 404
    out = json.loads(r.get_data())
    assert 'error' in out and isinstance(out['error'], str) and out['error']


def test_line_corrupt_database_file_is_404_not_200_or_500(monkeypatch, tmp_path):
    """A reuse table file that exists but is not a valid SQLite database
    (a garbage/truncated file, however that happened) must answer the same
    plain 404 as a language with no table at all -- not a 200 with
    available:false (sqlite3.connect() succeeds on a garbage file; the
    format error only surfaces on the first real read, so is_available()
    must actually try a read, not just check the file exists -- see
    backend/reuse_table.py's _get_connection) and not an unhandled 500."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    reuse_dir = tmp_path / 'reuse_pairs'
    reuse_dir.mkdir(parents=True, exist_ok=True)
    (reuse_dir / 'la.db').write_bytes(b'not a sqlite database, just garbage bytes')
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    assert r.status_code == 404
    out = json.loads(r.get_data())
    assert 'error' in out and isinstance(out['error'], str) and out['error']


def test_marks_corrupt_database_file_is_404_not_200_or_500(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    reuse_dir = tmp_path / 'reuse_pairs'
    reuse_dir.mkdir(parents=True, exist_ok=True)
    (reuse_dir / 'la.db').write_bytes(b'not a sqlite database, just garbage bytes')
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid', language='la')
    assert r.status_code == 404
    out = json.loads(r.get_data())
    assert 'error' in out and isinstance(out['error'], str) and out['error']


def test_corrupt_database_connection_is_never_cached(monkeypatch, tmp_path):
    """The failure must not stick around as a cached connection: once the
    garbage file is replaced with a real, valid database, the VERY NEXT
    call must succeed -- proving _get_connection did not cache (and keep
    reusing) a broken connection from the first, failed attempt."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    reuse_dir = tmp_path / 'reuse_pairs'
    reuse_dir.mkdir(parents=True, exist_ok=True)
    (reuse_dir / 'la.db').write_bytes(b'garbage')
    assert reuse_table.is_available('la') is False
    assert 'la' not in reuse_table._connections

    _build_fixture(tmp_path)  # overwrites la.db with a real, valid database
    assert reuse_table.is_available('la') is True
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True


def test_line_resolves_a_part_file_work_id_to_the_base_id(monkeypatch, tmp_path):
    """The Reader sends the part file it has open (e.g.
    vergil.aeneid.part.7.tess), but the table is keyed on the collapsed
    base id -- a part-file work id must find the same quotations as the
    base id."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    base = _get(client, _route('/reuse/line'), work='vergil.aeneid',
                ref='verg. aen. 1.1', language='la')
    part = _get(client, _route('/reuse/line'), work='vergil.aeneid.part.1.tess',
                ref='verg. aen. 1.1', language='la')
    assert part.status_code == 200
    assert json.loads(part.get_data())['quotations'] == json.loads(base.get_data())['quotations']


def test_line_keeps_a_part_only_works_own_part_id(monkeypatch, tmp_path):
    """A work with no base/whole-text file at all is keyed on its own full
    part id in the table -- _resolve_work must not strip that .part.N off,
    or a legitimate part-only work id would find nothing. `partonly.work`
    is a stand-in for the real corpus shape this covers: paschasius_
    radbertus.epitaphium_arsenii ships only as
    paschasius_radbertus.epitaphium_arsenii.part.2.tess, with no base
    epitaphium_arsenii.tess at all (see
    test_line_resolves_the_real_paschasius_radbertus_part_only_work below
    for that exact work id)."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='partonly.work.part.2.tess',
              ref='partonly. work. 2.1', language='la')
    out = json.loads(r.get_data())
    assert out['available'] is True
    assert [(q['work'], q['ref']) for q in out['quotations']] == [
        ('macrobius.saturnalia', 'macro. sat. 5.2.8'),
    ]


def test_line_resolves_the_real_paschasius_radbertus_part_only_work(monkeypatch, tmp_path):
    """The same fallback as test_line_keeps_a_part_only_works_own_part_id
    above, but with the actual real-corpus work id rather than a stand-in:
    paschasius_radbertus.epitaphium_arsenii ships as
    texts/la/paschasius_radbertus.epitaphium_arsenii.part.2.tess with no
    base (whole-text) file, so the table keys it on that full part id, and
    _norm_work's usual "collapse .part.N to the base id" must not apply
    here -- there is no base id to collapse to."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _write_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris'),
    ])
    _write_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'paschasius_radbertus.epitaphium_arsenii.part.2', [
        ('paschasius_radbertus. epitaphium_arsenii. 2.1', 'a line from the real part-only work'),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), 'la',
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 'paschasius_radbertus.epitaphium_arsenii.part.2',
             'paschasius_radbertus. epitaphium_arsenii. 2.1', 4, 0.2, 1),
        ],
        line_counts_rows=[
            ('paschasius_radbertus.epitaphium_arsenii.part.2',
             'paschasius_radbertus. epitaphium_arsenii. 2.1', 1),
        ],
        meta_rows=[('corpus_version', '2026-08-16')],
    )
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='paschasius_radbertus.epitaphium_arsenii.part.2.tess',
              ref='paschasius_radbertus. epitaphium_arsenii. 2.1', language='la')
    out = json.loads(r.get_data())
    assert out['available'] is True
    assert [(q['work'], q['ref']) for q in out['quotations']] == [
        ('vergil.aeneid', 'verg. aen. 1.1'),
    ]

    r_marks = _get(client, _route('/reuse/marks'),
                    work='paschasius_radbertus.epitaphium_arsenii.part.2.tess', language='la')
    out_marks = json.loads(r_marks.get_data())
    assert out_marks['available'] is True
    assert [row['ref'] for row in out_marks['lines']] == ['paschasius_radbertus. epitaphium_arsenii. 2.1']


# --- /reuse/marks --------------------------------------------------------

def test_marks_returns_all_reused_lines_when_no_range_given(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    refs = {row['ref']: row['n_works'] for row in out['lines']}
    assert refs == {'verg. aen. 1.1': 2, 'verg. aen. 1.3': 1}


def test_marks_reports_strict_and_possible_counts_separately(monkeypatch, tmp_path):
    """1.1 has two strict pairs (macrobius, servius) and one possible pair
    (seneca, shared=1): n_works must stay 2 (strict only), and the
    possible pair must show up as n_possible_works=1, not inflate n_works
    to 3. 1.3 has one strict pair and no possible one, so n_possible_works
    there is 0."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid', language='la')
    out = json.loads(r.get_data())
    by_ref = {row['ref']: row for row in out['lines']}
    assert by_ref['verg. aen. 1.1']['n_works'] == 2
    assert by_ref['verg. aen. 1.1']['n_possible_works'] == 1
    assert by_ref['verg. aen. 1.3']['n_works'] == 1
    assert by_ref['verg. aen. 1.3']['n_possible_works'] == 0


def test_marks_a_line_with_only_a_possible_pair_has_zero_strict(monkeypatch, tmp_path):
    """A line reused only in the loose, single-rare-shared-word sense (no
    strict pair at all) must report n_works=0 -- the Reader shows the
    lighter outline mark only in exactly this case (n_works==0 and
    n_possible_works>0)."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _write_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'lucan.bellum_civile', [
        ('luc. 1.1', 'a line quoted nowhere strictly'),
    ])
    _write_lemma_cache(str(tmp_path / 'lemmas'), 'la', 'pliny.naturalis_historia', [
        ('plin. nat. 1.1', 'a line sharing one rare phrase with lucan'),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), 'la',
        pairs_rows=[
            ('lucan.bellum_civile', 'luc. 1.1', 'pliny.naturalis_historia', 'plin. nat. 1.1', 1, 0.02, 1),
        ],
        line_counts_rows=[('lucan.bellum_civile', 'luc. 1.1', 1)],
        meta_rows=[('corpus_version', '2026-08-16')],
    )
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='lucan.bellum_civile', language='la')
    out = json.loads(r.get_data())
    row = next(row for row in out['lines'] if row['ref'] == 'luc. 1.1')
    assert row['n_works'] == 0
    assert row['n_possible_works'] == 1


def test_marks_range_uses_line_order_not_string_order(monkeypatch, tmp_path):
    """verg. aen. 1.3 is line-order after 1.1 but before nothing else here --
    a range of just line 1 must exclude it even though ref strings could
    mislead a naive comparison on a work with double-digit line numbers."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid',
              ref_start='verg. aen. 1.1', ref_end='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    assert [row['ref'] for row in out['lines']] == ['verg. aen. 1.1']


def test_marks_missing_work_is_400(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), language='la')
    assert r.status_code == 400


def test_marks_missing_language_table_is_404_plain_message(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid', language='grc')
    assert r.status_code == 404
    out = json.loads(r.get_data())
    assert 'error' in out


def test_marks_resolves_a_part_file_work_id_to_the_base_id(monkeypatch, tmp_path):
    """Reproduces the bug report: GET /api/reuse/marks?work=vergil.aeneid.part.7
    (a part file, the Reader's normal navigation unit) must answer the same
    marks as work=vergil.aeneid, not an empty list."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid.part.7.tess', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    refs = {row['ref']: row['n_works'] for row in out['lines']}
    assert refs == {'verg. aen. 1.1': 2, 'verg. aen. 1.3': 1}


def test_marks_range_still_works_with_a_part_file_work_id(monkeypatch, tmp_path):
    """The ref_start/ref_end range logic loads the work's own line order
    from its lemma cache (_load_work_lines) -- that must also use the
    resolved base id, not the raw part-file id, or the range filter would
    silently find no ref_to_seq entries and drop every row."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid.part.1.tess',
              ref_start='verg. aen. 1.1', ref_end='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    assert [row['ref'] for row in out['lines']] == ['verg. aen. 1.1']


def test_marks_keeps_a_part_only_works_own_part_id(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='partonly.work.part.2.tess', language='la')
    out = json.loads(r.get_data())
    assert out['available'] is True
    assert [row['ref'] for row in out['lines']] == ['partonly. work. 2.1']
