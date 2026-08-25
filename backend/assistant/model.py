"""Client for the locally served open model, plus the guardrails around it.

The model runs on this machine under llama-server (an OpenAI-compatible HTTP
server), so nothing leaves the building and there is no API key or per-query
cost. Qwen3-30B-A3B-Instruct is the intended model: it activates about 3.3B of
its 30.5B parameters per token, so on this CPU it generates at roughly the speed
of a 3B model while reasoning far better. Apache-2.0.

If the model is not running, every entry point here fails soft. The assistant
disappears from the interface rather than breaking a page: the search tools are
the product, and the assistant is help on top of them.
"""
import json
import os
import re
import urllib.error
import urllib.request

from backend.logging_config import get_logger

logger = get_logger('assistant.model')

ENDPOINT = os.environ.get('TESSERAE_LLM_URL', 'http://127.0.0.1:8081')
MODEL_NAME = os.environ.get('TESSERAE_LLM_MODEL', 'local')
_HEALTH_TIMEOUT = 2
_GEN_TIMEOUT = 180

# Generation stays short on purpose. A small model asked for a paragraph writes a
# good paragraph; asked for an essay it starts inventing to fill the space, and
# on CPU every extra sentence costs seconds.
MAX_TOKENS_GUIDE = 220
MAX_TOKENS_ANALYZE = 420


def is_available():
    """True when the local model server answers. Cheap enough to call per request."""
    try:
        with urllib.request.urlopen(f'{ENDPOINT}/health', timeout=_HEALTH_TIMEOUT) as r:
            return json.loads(r.read()).get('status') == 'ok'
    except Exception:
        return False


def complete(system, user, max_tokens=MAX_TOKENS_GUIDE, temperature=0.2):
    """One turn against the local model. Returns text, or None when unavailable."""
    body = json.dumps({
        'model': MODEL_NAME,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user}],
        'temperature': temperature,
        'max_tokens': max_tokens,
    }).encode()
    req = urllib.request.Request(f'{ENDPOINT}/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=_GEN_TIMEOUT) as r:
            payload = json.loads(r.read())
        return payload['choices'][0]['message']['content'].strip()
    except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
        logger.warning('[ASSISTANT] generation failed: %s', e)
        return None


def stream(system, user, max_tokens=MAX_TOKENS_GUIDE, temperature=0.2):
    """Yield the answer token by token as the model writes it.

    On a CPU the total time to a finished paragraph is 15-20 seconds, but the
    first words arrive in about two. Streaming therefore changes the experience
    far more than it changes the clock: a reader starts reading immediately
    instead of watching a spinner, and generation at 16 tokens per second
    outpaces reading speed. Yields plain text chunks; the caller frames them.
    """
    body = json.dumps({
        'model': MODEL_NAME,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user}],
        'temperature': temperature,
        'max_tokens': max_tokens,
        'stream': True,
    }).encode()
    req = urllib.request.Request(f'{ENDPOINT}/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=_GEN_TIMEOUT) as resp:
            for raw in resp:
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                payload = line[5:].strip()
                if payload == '[DONE]':
                    return
                try:
                    delta = json.loads(payload)['choices'][0].get('delta', {})
                except (ValueError, KeyError, IndexError):
                    continue
                piece = delta.get('content')
                if piece:
                    yield piece
    except (urllib.error.URLError, OSError) as e:
        logger.warning('[ASSISTANT] streaming failed: %s', e)
        return


# --------------------------------------------------------------------------
# Guardrails
# --------------------------------------------------------------------------
# A citation invented by a model is the one failure that would embarrass a
# scholar quoting this tool, and purpose-built commercial systems still do it at
# 17-33%. So the model is never the source of a reference: it narrates facts we
# computed, and anything that looks like a citation it produced on its own is
# checked against the references we actually gave it.
_REF_PATTERN = re.compile(r'\b([A-Z][a-z]+\.?\s+[A-Z]?[a-z]*\.?\s*\d+\.\d+)\b')


def strip_unsupported_references(text, allowed_refs):
    """Remove citations the model produced that were not in its input.

    Returns (cleaned_text, removed_list). A removed citation is a bug worth
    logging: it means the prompt let the model believe it should cite.
    """
    if not text:
        return text, []
    allowed = [_ref_parts(r) for r in (allowed_refs or [])]
    removed = []

    def keep(match):
        if not allowed:
            return match.group(0)
        c_locus, c_words = _ref_parts(match.group(1))
        for a_locus, a_words in allowed:
            if c_locus != a_locus:
                continue
            # The locus agrees; one shared name word (or a prefix of one, since
            # "Verg." abbreviates "vergil") is enough to call it the same citation.
            if not c_words or any(
                    cw == aw or aw.startswith(cw) or cw.startswith(aw)
                    for cw in c_words for aw in a_words):
                return match.group(0)
        removed.append(match.group(1))
        return 'that passage'

    cleaned = _REF_PATTERN.sub(keep, text)
    if removed:
        logger.warning('[ASSISTANT] removed unsupported references: %s', removed)
    return cleaned, removed


def _normalise_ref(ref):
    return re.sub(r'[^a-z0-9.]', '', str(ref).lower())


def _ref_parts(ref):
    """Split a reference into its name words and its numeric locus.

    Our tags carry the full work name ("lucan.bellum_civile 1.1") while a writer
    naturally shortens it to "Lucan 1.1". Comparing the whole strings called that
    shortening a fabrication. What actually identifies a citation is the locus
    plus at least one name word, so compare those.
    """
    s = re.sub(r'[^a-z0-9. ]', ' ', str(ref).lower())
    locus = re.findall(r'\d+(?:\.\d+)*', s)
    words = {w for w in re.split(r'[ .]+', re.sub(r'\d', ' ', s)) if len(w) > 2}
    return (locus[-1] if locus else ''), words


def numbers_preserved(source_text, generated):
    """True when the model introduced no numeric claim of its own.

    Borrowed from Tableau's practice of asserting that no number changes between
    the computed record and the prose. A number in the prose that never appeared
    in the facts is a fabricated statistic.
    """
    src_nums = set(re.findall(r'\d+(?:\.\d+)?', source_text or ''))
    gen_nums = set(re.findall(r'\d+(?:\.\d+)?', generated or ''))
    invented = {n for n in gen_nums - src_nums if len(n) > 1 or float(n) > 9}
    if invented:
        logger.warning('[ASSISTANT] generated unsupported numbers: %s', invented)
    return not invented, sorted(invented)
