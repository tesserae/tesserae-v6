"""Passage lookup by CTS URN: the parser, the table lookup, the route, the connector
argument, and the fill and check commands of scripts/corpus/cts_urns.py.

Nothing here reads the real table, the texts folder or the passage index: each test
builds its own in tmp_path and stubs the line store.
"""
import importlib.util
import json
import os

import pytest

from backend import cts_urns
from backend.cts_urns import UrnMalformed, UrnNotFound, lookup, parse_urn, work_key

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    'cts_urns_script', os.path.join(ROOT, 'scripts', 'corpus', 'cts_urns.py'))
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

AENEID = 'urn:cts:latinLit:phi0690.phi003'
ILIAD = 'urn:cts:greekLit:tlg0012.tlg001'
TABLE = {
    '_description': 'x',
    'la': {
        'vergil.aeneid.tess': {'urn': AENEID, 'source': 'catalog'},
        'vergil.eclogues.tess': {'urn': 'urn:cts:latinLit:phi0690.phi001', 'source': 'catalog'},
        'cicero.in_catilinam.tess': {'urn': 'urn:cts:latinLit:phi0474.phi013', 'source': 'catalog'},
        'alcuin.carmina.tess': {'urn': None, 'source': 'none'},
    },
    'grc': {'homer.iliad.tess': {'urn': ILIAD, 'source': 'catalog'}},
}


def make_texts(root, files):
    for lang, names in files.items():
        (root / lang).mkdir(parents=True, exist_ok=True)
        for n in names:
            (root / lang / n).write_text('<x. 1.1>\tword\n', encoding='utf-8')
    return root


@pytest.fixture
def env(tmp_path):
    texts = make_texts(tmp_path / 'texts', {
        'la': ['vergil.aeneid.tess', 'vergil.aeneid.part.1.tess', 'vergil.aeneid.part.2.tess',
               'vergil.eclogues.part.1.tess', 'vergil.eclogues.part.2.tess', 'vergil.eclogues.part.10.tess',
               'cicero.in_catilinam.tess', 'alcuin.carmina.part.10.tess'],
        'grc': ['homer.iliad.tess', 'homer.iliad.part.1.tess'],
    })
    return str(texts), TABLE


# ---- the parser: ten URNs --------------------------------------------------

@pytest.mark.parametrize('urn, expected', [
    ('urn:cts:latinLit:phi0690.phi003:1.1-1.7', ('la', 'phi0690.phi003', '1.1', '1.7')),
    ('urn:cts:latinLit:phi0690.phi003:6.851', ('la', 'phi0690.phi003', '6.851', '6.851')),
    ('urn:cts:greekLit:tlg0012.tlg001:1.1-1.7', ('grc', 'tlg0012.tlg001', '1.1', '1.7')),
    ('urn:cts:greekLit:tlg0012.tlg001.perseus-grc2:1.1-1.7', ('grc', 'tlg0012.tlg001', '1.1', '1.7')),
    ('urn:cts:latinLit:phi0474.phi013.perseus-lat2:1.1.1-1.2.3', ('la', 'phi0474.phi013', '1.1.1', '1.2.3')),
    ('urn:cts:latinLit:phi0474.phi013:2', ('la', 'phi0474.phi013', '2', '2')),
    ('urn:cts:greekLit:tlg0059.tlg030:327a-328b', ('grc', 'tlg0059.tlg030', '327a', '328b')),
    ('urn:cts:greekLit:tlg0012.tlg001:1.1-7', ('grc', 'tlg0012.tlg001', '1.1', '1.7')),
    ('urn:cts:latinLit:stoa0040.stoa021:3.4.5@sed[1]', ('la', 'stoa0040.stoa021', '3.4.5', '3.4.5')),
    ('  urn:cts:latinLit:phi1017.phi002:1-5  ', ('la', 'phi1017.phi002', '1', '5')),
])
def test_parse_accepts_poetry_prose_ranges_and_versions(urn, expected):
    p = parse_urn(urn)
    language, work, start, end = expected
    assert (p['language'], p['work_urn'].split(':', 3)[3], p['start'], p['end']) == (language, work, start, end)


