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
    allowed = {_normalise_ref(r) for r in (allowed_refs or [])}
    removed = []

    def keep(match):
        cand = _normalise_ref(match.group(1))
        if not allowed or any(cand in a or a in cand for a in allowed):
            return match.group(0)
        removed.append(match.group(1))
        return 'that passage'

    cleaned = _REF_PATTERN.sub(keep, text)
    if removed:
        logger.warning('[ASSISTANT] removed unsupported references: %s', removed)
    return cleaned, removed


def _normalise_ref(ref):
    return re.sub(r'[^a-z0-9.]', '', str(ref).lower())


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
