#!/usr/bin/env python3
"""Record what the assistant's _prepare() returns for a set of questions, with every outside answer held still.

    python3 scripts/review/assistant_prepare_record.py capture QUESTIONS FIXTURE [--env ENVFILE]
    python3 scripts/review/assistant_prepare_record.py record  QUESTIONS FIXTURE OUT
    python3 scripts/review/assistant_prepare_record.py check   QUESTIONS FIXTURE RECORDING

QUESTIONS is a JSON list of objects: {"id", "question", "history" (optional list of
{"role","text"}), "offered_phrase" (optional)}. Run it from the repository root of the
tree being tested, with that tree's python path (the tree's backend package is imported).

What is held still. _prepare() meets the outside world in exactly two places: the model
(backend.assistant.model.complete, used for the routing judgment and the chooser) and the
site's own search routes (backend.assistant.searches._get, which every search, listing and
census goes through). Both are replaced by a FIXTURE, a JSON file of the answers they gave
when `capture` ran against the real gateway and the real site. `record` and `check` never
touch the network: a model call or a search the fixture does not hold is counted as a MISS
and fails the run, because it means the code asked for something the captured run never
asked for. The two comparison routes (/fusion-search, /crosslingual-search-poll) are
answered by a fixed rule in both modes (about one pair in four is "still running", the rest
return three canned parallels), so capture never starts a real comparison. time.sleep is a
no-op so the wait loop of a "still running" pair does not wait.

Each question is run twice, with model routing on and off, because production runs with it
on and the heuristics are the path when the model cannot answer. For every run the
recording keeps: the dict _prepare returned (block text, facts, ran, error, flags, all of
it), the progress messages passed to step(), and the ordered list of outside calls made
(a short hash of each model prompt, and each search path with its parameters). Two
recordings are equal only if every one of those is equal. Nothing is normalized: the
stubbed model and searches leave no timestamp or elapsed time in what is kept. The one
source of variation between runs found on main is string-hash order in _named_works (a set
sorted by length), so the script restarts itself with PYTHONHASHSEED=0.

`record` also prints the total seconds spent in the _prepare calls, for the timing check.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
import time

# _named_works sorts a set of names by length, so ties come out in string-hash order, which
# changes from one process to the next. A fixed hash seed makes two runs comparable.
if os.environ.get('PYTHONHASHSEED') != '0':
    os.environ['PYTHONHASHSEED'] = '0'
    os.execv(sys.executable, [sys.executable] + sys.argv)

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

_STATE = {'mode': 'record', 'fixture': {}, 'dirty': False, 'calls': [], 'misses': []}
_FIXTURE_ENV_KEYS = ('TESSERAE_LLM_URL', 'TESSERAE_LLM_MODEL', 'TESSERAE_LLM_API_KEY',
                     'TESSERAE_LLM_EXTRA_JSON')


def _load_env(path):
    """Copy the model settings from an .env file into os.environ. Prints nothing."""
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            if k.strip() in _FIXTURE_ENV_KEYS:
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


def _key(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=False,
                                   default=str).encode('utf-8')).hexdigest()


def _canned_page(path, params):
    """The fixed rule for the two comparison routes."""
    pair = _key(path, params.get('source'), params.get('target'))
    if int(pair[:4], 16) % 4 == 0:
        return {'status': 'running'}
    return {'status': 'complete', 'parallels': [
        {'source': {'ref': f'{params.get("source")} {i}'}, 'target': {'ref': f'{params.get("target")} {i}'},
         'score': 9 - i} for i in range(1, 4)]}


def _install(model, searches, real_complete, real_get):
    """Replace the model and the site's search transport by the fixture."""
    fixture = _STATE['fixture']
    capture = _STATE['mode'] == 'capture'

    def complete(system, user, max_tokens=900, temperature=0.2):
        k = _key('model', system, user, max_tokens, temperature)
        _STATE['calls'].append('model:' + k[:12])
        store = fixture.setdefault('model', {})
        if k in store:
            return store[k]
        if not capture:
            _STATE['misses'].append('model:' + k[:12] + ' ' + user[:80].replace('\n', ' '))
            return None
        out = real_complete(system, user, max_tokens=max_tokens, temperature=temperature)
        store[k] = out
        _STATE['dirty'] = True
        return out

    def get(path, params):
        label = path + '?' + json.dumps(params, sort_keys=True, ensure_ascii=False)
        _STATE['calls'].append('get:' + label)
        if path in ('/fusion-search', '/crosslingual-search-poll'):
            return _canned_page(path, params)
        k = _key('get', path, params)
        store = fixture.setdefault('get', {})
        if k not in store:
            if not capture:
                _STATE['misses'].append('get:' + label[:120])
                raise searches.SearchError('not in the fixture')
            try:
                store[k] = ['ok', json.dumps(real_get(path, params), ensure_ascii=False)]
            except searches.SearchError as e:
                store[k] = ['error', str(e)]
            _STATE['dirty'] = True
        kind, payload = store[k]
        if kind == 'error':
            raise searches.SearchError(payload)
        return json.loads(payload)

    model.complete = complete
    model.is_available = lambda: True
    searches._get = get
    # The TOOLS table holds lambdas that look _get up by name at call time, so the
    # replacement above is seen by them.
    time.sleep = lambda s: None