@pytest.mark.parametrize('bad', [
    '', 'phi0690.phi003:1.1', 'urn:cts:latinLit', 'urn:cts:latinLit:phi0690', 'urn:cts:latinLit:phi0690.phi003:',
    'urn:cts:latinLit:phi0690.phi003:1.1-', 'urn:cts:latinLit:phi0690.phi003:..1', 'urn:isbn:latinLit:a.b:1',
    'urn:cts:latinLit:phi0690.phi003:1.1 1.2', 'http://scaife.perseus.org/urn:cts:latinLit:phi0690.phi003:1.1',
])
def test_parse_rejects_malformed(bad):
    with pytest.raises(UrnMalformed):
        parse_urn(bad)


def test_work_key_folds_parts_into_their_work():
    assert work_key('vergil.aeneid.part.6.tess') == 'vergil.aeneid.tess'
    assert work_key('vergil.aeneid.tess') == 'vergil.aeneid.tess'
    assert work_key('paulinus.carmina.part.2a.tess') == 'paulinus.carmina.tess'
    assert work_key('jerome.vulgate.part.21a.old_latin_psalms.tess') == 'jerome.vulgate.tess'
    assert work_key('gellius.attic_nights.part.pr.tess') == 'gellius.attic_nights.tess'
    assert work_key('vergil.aeneid') == 'vergil.aeneid.tess'


# ---- the lookup ------------------------------------------------------------

def test_lookup_whole_file_wins_over_its_parts(env):
    texts, table = env
    assert lookup(AENEID + ':1.1-1.7', texts, table) == ('la', 'vergil.aeneid.tess', '1.1', '1.7')
    assert lookup(AENEID + '.perseus-lat2:6.851', texts, table)[1:] == ('vergil.aeneid.tess', '6.851', '6.851')
    assert lookup(ILIAD + ':1.1-1.7', texts, table)[:2] == ('grc', 'homer.iliad.tess')


def test_lookup_part_only_work_resolves_by_first_citation_number(env):
    texts, table = env
    eclogues = 'urn:cts:latinLit:phi0690.phi001'
    assert lookup(eclogues + ':2.3-2.9', texts, table)[1] == 'vergil.eclogues.part.2.tess'
    assert lookup(eclogues + ':10.1', texts, table)[1] == 'vergil.eclogues.part.10.tess'
    with pytest.raises(UrnNotFound, match='has none for 7.1'):
        lookup(eclogues + ':7.1', texts, table)
    with pytest.raises(UrnNotFound, match='crosses'):
        lookup(eclogues + ':1.1-2.3', texts, table)


def test_lookup_unknown_work_namespace_and_work_without_passage(env):
    texts, table = env
    with pytest.raises(UrnNotFound, match='no text in Tesserae'):
        lookup('urn:cts:latinLit:phi9999.phi001:1.1', texts, table)
    with pytest.raises(UrnNotFound, match='namespace'):
        lookup('urn:cts:farsiLit:abc.def:1.1', texts, table)
    with pytest.raises(UrnMalformed, match='names a work'):
        lookup(AENEID, texts, table)
    # a "none" entry has no URN to resolve
    with pytest.raises(UrnNotFound):
        lookup('urn:cts:latinLit:stoa0023.stoa001:1', texts, table)


def test_lookup_table_entry_whose_file_is_not_on_the_server(tmp_path):
    texts = make_texts(tmp_path / 'texts', {'la': ['cicero.in_catilinam.tess']})
    with pytest.raises(UrnNotFound, match='not on this server'):
        lookup(AENEID + ':1.1', str(texts), TABLE)


def test_urn_for_resolves_parts_and_ignores_none_entries():
    assert cts_urns.urn_for('la', 'vergil.aeneid.part.6.tess', TABLE) == AENEID
    assert cts_urns.urn_for('la', 'vergil.aeneid', TABLE) == AENEID
    assert cts_urns.urn_for('la', 'alcuin.carmina.part.10.tess', TABLE) is None
    assert cts_urns.urn_for('la', 'unknown.tess', TABLE) is None


# ---- the route -------------------------------------------------------------

