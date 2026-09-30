"""A second look at the specifics in an answer.

The prompts let the assistant bring in what it knows as background, and the
guards in model.py do not reach that far: they check citations, quotations
and figures against the material the assistant was given, and a wrong century
or a misattributed work carries none of those. This asks the model, a second
time and with the same material in front of it, which sentences make a
specific checkable claim the material does not support, and what each would
say with the specific removed or made uncertain. The revision replaces the
sentence; nothing is added.

Only specifics are in scope: a date, century or reign, the attribution of a
work, the title of a work, what a work contains. A critical judgement (that
one poem answers another) is not a claim of this kind and is left alone.

TESSERAE_ASSISTANT_BACKGROUND_CHECK=0 turns it off.
"""
import json
import os
import re

from backend.assistant import model
from backend.logging_config import get_logger

logger = get_logger('assistant.background')

SYSTEM = (
    'You check one answer written by a website\'s assistant. You are given the MATERIAL the '
    'assistant was shown (sections of the site\'s help, the site\'s list of an author\'s works '
    'with their descriptions, computed facts about search results) and the ANSWER it wrote. '
    'Find each sentence of the answer that makes a SPECIFIC checkable claim the material does '
    'not support: a date, century or reign; the attribution of a work to an author; the title '
    'of a work; what a work contains or is about. A broad period word (late antique, medieval, '
    'Hellenistic, classical) is not a specific date. A judgement about influence, imitation or '
    'style (that one poet imitated another, that a poem answers another, that a parallel looks '
    'like allusion) is not such a claim and must not be listed. A statement of '
    'what the site holds or does that follows the material is supported. Reply with JSON only: '
    '{"unsupported": [{"sentence": "<the sentence exactly as written>", '
    '"claim": "<the unsupported specific>", "revised": "<the sentence with the specific '
    'removed or made uncertain, or an empty string to drop the sentence>"}]}. '
    'If nothing is unsupported reply {"unsupported": []}.')

_MAX_TOKENS = 700


def worth_checking(text):
    """A results reading is checked when it reaches beyond the results: a
    sentence marked as background, or a date, century or reign, which the
    computed facts never contain. Line numbers alone are not a reason."""
    return bool(re.search(r'background|centur|\bBC\b|\bAD\b|\breign|\bdied\b|\bborn\b', text or '', re.I))


def enabled():
    return (os.environ.get('TESSERAE_ASSISTANT_BACKGROUND_CHECK') or '').strip() != '0'


def check(answer, material):
    """The model's list of unsupported specifics, or [] when it finds none or fails."""
    user = f'MATERIAL:\n{material[:12000]}\n\nANSWER:\n{answer}\n\nJSON:'
    raw = model.complete(SYSTEM, user, max_tokens=_MAX_TOKENS, temperature=0.0) or ''
    start, end = raw.find('{'), raw.rfind('}')
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(raw[start:end + 1])
    except ValueError:
        return []
    out = []
    for item in data.get('unsupported') or []:
        if not (isinstance(item, dict) and item.get('sentence')):
            continue
        sentence = str(item['sentence']).strip()
        claim = str(item.get('claim') or '').strip()
        if not _specific(sentence, claim):
            continue
        out.append({'sentence': sentence, 'claim': claim,
                    'revised': str(item.get('revised') or '').strip()})
    return out


def _specific(sentence, claim):
    """Only the specifics are in scope, whatever the model listed.

    Tried on a real answer the model flagged "a late antique Latin poet" and
    "a devoted imitator of Vergil", a period word and a judgement, and the
    revision gutted a fair answer. A finding is kept when the sentence carries
    a date-like token or the claim names a title, an attribution or contents.
    """
    if re.search(r'\d|\bcentur|\bBC\b|\bAD\b|\breign|\bdied\b|\bborn\b|\bflourish', sentence, re.I):
        return True
    return bool(re.search(r'title|attribut|author|wrote|composed|content|\babout\b|retell|narrat|describ',
                          claim, re.I))


def apply(answer, findings):
    """Replace or drop the flagged sentences. Returns (text, applied).

    A revision may not introduce a digit its sentence did not have, and may
    not be longer than half again the sentence it replaces. The answer is
    left alone if the result would fall below two fifths of its length.
    """
    text = answer or ''
    applied = []
    for f in findings:
        sent = f['sentence']
        if not sent or sent not in text:
            continue
        rev = f.get('revised') or ''
        if rev and (set(re.findall(r'\d', rev)) - set(re.findall(r'\d', sent))
                    or len(rev) > 1.5 * len(sent)):
            rev = ''
        new = text.replace(sent, rev, 1)
        new = re.sub(r'\s{2,}', ' ', new).strip()
        applied.append({'claim': f.get('claim') or '', 'dropped': not rev})
        text = new
    if applied and len(text) < 0.4 * len(answer or ''):
        return answer, []
    return text, applied


def review(answer, material):
    """Check and apply. Returns (text, verdict) where verdict is a small dict
    the route can pass to the page and the record."""
    if not enabled() or not answer or not material:
        return answer, {'checked': False}
    try:
        findings = check(answer, material)
    except Exception as e:  # noqa: BLE001
        logger.info('[ASSISTANT] background check failed: %s', e)
        return answer, {'checked': False}
    text, applied = apply(answer, findings)
    if applied:
        logger.info('[ASSISTANT] background check revised %d sentence(s): %s',
                    len(applied), '; '.join(a['claim'] for a in applied)[:300])
    return text, {'checked': True, 'flagged': len(findings), 'revised': applied}
