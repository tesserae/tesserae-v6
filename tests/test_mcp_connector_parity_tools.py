"""Tests for the five connector-parity gaps closed 2026-09-10 (see PROGRESS in
the feat/connector-parity branch): get_passage's translation flag, the new
describe_text and evidence_summary tools, theme_search paging past the normal
cutoff, and fusion_search's unit-type/weights passthrough.

Same style as test_mcp_http.py: no network, tool bodies exercised directly
with backend.blueprints.mcp_http._get/_post monkeypatched.
"""
import backend.blueprints.mcp_http as M


# --------------------------------------------------------------------------
# 1. get_passage(translation=true)
# --------------------------------------------------------------------------
def _lines_response():
    return {'work': 'vergil.aeneid.part.6', 'author': 'Vergil', 'title': 'Aeneid, Book 6',
            'display_name': 'Vergil, Aeneid, Book 6', 'language': 'la',
            'lines': [{'ref': 'verg. aen. 6.1', 'text': 'a'},
                      {'ref': 'verg. aen. 6.2', 'text': 'b'}],
            'returned': 2, 'total': 2, 'capped': False, 'note': None,
            'corpus_version': '2026-09-01', 'web_url': '/read?work=x'}


def test_get_passage_without_translation_flag_unchanged(monkeypatch):
    calls = []

    def fake_get(path, params=None):
        calls.append(path)
        return _lines_response()

    monkeypatch.setattr(M, '_get', fake_get)
    out = M._t_get_passage({'work': 'vergil.aeneid.part.6', 'ref_start': 'verg. aen. 6.1'})
    assert calls == ['/passages/lines']
    assert 'translation' not in out