@pytest.fixture
def client(env, tmp_path, monkeypatch):
    from backend import passage_index, window_texts
    from backend.app import app
    from backend.blueprints import passages
    texts, table = env
    table_path = tmp_path / 'cts_urns.json'
    table_path.write_text(json.dumps(table), encoding='utf-8')
    monkeypatch.setattr(cts_urns, 'TABLE_PATH', str(table_path))
    monkeypatch.setattr(cts_urns, 'TEXTS_DIR', texts)

    aeneid = [(f'verg. aen. 1.{i}', f'line {i}') for i in range(1, 12)]

    def ref_for_locus(work, locus, last=False):
        assert work == 'vergil.aeneid'
        for ref, _ in aeneid:
            if ref.endswith(' ' + locus):
                return ref
        return None

    def passage_lines(work, ref_start=None, ref_end=None, context=0):
        refs = [r for r, _ in aeneid]
        i, j = refs.index(ref_start), refs.index(ref_end or ref_start)
        got = aeneid[i:j + 1]
        return {'lines': [{'ref': r, 'text': t} for r, t in got], 'capped': False,
                'total': len(got), 'returned': len(got)}

    monkeypatch.setattr(window_texts, 'ref_for_locus', ref_for_locus)
    monkeypatch.setattr(window_texts, 'passage_lines', passage_lines)
    # a whole-work file has no window rows, so language_of finds nothing; the URN knows the language
    monkeypatch.setattr(window_texts, 'language_of', lambda w: None)
    monkeypatch.setattr(passage_index, '_naming', lambda w: {'author': 'Vergil', 'title': 'Aeneid',
                                                              'display_name': 'Vergil, Aeneid'})
    monkeypatch.setattr(passages, 'get_corpus_version', lambda lang: '2026-11-08')
    return app.test_client()


def by_urn(client, urn):
    route = next(str(r) for r in client.application.url_map.iter_rules()
                 if str(r).endswith('/passages/by-urn'))
    return client.get(route, query_string={'urn': urn})


def test_route_known_urn_returns_the_lines_with_urn_and_resolved(client):
    r = by_urn(client, AENEID + ':1.1-1.7')
    assert r.status_code == 200
    d = r.get_json()
    assert [ln['ref'] for ln in d['lines']] == [f'verg. aen. 1.{i}' for i in range(1, 8)]
    assert d['urn'] == AENEID + ':1.1-1.7'
    assert d['resolved'] == {'language': 'la', 'text': 'vergil.aeneid.tess', 'locus': '1.1-1.7'}
    assert d['author'] == 'Vergil' and d['language'] == 'la' and d['web_url'].startswith('/read?work=')


def test_route_single_locus(client):
    d = by_urn(client, AENEID + ':1.3').get_json()
    assert [ln['ref'] for ln in d['lines']] == ['verg. aen. 1.3']
    assert d['resolved']['locus'] == '1.3'


def test_route_unknown_work_is_404_with_a_message(client):
    r = by_urn(client, 'urn:cts:latinLit:phi9999.phi001:1.1')
    assert r.status_code == 404
    assert 'no text in Tesserae' in r.get_json()['error']


def test_route_locus_outside_the_file_is_404(client):
    r = by_urn(client, AENEID + ':99.1-99.7')
    assert r.status_code == 404
    assert 'not in vergil.aeneid.tess' in r.get_json()['error']


@pytest.mark.parametrize('bad', ['', 'nonsense', 'urn:cts:latinLit:phi0690.phi003'])
def test_route_malformed_urn_is_400(client, bad):
    r = by_urn(client, bad)
    assert r.status_code == 400
    assert r.get_json()['error']


# ---- the connector ---------------------------------------------------------

def test_connector_get_passage_takes_a_urn_in_place_of_work_and_locus(monkeypatch):
    import backend.blueprints.mcp_http as M
    seen = {}

    def fake_by_urn(urn, context=None):
        seen['urn'] = urn
        return {'work': 'vergil.aeneid', 'author': 'Vergil', 'title': 'Aeneid', 'display_name': 'Vergil, Aeneid',
                'language': 'la', 'lines': [{'ref': 'verg. aen. 1.1', 'text': 'a'}, {'ref': 'verg. aen. 1.2', 'text': 'b'}],
                'returned': 2, 'total': 2, 'capped': False, 'urn': urn,
                'resolved': {'language': 'la', 'text': 'vergil.aeneid.tess', 'locus': '1.1-1.2'}}

    monkeypatch.setattr(M, '_get_by_urn', fake_by_urn)
    monkeypatch.setattr(M, '_get', lambda *a, **k: pytest.fail('the work route must not be called'))
    out = M._t_get_passage({'urn': AENEID + ':1.1-1.2'})
    assert seen['urn'] == AENEID + ':1.1-1.2'
    assert out['urn'] == AENEID + ':1.1-1.2'
    assert out['resolved']['text'] == 'vergil.aeneid.tess'
    assert [ln['ref'] for ln in out['lines']] == ['verg. aen. 1.1', 'verg. aen. 1.2']
    assert any(t['name'] == 'get_passage' and 'urn' in t['inputSchema']['properties']
               and t['inputSchema']['required'] == [] for t in M.TOOLS)


