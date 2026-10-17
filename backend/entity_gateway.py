"""A small client for the campus language-model gateway, used by the entity model pass
(stage 1d, 2026-10-17). One question, one short answer, temperature 0, thinking off.

The address and the key are read from the production .env (TESSERAE_LLM_URL and
TESSERAE_LLM_API_KEY) or from the environment, held in the object, and never printed,
logged or written to a file. Failures are counted by kind and carry no address.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

MODEL = 'Qwen/Qwen3.8-27B-FP8'
DEFAULT_ENV = '/var/www/tesseraev6_flask/.env'


def load_config(env_path=DEFAULT_ENV):
    """Return (url, key). The environment wins over the file."""
    vals = {}
    if env_path and os.path.exists(env_path):
        for line in open(env_path, encoding='utf-8'):
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.rstrip('\n').split('=', 1)
                vals[k.strip()] = v.strip().strip('"\'')
    url = os.environ.get('TESSERAE_LLM_URL') or vals.get('TESSERAE_LLM_URL')
    key = os.environ.get('TESSERAE_LLM_API_KEY') or vals.get('TESSERAE_LLM_API_KEY')
    if not url or not key:
        raise RuntimeError('gateway address or key not set')
    return url, key


def chat_url(url):
    """The chat-completions address for a gateway base address. Only http and https are
    accepted, so a file or custom scheme from a misread setting cannot reach urlopen."""
    if not url.startswith(('https://', 'http://')):
        raise ValueError('gateway address must start with https:// or http://')
    if url.endswith('/chat/completions'):
        return url
    u = url.rstrip('/')
    return u + ('/chat/completions' if u.endswith('/v1') else '/v1/chat/completions')


class Gateway:
    def __init__(self, url, key, model=MODEL, timeout=120, retries=5, sleep_429=(30, 60, 120, 240, 300),
                 sleep_fn=time.sleep):
        self._url = chat_url(url)
        self._key = key
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.sleep_429 = sleep_429
        self._sleep = sleep_fn
        self._lock = threading.Lock()
        self.stats = {'requests': 0, 'answered': 0, 'failed': 0, 'retries': 0, 'http_429': 0, 'errors': {}}

    def _bump(self, k, n=1):
        with self._lock:
            self.stats[k] += n

    def _err(self, name):
        with self._lock:
            self.stats['errors'][name] = self.stats['errors'].get(name, 0) + 1

    def ask(self, system, user, max_tokens=12):
        """The reply text, or None after the retries are used up."""
        self._bump('requests')
        body = json.dumps({'model': self.model, 'max_tokens': max_tokens, 'temperature': 0,
                           'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                           'chat_template_kwargs': {'enable_thinking': False}}).encode()
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(self._url, data=body, headers={
                    'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # nosec B310
                    txt = json.loads(r.read())['choices'][0]['message'].get('content') or ''
                self._bump('answered')
                return txt
            except urllib.error.HTTPError as e:
                self._err('http_%d' % e.code)
                if e.code == 429:
                    self._bump('http_429')
                    self._bump('retries')
                    self._sleep(self.sleep_429[min(attempt, len(self.sleep_429) - 1)])
                    continue
            except Exception as e:  # noqa: BLE001
                self._err(type(e).__name__)
            self._bump('retries')
            self._sleep(3)
        self._bump('failed')
        return None


def run_jobs(jobs, work, threads, on_result=None):
    """Run work(job) for each job on a pool of `threads`, in order of completion. Returns
    (results in job order, seconds). on_result(job, result) is called in the main thread."""
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.time()
    out = []
    with ThreadPoolExecutor(threads) as ex:
        for job, res in zip(jobs, ex.map(work, jobs)):
            out.append(res)
            if on_result:
                on_result(job, res)
    return out, time.time() - t0
