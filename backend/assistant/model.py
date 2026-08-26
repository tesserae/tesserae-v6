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
# 220 cut the "how do I use my own AI" answer off mid-sentence, and that answer
# now stands in for a banner that used to be on every page, so it has to finish.
MAX_TOKENS_GUIDE = 700
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
            # A locus may be written SHORTER than the one in the results and
            # still be the same citation: the results carry "Tristia 2.1.534"
            # and a writer naturally cites "Tristia 2.1". Requiring equality
            # stripped correct references out of good answers, which is worse
            # than the fabrication it was guarding against. A prefix on a dot
            # boundary is the same passage, more loosely specified.
            if not (c_locus == a_locus
                    or a_locus.startswith(c_locus + '.')
                    or c_locus.startswith(a_locus + '.')):
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


# Spelled-out numbers the guard treats as claims. "one" is deliberately absent:
# it is idiomatic ("one of the works") far more often than numeric.
_WORD_NUMBERS = {
    'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
    'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
    'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
    'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000,
}


def numbers_preserved(source_text, generated, question=''):
    """True when the model introduced no numeric claim of its own.

    Borrowed from Tableau's practice of asserting that no number changes between
    the computed record and the prose. A number in the prose that never appeared
    in the facts is a fabricated statistic.

    The QUESTION counts as a source. Asked about "Thebaid 12", a good answer says
    "Thebaid 12" back, and the check was calling that 12 a fabricated statistic:
    the number was the user's own. A number the user supplied is the one kind of
    number the model demonstrably did not invent.
    """
    source = (source_text or '') + ' ' + (question or '')
    src_nums = set(re.findall(r'\d+(?:\.\d+)?', source))
    gen_nums = set(re.findall(r'\d+(?:\.\d+)?', generated or ''))
    invented = {n for n in gen_nums - src_nums if len(n) > 1 or float(n) > 9}

    # SPELLED-OUT NUMBERS COUNT TOO.
    #
    # This read digits only, so a fabricated statistic in words went straight
    # through. Asked for passages about a storm at sea, Tessa wrote "All but TWO
    # of the instances are from later authors", a quantified claim about the
    # corpus that nothing in the results supports, and the guard passed the
    # answer as clean. To a scholar an invented figure in words is no better
    # than one in digits.
    #
    # "one" is left out: it is idiomatic far more often than numeric ("one of
    # the works", "no one"), and flagging it would train the reader to ignore
    # the warning, which is worse than not checking.
    for word, value in _WORD_NUMBERS.items():
        if not re.search(rf'\b{word}\b', (generated or '').lower()):
            continue
        if re.search(rf'\b{word}\b', source.lower()) or str(value) in src_nums:
            continue
        invented.add(word)

    if invented:
        logger.warning('[ASSISTANT] generated unsupported numbers: %s', invented)
    return not invented, sorted(invented)


# Words that mark a line as the assistant's own English, not a quoted source.
_ENGLISH_TELLS = (
    ' the ', ' this ', ' that ', ' there ', ' appears', ' occurs', ' corpus',
    ' would ', ' these ', ' those ', ' which ', ' user', ' search', ' variant',
    ' instance', ' phrase ', ' works', ' lines ', ' total', ' such ', ' from the ',
)


def quotes_paired(facts, generated):
    """True when every quoted line belongs to the citation it is printed under.

    quotes_supported() asks whether a quoted line exists ANYWHERE in the
    results, and that is not enough. Asked to list twelve occurrences when six
    were shown, the model padded the list: it invented loci (Martial 1.11.1,
    Salutati 1.1) and printed VERGIL'S line under each of them. Every one of
    those quotes passed, because Aeneid 1.1 really is in the results -- under
    Vergil.

    So the check is now the PAIRING. A citation line followed by a line of
    source text must agree: that ref's text in the results must be what is
    printed beneath it.

    Returns (ok, [(ref, quoted_line), ...]) for the pairs that do not agree.
    """
    ref_text = {}
    for f in (facts or []):
        for key in ('examples', 'lines'):
            for e in (f.get(key) or []):
                if isinstance(e, dict) and e.get('ref') and e.get('text'):
                    ref_text[_norm(e['ref'])] = _norm(e['text'])

    if not ref_text:
        return True, []

    bad = []
    lines = [l.strip() for l in (generated or '').split('\n')]
    for i, line in enumerate(lines[:-1]):
        key = _norm(line)
        if not key or key not in ref_text:
            continue
        # the next non-empty line is what is being attributed to this citation
        nxt = next((l for l in lines[i + 1:i + 3] if l.strip()), '')
        if not nxt:
            continue
        quoted = _norm(nxt)
        if len(quoted) < 12:
            continue
        actual = ref_text[key]
        if quoted[:60] not in actual and actual[:60] not in quoted:
            bad.append((line, nxt[:70]))
    if bad:
        logger.warning('[ASSISTANT] quoted text does not match its citation: %s', bad[:3])
    return not bad, bad[:6]


def _norm(t):
    return ' '.join(re.sub(r'[^\w\s]', ' ', str(t or '').lower()).split())


def quotes_supported(facts_text, generated):
    """True when every passage the answer quotes actually appears in the facts.

    Added after the assistant, asked to list Eobanus's instances, produced twelve
    citations that each quoted the Aeneid's opening line as though it were
    Eobanus. The facts held the 21 real lines; a character cap had discarded them
    before the model saw them, and it reconstructed what it expected instead.

    Fabricated primary text is the worst output a corpus tool can produce, and it
    is the most convincing, so the check does not rely on the facts always
    arriving intact. Any line that reads as quoted source rather than English
    commentary must be found verbatim in the facts.

    Deliberately lenient about WHAT counts as a quotation and strict about
    whether a quotation checks out: a missed fabrication is far worse than a
    false alarm on a stray line.
    """
    # Compare on LETTERS, not characters. A model listing a verse line will add
    # or drop a comma, and the first version of this check called
    # "Quartam ducebant aciem vir maximus armis," a fabrication because the
    # results held the same line without the trailing comma. That is a guard
    # crying wolf on a true answer, which trains people to ignore it.
    #
    # Punctuation-insensitive and content-sensitive: the words themselves must
    # still match, so quoting the Aeneid's opening under an Eobanus citation is
    # still caught.
    def letters(t):
        return ' '.join(re.sub(r"[^\w\s]", ' ', (t or '').lower()).split())

    haystack = letters(facts_text)
    unsupported = []
    for raw in (generated or '').split('\n'):
        line = raw.strip(' \t*-–—•').strip()
        if len(line) < 18 or ':' in line or line.endswith('?'):
            continue
        padded = f' {line.lower()} '
        if any(t in padded for t in _ENGLISH_TELLS):
            continue          # the assistant's own prose, not a quotation
        probe = letters(line)
        if probe and probe not in haystack:
            unsupported.append(line[:80])
    if unsupported:
        logger.warning('[ASSISTANT] quoted text not found in results: %s',
                       unsupported[:3])
    return not unsupported, unsupported[:5]