def test_connector_urn_error_comes_back_as_the_routes_message(monkeypatch):
    import backend.blueprints.mcp_http as M

    class R:
        status_code = 404

        def json(self):
            return {'error': 'no text in Tesserae for x'}

    monkeypatch.setattr(M.requests, 'get', lambda *a, **k: R())
    out = M._t_get_passage({'urn': 'urn:cts:latinLit:phi9999.phi001:1.1'})
    assert out['error'] == 'no text in Tesserae for x' and out['lines'] == []


def test_connector_get_passage_needs_work_or_urn():
    import backend.blueprints.mcp_http as M
    assert 'urn' in M._t_get_passage({})['error']


def test_connector_passage_and_listing_entries_carry_the_urn_when_the_table_has_one(monkeypatch, tmp_path):
    import backend.blueprints.mcp_http as M
    path = tmp_path / 'cts_urns.json'
    path.write_text(json.dumps(TABLE), encoding='utf-8')
    monkeypatch.setattr(cts_urns, 'TABLE_PATH', str(path))

    def fake_get(p, params=None):
        if p == '/passages/lines':
            return {'work': 'vergil.aeneid.part.1', 'language': 'la', 'returned': 2, 'total': 2,
                    'lines': [{'ref': 'verg. aen. 1.5', 'text': 'a'}, {'ref': 'verg. aen. 1.9', 'text': 'b'}]}
        if p == '/texts':
            return [{'id': 'vergil.aeneid.tess', 'author': 'Vergil', 'work': 'Aeneid'},
                    {'id': 'vergil.copa.tess', 'author': 'Vergil', 'work': 'Copa'}]
        if p == '/passages/theme-search':
            return {'results': [{'work': 'vergil.aeneid', 'language': 'la', 'ref_start': 'verg. aen. 6.1',
                                 'ref_end': 'verg. aen. 6.3'},
                                {'work': 'no.table.entry', 'language': 'la', 'ref_start': 'x. 1.1'}]}
        raise AssertionError(p)

    monkeypatch.setattr(M, '_get', fake_get)
    assert M._t_get_passage({'work': 'vergil.aeneid.part.1'})['urn'] == AENEID + ':1.5-1.9'
    texts = M._t_list_texts({'language': 'la'})
    assert texts[0]['urn'] == AENEID and 'urn' not in texts[1]
    results = M._t_theme_search({'query': 'q'})['results']
    assert results[0]['urn'] == AENEID + ':6.1-6.3' and 'urn' not in results[1]


# ---- fill and check --------------------------------------------------------

CTS_GROUP = ('<ti:textgroup xmlns:ti="http://chs.harvard.edu/xmlns/cts" projid="latinLit:phi0690" '
             'urn="urn:cts:latinLit:phi0690"><ti:groupname xml:lang="lat">Vergil</ti:groupname></ti:textgroup>')
CTS_WORK = ('<ti:work xmlns:ti="http://chs.harvard.edu/xmlns/cts" groupUrn="urn:cts:latinLit:phi0690" '
            'urn="urn:cts:latinLit:phi0690.phi003" xml:lang="lat"><ti:title xml:lang="eng">Aeneid</ti:title>'
            '<ti:edition urn="urn:cts:latinLit:phi0690.phi003.perseus-lat2"><ti:label xml:lang="eng">Aeneid</ti:label>'
            '</ti:edition></ti:work>')
CTS_WORK_2 = CTS_WORK.replace('phi003', 'phi002').replace('Aeneid', 'Georgics')


@pytest.fixture
def fill_env(tmp_path, monkeypatch):
    inv = tmp_path / 'inventory' / 'latin' / 'data' / 'phi0690'
    (inv / 'phi003').mkdir(parents=True)
    (inv / 'phi002').mkdir(parents=True)
    (inv / '__cts__.xml').write_text(CTS_GROUP, encoding='utf-8')
    (inv / 'phi003' / '__cts__.xml').write_text(CTS_WORK, encoding='utf-8')
    (inv / 'phi002' / '__cts__.xml').write_text(CTS_WORK_2, encoding='utf-8')
    texts = make_texts(tmp_path / 'texts', {
        'la': ['vergil.aeneid.part.1.tess', 'vergil.aeneid.part.2.tess', 'vergil.georgics.tess',
               'nobody.unlisted_poem.tess'],
        'grc': []})
    sources = tmp_path / 'text_sources.json'
    sources.write_text('[]', encoding='utf-8')
    monkeypatch.setattr(script, 'SOURCES', str(sources))
    return tmp_path, str(texts), str(tmp_path / 'inventory')


