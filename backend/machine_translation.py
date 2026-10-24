"""A machine translation of a selected passage, on request, from the free campus model.

Only for passages with no aligned human translation. The model is reached over
the university's gateway (the same address and key the assistant uses), never a
paid service: the model name must look like a gateway model name and the
gateway address must not be a known paid host, otherwise the setting is
refused at startup with a logged error and the default model is used.

Each answer is cached on disk, so a passage is translated once. One request per
visitor at a time, and a ceiling on requests in flight at once (per web worker).
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

from backend.logging_config import get_logger

logger = get_logger('machine_translation')

DEFAULT_MODEL = 'zai-org/GLM-5.2'
_GATEWAY_NAME = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+$')
_PAID_HOSTS = ('api.openai.com', 'api.anthropic.com', 'generativelanguage.googleapis.com',
               'api.mistral.ai', 'api.cohere.com', 'api.x.ai', 'openrouter.ai')

MAX_LINES = 40
TIMEOUT_SECONDS = 60
MAX_IN_FLIGHT = 4
MAX_TOKENS = 3000

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.environ.get('TESSERAE_MT_CACHE_DIR') or os.path.join(_ROOT, 'cache', 'machine_translations')

# Trial figures (121 passages graded blind, 2026-10-23): fully right, nearly
# right, wrong, and passages graded, per kind of text.
TRIAL = {
    ('la', 'prose'): (15, 10, 0, 25),
    ('la', 'verse'): (16, 8, 1, 25),
    ('grc', 'prose'): (10, 8, 3, 21),
    ('grc', 'verse'): (10, 14, 1, 25),
    ('fa', 'verse'): (7, 14, 4, 25),
}
LANGUAGE_NAMES = {'la': 'Latin', 'grc': 'Ancient Greek', 'fa': 'Persian', 'ur': 'Urdu', 'ar': 'Arabic',
                  'he': 'Hebrew', 'cop': 'Coptic', 'en': 'English'}

PROMPT = (
    'Translate the following {language} passage into plain modern English prose. '
    'Keep the order of the lines and start a new line for each source line. '
    'Do not add notes or alternatives. If a word is unreadable or the text is corrupt, '
    'write [unclear] at that point. Give one version only, with no commentary.\n\n'
    'Author and work: {author}, {title}.\n\n{lines}')


def configured_model(environ=None):
    """The model named by TESSERAE_TRANSLATE_MODEL, or the default when the
    setting is not a gateway model name or the gateway is a paid host."""
    env = os.environ if environ is None else environ
    model = (env.get('TESSERAE_TRANSLATE_MODEL') or DEFAULT_MODEL).strip()
    url = (env.get('TESSERAE_LLM_URL') or '').lower()
    if any(h in url for h in _PAID_HOSTS):
        logger.error('[MT] gateway address %s is a paid service; machine translation is switched off', url)
        return None
    if not _GATEWAY_NAME.match(model) or any(
            w in model.lower() for w in ('claude', 'gpt-4', 'gpt-5', 'gemini', 'fable', 'opus', 'sonnet')):
        logger.error('[MT] TESSERAE_TRANSLATE_MODEL=%r is not a gateway model name; using %s', model, DEFAULT_MODEL)
        return DEFAULT_MODEL
    return model


MODEL = configured_model()

_ENDPOINT = os.environ.get('TESSERAE_LLM_URL', '').rstrip('/')
_API_KEY = os.environ.get('TESSERAE_LLM_API_KEY', '').strip()

_gate = threading.Semaphore(MAX_IN_FLIGHT)
_busy = set()
_busy_lock = threading.Lock()


class Busy(Exception):
    """Too many translations in flight, or this visitor already has one."""


def reliability(language, kind):
    """{'right', 'nearly', 'wrong', 'of'} for the kind, or None if untested."""
    t = TRIAL.get((language, kind))
    if not t:
        return None
    return {'right': t[0], 'nearly': t[1], 'wrong': t[2], 'of': t[3]}


def build_prompt(language_name, author, title, lines):
    return PROMPT.format(language=language_name, author=author, title=title, lines='\n'.join(lines))


def cache_path(model, work, refs):
    h = hashlib.sha256('|'.join(refs).encode('utf-8')).hexdigest()[:32]
    safe = lambda s: re.sub(r'[^A-Za-z0-9_.-]', '_', s)  # noqa: E731
    return os.path.join(CACHE_DIR, safe(model), safe(work), h + '.json')


def _read_cache(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_cache(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp%d' % os.getpid()
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as e:
        logger.warning('[MT] could not write cache %s: %s', path, e)


def _call_gateway(prompt, model):
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0, 'max_tokens': MAX_TOKENS,
            'chat_template_kwargs': {'enable_thinking': False}}
    headers = {'Content-Type': 'application/json'}
    if _API_KEY:
        headers['Authorization'] = 'Bearer ' + _API_KEY
    req = urllib.request.Request(f'{_ENDPOINT}/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:  # nosec B310 - fixed gateway from configuration
        return json.loads(r.read())['choices'][0]['message']['content']


def translate(work, refs, source_lines, language, author, title, visitor):
    """The machine translation as a list of lines, from cache when possible.

    Returns (lines, cached). Raises Busy when this visitor already has a
    request running or the ceiling is reached; other failures propagate."""
    path = cache_path(MODEL, work, refs)
    hit = _read_cache(path)
    if hit and isinstance(hit.get('lines'), list):
        return hit['lines'], True
    with _busy_lock:
        if visitor in _busy:
            raise Busy('You already have a machine translation running. Please wait for it to finish.')
        _busy.add(visitor)
    got = False
    try:
        got = _gate.acquire(blocking=False)
        if not got:
            raise Busy('The machine translation service is busy. Please try again in a minute.')
        started = time.time()
        text = _call_gateway(build_prompt(LANGUAGE_NAMES.get(language, language), author, title,
                                          source_lines), MODEL)
        logger.info('[MT] %s %d lines %s in %.1fs', work, len(source_lines), MODEL, time.time() - started)
    finally:
        if got:
            _gate.release()
        with _busy_lock:
            _busy.discard(visitor)
    lines = [ln.strip() for ln in (text or '').strip().splitlines() if ln.strip()]
    if lines:
        _write_cache(path, {'model': MODEL, 'work': work, 'refs': refs, 'lines': lines,
                            'made': time.strftime('%Y-%m-%d')})
    return lines, False
