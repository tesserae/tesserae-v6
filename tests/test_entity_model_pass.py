"""The entity model pass (stage 1d): the gateway client against a fake gateway, the answer
parsers, the lemma decisions and the window answers applied to a hand-made matcher. No live
gateway and no live index is read."""
import collections
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import entity_gateway as gw  # noqa: E402
from backend import entity_index as ei  # noqa: E402
from backend import entity_lemma as el  # noqa: E402
from backend import entity_model_pass as mp  # noqa: E402


class _Fake(BaseHTTPRequestHandler):
    replies = []
    seen = []

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n))
        type(self).seen.append((self.headers.get('Authorization'), body))
        code, text = type(self).replies.pop(0) if type(self).replies else (200, 'yes')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'choices': [{'message': {'content': text}}]}).encode())

    def log_message(self, *a):
        pass


def _serve():
    srv = HTTPServer(('127.0.0.1', 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, 'http://127.0.0.1:%d' % srv.server_address[1]


def test_gateway_sends_the_key_asks_for_temperature_zero_and_retries_a_429():
    srv, url = _serve()
    try:
        _Fake.replies = [(429, ''), (200, 'Demonym.')]
        _Fake.seen = []
        sleeps = []
        g = gw.Gateway(url, 'k-secret', sleep_fn=sleeps.append)
        assert g.ask('sys', 'user') == 'Demonym.'
        assert len(_Fake.seen) == 2
        auth, body = _Fake.seen[0]
        assert auth == 'Bearer k-secret'
        assert body['temperature'] == 0 and body['chat_template_kwargs'] == {'enable_thinking': False}
        assert g.stats['http_429'] == 1 and g.stats['answered'] == 1 and g.stats['failed'] == 0
        assert sleeps and 'k-secret' not in json.dumps(g.stats)
    finally:
        srv.shutdown()


def test_gateway_gives_up_after_the_retries_and_counts_the_failure():
    srv, url = _serve()
    try:
        _Fake.replies = [(500, '')] * 10
        g = gw.Gateway(url, 'k', retries=2, sleep_fn=lambda s: None)
        assert g.ask('s', 'u') is None
        assert g.stats['failed'] == 1 and g.stats['errors'] == {'http_500': 3}
    finally:
        srv.shutdown()


def test_run_jobs_keeps_the_order():
    out, _secs = gw.run_jobs(list(range(20)), lambda x: x * 2, 4)
    assert out == [x * 2 for x in range(20)]


def test_pass_one_and_two_parsers():
    assert mp.parse_pass1('Yes') == 'yes'
    assert mp.parse_pass1(' demonym.\n') == 'demonym'
    assert mp.parse_pass1('Other (a different Atreus)') == 'other'
    assert mp.parse_pass1('maybe') is None and mp.parse_pass1('') is None and mp.parse_pass1(None) is None
    assert mp.parse_pass2('2', 3) == 2
    assert mp.parse_pass2('0', 3) == 0
    assert mp.parse_pass2('The answer is 3.', 3) == 3
    assert mp.parse_pass2('7', 3) is None and mp.parse_pass2('none', 3) is None


def test_clip_words_keeps_the_token_in_view():
    text = ' '.join(f'w{i}' for i in range(1000)) + ' Alexandri ' + ' '.join(f'v{i}' for i in range(1000))
    clipped = mp.clip_words(text, 'Alexandri', limit=400)
    assert 'Alexandri' in clipped and len(clipped.split()) == 400
    assert mp.clip_words('short text', 'text') == 'short text'


# --- the decisions and answers applied to a hand-made matcher

def _world():
    keys = [
        {'id': 'E1', 'greek': '', 'latin': ['Alexander'], 'english': 'Alexander the Great', 'type': 'person', 'pleiades': []},
        {'id': 'E2', 'greek': '', 'latin': ['Alexander'], 'english': 'Alexander of Pherae', 'type': 'person', 'pleiades': []},
        {'id': 'E3', 'greek': '', 'latin': ['Roma'], 'english': 'Rome', 'type': 'place', 'pleiades': ['1']},
        {'id': 'E4', 'greek': '', 'latin': ['Argos'], 'english': 'Argos', 'type': 'place', 'pleiades': ['2']},
    ]
    entities, _ = ei.merge_list_entities(keys)
    types = {l: {} for l in ei.LANGS}
    for tok, lem in [('alexander', 'alexander'), ('romanus', 'romanus'), ('roma', 'roma'), ('argo', 'argo'),
                     ('argos', 'argos')]:
        types['la'][tok] = [10, 10, 10, 10, tok]
    prep = {'type_lemma': {'la': {t: t for t in types['la']}, 'grc': {}, 'en': {}},
            'stats': {l: {} for l in ei.LANGS}, 'form_source': {},
            'form_lemma': [('la', 0, 'alexander', 'alexander'), ('la', 1, 'alexander', 'alexander'),
                           ('la', 2, 'roma', 'roma'), ('la', 2, 'romanus', 'romanus'),
                           ('la', 3, 'argos', 'argos'), ('la', 3, 'argo', 'argo')]}
    for lem in ('alexander', 'roma', 'romanus', 'argos', 'argo'):
        prep['stats']['la'][lem] = [10, 10, 10, 10]
    return entities, types, prep


def _lemmas(info, entities, lang='la'):
    return {entities[i]['label']: sorted(v) for i, v in info['ent_lemmas'][lang].items()}


def test_model_decisions_replace_the_audit_and_mark_other_lemmas_ambiguous():
    entities, types, prep = _world()
    id_of = {e['label']: e['entity_id'] for e in entities}
    _t, info0 = el.assemble_matcher(entities, types, prep, overrides=False, log=lambda *_: None)
    assert _lemmas(info0, entities)['Rome'] == ['roma']          # the audit drops the ending 'anus'
    dec = {('la', id_of['Rome'], 'romanus'): 'keep', ('la', id_of['Argos'], 'argo'): 'other',
           ('la', id_of['Alexander of Pherae'], 'alexander'): 'drop'}
    t2e, info = el.assemble_matcher(entities, types, prep, overrides=False, log=lambda *_: None, decisions=dec)
    assert _lemmas(info, entities)['Rome'] == ['roma', 'romanus']  # a model 'yes' overrides the audit
    assert 'argo' in _lemmas(info, entities)['Argos']
    assert 'Alexander of Pherae' not in _lemmas(info, entities) or _lemmas(info, entities)['Alexander of Pherae'] == []
    assert info['amb_tokens']['la'] == {'argo'}
    assert 'romanus' in t2e['la']


def test_window_answers_pick_one_of_the_entities_that_share_a_token():
    entities, types, prep = _world()
    t2e, info = el.assemble_matcher(entities, types, prep, overrides=False, log=lambda *_: None)
    ids = [e['entity_id'] for e in entities]
    a_idx = [i for i, e in enumerate(entities) if e['label'].startswith('Alexander')]
    assert len(a_idx) == 2
    texts = sqlite3_texts({'w1': 'Tum Alexander uenit.', 'w2': 'Hic Alexander cecidit.'})
    unit = {'w1', 'w2'}
    amb = info['amb_tokens']
    rows, _, _ = el.scan_windows_lemma(texts, unit, t2e, amb_tokens=amb)
    assert len(rows) == 4 and all(r['homonym'] for r in rows)
    collect = {}
    el.scan_windows_lemma(texts, unit, t2e, amb_tokens=amb, collect=collect)
    assert len(collect) == 2 and {k[0] for k in collect} == {'w1', 'w2'}
    great = next(e['entity_id'] for e in entities if 'Great' in e['label'])
    cands = tuple(sorted(ids[i] for i in a_idx))
    ans = el.answers_by_index(entities, {('w1', cands): great, ('w2', cands): None})
    rows, _, tally = el.scan_windows_lemma(texts, unit, t2e, amb_tokens=amb, answers=ans)
    assert [(r['wid'], entities[r['eidx']]['entity_id'], r['homonym']) for r in rows] == [('w1', great, False)]
    assert tally['mentions_removed_by_answer'] == 3


def test_scan_without_ambiguity_data_is_the_stage_1b_scan():
    entities, types, prep = _world()
    t2e, _ = el.assemble_matcher(entities, types, prep, overrides=False, log=lambda *_: None)
    texts = sqlite3_texts({'w1': 'Tum Alexander et Roma.'})
    rows, _, _ = el.scan_windows_lemma(texts, {'w1'}, t2e)
    c = collections.Counter(entities[r['eidx']]['label'] for r in rows)
    assert c['Rome'] == 1 and c['Alexander the Great'] == 1 and all(
        r['homonym'] == (entities[r['eidx']]['label'].startswith('Alexander')) for r in rows)


def sqlite3_texts(d):
    import sqlite3
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE window_texts (id TEXT, language TEXT, work TEXT, ref_start TEXT, ref_end TEXT, text TEXT)')
    c.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', [(k, 'la', 'w', '1', '2', v) for k, v in d.items()])
    return c


def _script():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'entity_model_pass.py')
    spec = importlib.util.spec_from_file_location('entity_model_pass_script', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_reverse_job_reverses_the_candidates_and_their_prompt_lines():
    m = _script()
    prompt = mp.pass2_prompt('text', 'Alexandro', [
        {'label': 'A', 'type': 'person', 'description': 'first.'},
        {'label': 'B', 'type': 'person', 'description': 'second.'}])
    job = {'window_id': 'w', 'cands': ['ln:A', 'ln:B'], 'prompt': prompt}
    rev = m.reverse_job(job)
    assert rev['cands'] == ['ln:B', 'ln:A']
    assert '1. B (person). second.\n2. A (person). first.\n0. none of these' in rev['prompt']


def test_a_window_is_answered_only_when_both_orders_agree(tmp_path):
    m = _script()
    fwd, rev = tmp_path / 'f.jsonl', tmp_path / 'r.jsonl'

    def row(w, cands, chosen, answer=1):
        return {'window_id': w, 'cands': cands, 'chosen': chosen, 'answer': answer}
    fwd.write_text('\n'.join(json.dumps(r) for r in [
        row('w1', ['a', 'b'], 'a'), row('w2', ['a', 'b'], 'a'), row('w3', ['a', 'b'], None, 0),
        row('w4', ['a'], 'a')]))
    rev.write_text('\n'.join(json.dumps(r) for r in [
        row('w1', ['b', 'a'], 'a'), row('w2', ['b', 'a'], 'b'), row('w3', ['b', 'a'], None, 0)]))
    out = m.load_answers(str(fwd), str(rev))
    assert out == {('w1', ('a', 'b')): 'a', ('w3', ('a', 'b')): None, ('w4', ('a',)): 'a'}


def test_chat_url_accepts_only_web_schemes():
    import pytest
    assert gw.chat_url('https://gw.example/v1') == 'https://gw.example/v1/chat/completions'
    assert gw.chat_url('http://127.0.0.1:9/v1/chat/completions') == 'http://127.0.0.1:9/v1/chat/completions'
    with pytest.raises(ValueError):
        gw.chat_url('file:///etc/passwd')