def test_get_passage_translation_true_fetches_and_attaches(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        if path == '/passages/lines':
            return _lines_response()
        if path == '/passages/translation':
            seen['work'] = params.get('work')
            seen['refs'] = params.get('refs')
            return {'available': True, 'translator': 'Fairclough', 'text': 'Down they went...',
                    'year': 1916, 'license': 'Public domain'}
        raise AssertionError(f'unexpected path {path}')

    monkeypatch.setattr(M, '_get', fake_get)
    out = M._t_get_passage({'work': 'vergil.aeneid.part.6', 'ref_start': 'verg. aen. 6.1',
                            'translation': True})
    assert seen['work'] == 'vergil.aeneid.part.6'
    assert seen['refs'] == 'verg. aen. 6.1|verg. aen. 6.2'
    assert out['translation']['available'] is True
    assert out['translation']['translator'] == 'Fairclough'
    assert out['translation']['text'] == 'Down they went...'
    assert out['translation']['year'] == 1916


def test_get_passage_translation_absent_says_so_not_omits(monkeypatch):
    def fake_get(path, params=None):
        if path == '/passages/lines':
            return _lines_response()
        if path == '/passages/translation':
            return {'available': False, 'reason': 'No aligned public-domain translation for this work.'}
        raise AssertionError(path)

    monkeypatch.setattr(M, '_get', fake_get)
    out = M._t_get_passage({'work': 'some.obscure_work', 'translation': True})
    assert out['translation']['available'] is False
    assert 'reason' in out['translation']


def test_get_passage_error_short_circuits_before_translation(monkeypatch):
    monkeypatch.setattr(M, '_get', lambda path, params=None: {'error': 'work is required', 'lines': []})
    out = M._t_get_passage({'work': '', 'translation': True})
    assert out.get('error')
    assert 'translation' not in out


# --------------------------------------------------------------------------
# 2. describe_text
# --------------------------------------------------------------------------
def _texts_listing():
    return [{'id': 'vergil.aeneid.part.6.tess', 'author': 'Vergil', 'author_key': 'vergil',
             'work': 'Aeneid', 'title': 'Aeneid, Book 6', 'year': -19, 'era': 'Augustan'}]


def test_describe_text_joins_all_four_sources(monkeypatch):
    def fake_get(path, params=None):
        if path == '/texts':
            return _texts_listing()
        if path == '/text-descriptions':
            assert params == {'language': 'la', 'work': 'vergil.aeneid'}
            return {'description': 'The descent to the underworld.'}
        if path == '/text-credits':
            assert params['query'] == 'Vergil'
            return {'entries': [{'author': 'Vergil', 'work': 'Aeneid', 'e_source': 'Perseus',
                                 'e_source_url': 'http://perseus/aen', 'print_source': 'Loeb 1916'}],
                    'total': 1}
        if path == '/author-dates':
            return {'la': {'vergil': {'year': -19, 'era': 'Augustan', 'note': 'd. 19 BCE'}}}
        raise AssertionError(path)

    monkeypatch.setattr(M, '_get', fake_get)
    monkeypatch.setattr(M, '_text_genre_row',
                        lambda fn: {'era': 'Augustan', 'meter': 'hexameter', 'genre': 'epic',
                                    'confidence': 'human'} if fn == 'vergil.aeneid.part.6.tess' else None)
    out = M._t_describe_text({'id': 'vergil.aeneid.part.6', 'language': 'la'})
    assert out['id'] == 'vergil.aeneid.part.6.tess'
    assert out['description'] == 'The descent to the underworld.'
    assert out['source']['e_source'] == 'Perseus'
    assert out['author_dates']['note'] == 'd. 19 BCE'
    assert out['genre']['meter'] == 'hexameter'


def test_describe_text_missing_pieces_are_null_not_dropped(monkeypatch):
    def fake_get(path, params=None):
        if path == '/texts':
            return _texts_listing()
        if path == '/text-descriptions':
            return {'description': None}
        if path == '/text-credits':
            return {'entries': [], 'total': 0}
        if path == '/author-dates':
            return {'la': {}}
        raise AssertionError(path)

    monkeypatch.setattr(M, '_get', fake_get)
    monkeypatch.setattr(M, '_text_genre_row', lambda fn: None)
    out = M._t_describe_text({'id': 'vergil.aeneid.part.6', 'language': 'la'})
    assert out['description'] is None
    assert out['source'] is None
    assert out['author_dates'] is None
    assert out['genre'] is None
    # The rest of the record is still present.
    assert out['author'] == 'Vergil'


def test_describe_text_unknown_id_errors_cleanly(monkeypatch):
    monkeypatch.setattr(M, '_get', lambda path, params=None: _texts_listing())
    out = M._t_describe_text({'id': 'nobody.nothing', 'language': 'la'})
    assert 'error' in out


def test_describe_text_requires_id():
    assert 'error' in M._t_describe_text({'language': 'la'})


# --------------------------------------------------------------------------
# 3. evidence_summary (+ compare_texts 'evidence' key)
# --------------------------------------------------------------------------
def _fusion_parallel(source_ref, target_ref, channels, idf=8.0):
    return {'source': {'ref': source_ref, 'text': 'src text'},
            'target': {'ref': target_ref, 'text': 'tgt text'},
            'channels': channels,
            'matched_words': [{'lemma': 'w', 'idf_score': idf}],
            'fused_score': 5.0}


def test_evidence_summary_reduces_fusion_results(monkeypatch):
    parallels = [_fusion_parallel('verg. aen. 6.1', f'lucan. bc 1.{i}', ['quotation'])
                for i in range(3)]

    def fake_get(path, params=None):
        assert path == '/fusion-search'
        return {'status': 'complete', 'count': 3, 'showing': 3, 'offset': 0,
                'parallels': parallels}

    monkeypatch.setattr(M, '_get', fake_get)
    out = M._t_evidence_summary({'source': 'vergil.aeneid', 'target': 'lucan.bellum_civile',
                                 'language': 'la', 'limit': 25})
    assert out['n_results'] == 3
    assert out['verdict'] == 'verbatim'
    assert out['reading'] == 'verbatim reuse'
    assert out['reading_note']


def test_evidence_summary_passes_through_running_status(monkeypatch):
    # Zero the poll budget so _fusion_poll returns 'running' on its first check
    # instead of blocking through real sleep() calls for the full budget.
    monkeypatch.setattr(M, '_FUSION_MCP_BUDGET', 0)
    monkeypatch.setattr(M, '_get', lambda path, params=None: {'status': 'running'})
    out = M._t_evidence_summary({'source': 'a', 'target': 'b', 'language': 'la'})
    assert out['status'] == 'running'


def test_compare_texts_carries_evidence_key(monkeypatch):
    parallels = [_fusion_parallel('verg. aen. 6.1', 'lucan. bc 1.1', ['lemma', 'sound'])]

    def fake_get(path, params=None):
        assert path == '/fusion-search'
        return {'status': 'complete', 'count': 1, 'showing': 1, 'offset': 0, 'parallels': parallels}

    def fake_post(path, body, timeout=None):
        return {'shared_rare_count': 0, 'results': []}

    monkeypatch.setattr(M, '_get', fake_get)
    monkeypatch.setattr(M, '_post', fake_post)
    out = M._t_compare_texts({'source': 'vergil.aeneid', 'target': 'lucan.bellum_civile',
                              'language': 'la'})
    assert out['evidence'] is not None
    assert out['evidence']['n_results'] == 1
    assert 'reading' in out['evidence']


# --------------------------------------------------------------------------
# 4. theme_search offset
# --------------------------------------------------------------------------
def test_theme_search_forwards_offset(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        seen.update(params or {})
        return {'query': 'q', 'confidence': {'level': 'low'}, 'results': []}

    monkeypatch.setattr(M, '_get', fake_get)
    M._t_theme_search({'query': 'a shaded grove', 'offset': 300, 'limit': 25})
    assert seen.get('offset') == 300


def test_theme_search_omits_offset_when_zero_or_absent(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        seen.update(params or {})
        return {'query': 'q', 'confidence': {'level': 'low'}, 'results': []}

    monkeypatch.setattr(M, '_get', fake_get)
    M._t_theme_search({'query': 'a shaded grove'})
    assert 'offset' not in seen


# --------------------------------------------------------------------------
# 5. fusion_search settings passthrough (source_unit_type/target_unit_type/weights)
# --------------------------------------------------------------------------
def test_fusion_params_default_omits_settings():
    p = M._fusion_params({'source': 'a', 'target': 'b', 'language': 'la'})
    assert 'source_unit_type' not in p
    assert 'target_unit_type' not in p
    assert 'weights' not in p


def test_fusion_params_passes_unit_types_and_weights():
    p = M._fusion_params({'source': 'a', 'target': 'b', 'language': 'la',
                          'source_unit_type': 'phrase', 'target_unit_type': 'line',
                          'weights': {'semantic': 2.0, 'sound': 0}})
    assert p['source_unit_type'] == 'phrase'
    assert p['target_unit_type'] == 'line'
    import json as _json
    assert _json.loads(p['weights']) == {'semantic': 2.0, 'sound': 0}


def test_fusion_params_rejects_invalid_unit_type():
    p = M._fusion_params({'source': 'a', 'target': 'b', 'language': 'la',
                          'source_unit_type': 'paragraph'})
    assert 'source_unit_type' not in p


def test_fusion_search_forwards_settings_to_get(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        seen.update(params or {})
        return {'status': 'complete', 'count': 0, 'showing': 0, 'offset': 0, 'parallels': []}

    monkeypatch.setattr(M, '_get', fake_get)
    M._t_fusion_search({'source': 'a', 'target': 'b', 'language': 'la',
                        'source_unit_type': 'phrase', 'weights': {'rare_word': 9.0}})
    assert seen.get('source_unit_type') == 'phrase'
    assert 'weights' in seen