def run(*argv):
    return script.main(list(argv))


def test_fill_adds_missing_entries_only_and_check_passes(fill_env, capsys):
    tmp, texts, inv = fill_env
    table = tmp / 'cts_urns.json'
    table.write_text(json.dumps({'la': {'vergil.georgics.tess': {'urn': 'urn:cts:latinLit:phi0690.phi002',
                                                                  'source': 'manual', 'note': 'kept'}},
                                 'grc': {}}), encoding='utf-8')
    assert run('--table', str(table), '--texts', texts, 'fill', '--inventory', inv) == 0
    data = json.loads(table.read_text(encoding='utf-8'))
    # the two Aeneid parts fold into one work entry, found by author and title
    assert data['la']['vergil.aeneid.tess'] == {'urn': AENEID, 'source': 'catalog'}
    assert data['la']['vergil.georgics.tess']['note'] == 'kept'          # existing entry untouched
    assert 'nobody.unlisted_poem.tess' not in data['la']                 # no match: left out, not guessed
    assert data['_last_updated'] and 'CTS URN' in data['_description']
    out = capsys.readouterr().out
    assert 'la: 2 of 3 works have a URN' in out and 'nobody.unlisted_poem.tess' in out
    assert run('--table', str(table), '--texts', texts, 'check') == 0


def test_fill_twice_changes_nothing(fill_env):
    tmp, texts, inv = fill_env
    table = tmp / 'cts_urns.json'
    run('--table', str(table), '--texts', texts, 'fill', '--inventory', inv)
    first = table.read_text(encoding='utf-8')
    run('--table', str(table), '--texts', texts, 'fill', '--inventory', inv)
    assert json.loads(table.read_text(encoding='utf-8'))['la'] == json.loads(first)['la']


def test_fill_accept_writes_only_reviewed_entries_with_a_work_urn(fill_env):
    tmp, texts, inv = fill_env
    table = tmp / 'cts_urns.json'
    accept = tmp / 'accept.json'
    accept.write_text(json.dumps({
        'la:nobody.unlisted_poem.tess': {'urn': 'urn:cts:latinLit:phi0690.phi003', 'source': 'manual', 'note': 'read'},
        'la:vergil.georgics.tess': {'urn': 'not a urn', 'source': 'manual'}}), encoding='utf-8')
    run('--table', str(table), '--texts', texts, 'fill', '--inventory', inv, '--accept', str(accept))
    la = json.loads(table.read_text(encoding='utf-8'))['la']
    assert la['nobody.unlisted_poem.tess']['source'] == 'manual'
    assert la['vergil.georgics.tess']['source'] == 'catalog'            # the bad accept entry was ignored


def test_check_fails_on_an_entry_with_no_text_file_or_a_bad_urn(fill_env, capsys):
    tmp, texts, _inv = fill_env
    table = tmp / 'cts_urns.json'
    table.write_text(json.dumps({'la': {
        'vergil.georgics.tess': {'urn': 'urn:cts:latinLit:phi0690.phi002', 'source': 'catalog'},
        'gone.work.tess': {'urn': 'urn:cts:latinLit:phi0001.phi001', 'source': 'catalog'},
        'vergil.aeneid.tess': {'urn': 'urn:cts:greekLit:tlg0012.tlg001', 'source': 'catalog'}}, 'grc': {}}),
        encoding='utf-8')
    assert run('--table', str(table), '--texts', texts, 'check') == 1
    out = capsys.readouterr().out
    assert 'gone.work.tess: no text file' in out and 'vergil.aeneid.tess: not a work URN for this language' in out


def test_none_records_a_reviewed_absence_that_check_accepts(fill_env):
    tmp, texts, inv = fill_env
    table = tmp / 'cts_urns.json'
    run('--table', str(table), '--texts', texts, 'fill', '--inventory', inv)
    assert run('--table', str(table), '--texts', texts, 'none', '--language', 'la',
               '--note', 'medieval, in no inventory', 'nobody.unlisted_poem.tess') == 0
    la = json.loads(table.read_text(encoding='utf-8'))['la']
    assert la['nobody.unlisted_poem.tess'] == {'urn': None, 'source': 'none', 'note': 'medieval, in no inventory'}
    assert run('--table', str(table), '--texts', texts, 'check') == 0