def _reset_caches(classify, searches, corpus_lookup):
    classify._CACHE.clear()
    searches._census_cache.clear()
    searches._listing_cache.clear()
    corpus_lookup._texts.clear()


def _run_all(questions, out_path=None):
    from backend.assistant import agent, classify, corpus_lookup, model, searches
    real_complete, real_get = model.complete, searches._get
    _install(model, searches, real_complete, real_get)
    recording, total = [], 0.0
    for item in questions:
        for routing in (True, False):
            agent._MODEL_ROUTING = routing
            _reset_caches(classify, searches, corpus_lookup)
            _STATE['calls'] = []
            steps = []
            t0 = time.perf_counter()
            try:
                out = agent._prepare(item['question'], steps.append,
                                     copy.deepcopy(item.get('history')),
                                     item.get('offered_phrase'))
            except Exception as e:                          # noqa: BLE001
                out = {'RAISED': f'{type(e).__name__}: {e}'}
            total += time.perf_counter() - t0
            recording.append({
                'id': item['id'], 'routing': routing,
                'result': json.loads(json.dumps(out, ensure_ascii=False, default=str)),
                'steps': steps, 'calls': list(_STATE['calls'])})
    return recording, total


def _summary(recording):
    kinds = {}
    for r in recording:
        res = r['result']
        k = ('error' if 'error' in res else 'needs_model_only' if res.get('needs_model_only')
             else 'RAISED' if 'RAISED' in res
             else 'theme_compare' if 'theme_compare' in res
             else 'fusion_results' if 'fusion_results' in res else 'block')
        kinds[k] = kinds.get(k, 0) + 1
    return kinds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('capture', 'record', 'check'))
    ap.add_argument('questions')
    ap.add_argument('fixture')
    ap.add_argument('third', nargs='?')
    ap.add_argument('--env')
    a = ap.parse_args()
    if a.env:
        _load_env(a.env)
    questions = json.load(open(a.questions, encoding='utf-8'))
    if os.path.exists(a.fixture):
        _STATE['fixture'] = json.load(open(a.fixture, encoding='utf-8'))
    elif a.mode != 'capture':
        print('no fixture; run capture first')
        return 2
    _STATE['mode'] = a.mode
    recording, total = _run_all(questions)
    if a.mode == 'capture' and _STATE['dirty']:
        json.dump(_STATE['fixture'], open(a.fixture, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{len(questions)} questions x 2 routing modes = {len(recording)} runs; '
          f'seconds inside _prepare: {total:.2f}')
    print('outcomes:', _summary(recording))
    if _STATE['misses'] and a.mode != 'capture':
        print(f'FIXTURE MISSES: {len(_STATE["misses"])}')
        for m in _STATE['misses'][:20]:
            print('  ', m)
    if a.mode in ('capture', 'record'):
        if a.mode == 'record':
            json.dump(recording, open(a.third, 'w', encoding='utf-8'), ensure_ascii=False,
                      indent=1, sort_keys=True)
            print('wrote', a.third)
        return 1 if _STATE['misses'] and a.mode == 'record' else 0
    old = json.load(open(a.third, encoding='utf-8'))
    new = json.loads(json.dumps(recording, ensure_ascii=False, sort_keys=True))
    same = sum(1 for x, y in zip(old, new) if x == y)
    print(f'identical: {same} of {len(old)} runs (new recording has {len(new)})')
    bad = [(x, y) for x, y in zip(old, new) if x != y]
    for x, y in bad[:10]:
        fields = [f for f in ('result', 'steps', 'calls') if x.get(f) != y.get(f)]
        print('  DIFFERS', x['id'], 'routing', x['routing'], fields)
    return 0 if same == len(old) == len(new) and not _STATE['misses'] else 1


if __name__ == '__main__':
    sys.exit(main())
