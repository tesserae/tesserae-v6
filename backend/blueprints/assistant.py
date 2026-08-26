"""
Tesserae V6 - Assistant Blueprint

An in-site helper backed by a locally served open model. Two jobs:
  guide    which searches to run for a given question, and in what order
  analyze  what a set of results actually shows, narrated from computed facts

Endpoints (POST unless noted):
    /assistant/status   GET, whether the assistant is available
    /assistant/guide    {question}
    /assistant/analyze  {results, source, target, question?}

Everything degrades soft. With no model running, /guide still answers the common
questions from the deterministic router and /analyze still returns the computed
findings without prose, so the feature thins rather than breaks.
"""
import json

from flask import Blueprint, Response, jsonify, request, session

from backend.logging_config import get_logger
from backend.assistant import (actions, agent, findings, model, prompts,
                               router, site_help)

logger = get_logger('blueprints.assistant')

assistant_bp = Blueprint('assistant', __name__)


TURN_HEAD = 400
TURN_TAIL = 400


def _trim_turn(text):
    """Cap a history turn without throwing away the END of it.

    THIS IS WHY "yes" KEPT REPEATING THE PREVIOUS ANSWER.

    Turns were capped with text[:600]. The offer of the inflected forms is
    appended to the END of an answer, and the answer that most needs it is a
    listing of a dozen quoted lines, which runs well past 600 characters. So the
    offer was cut off before the server ever saw it, `_pending_offer_from` found
    no OFFER_MARK, and "yes" fell through to the ordinary phrase search and
    printed the same list again.

    It passed every direct test because a test sends the offer sentence alone,
    which is short. Only the browser sends the whole answer.

    Keeping both ends preserves the offer and still bounds what reaches a prompt.
    """
    text = text.strip()
    if len(text) <= TURN_HEAD + TURN_TAIL:
        return text
    return f'{text[:TURN_HEAD]}\n[...]\n{text[-TURN_TAIL:]}'


def _remember_offer(payload):
    """Record whether this answer offered the inflected forms.

    NOTE: this cannot work from inside the streaming endpoint, and for a while
    it silently did not. Flask writes the session cookie with the response
    HEADERS, and a streaming body is generated after those have gone, so a
    session assignment made inside the generator is never sent to the browser.
    The stream therefore hands the offer to the client in the `done` event and
    the client sends it back on the next question; this remains for the
    non-streaming path.
    """
    try:
        session['tessa_offer'] = (payload.get('offer_phrase')
                                  if payload.get('offered_variants') else None)
    except Exception:
        pass


def _with_help(question):
    """The question, preceded by the Help sections that bear on it.

    The guide prompt describes the SEARCHES and nothing else, so it had never
    heard of the Reader or Theme Search and answered questions about them by
    listing the corpus. The Help page already says what every feature does and
    is kept current because readers use it, so it is the source rather than
    another copy in a prompt.

    Question-specific, and in the user turn rather than the system prompt, so
    the system prompt stays identical between requests and only a few hundred
    words of context are added instead of forty thousand.
    """
    try:
        block = site_help.context_for(question)
    except Exception as e:                               # noqa: BLE001
        logger.info('[ASSISTANT] help lookup failed: %s', e)
        return question
    return f'{block}\n\nQuestion: {question}' if block else question


@assistant_bp.route('/assistant/status')
def status():
    return jsonify({
        'available': model.is_available(),
        'router_only': not model.is_available(),
        'note': ('The assistant explains the searches and reads results. It works from '
                 'the search engine output only, and it does not know classical '
                 'scholarship independently.'),
    })


@assistant_bp.route('/assistant/ask-stream', methods=['POST'])
def ask_stream():
    """Answer a question by RUNNING searches, streaming as it goes.

    The difference from /guide: this one looks. /guide can only say which search
    to use, because it has no corpus access, and asked to recommend interesting
    searches it recommends tool names. This runs them and reports what came back.

    Events: step (what it is doing), chunk (answer text), done (facts, which
    searches ran, guardrail verdict).
    """
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    # Prior turns, so a follow-up can be resolved instead of being handed back
    # to the user as advice. Trimmed and capped: this goes into a prompt, and
    # the client is not a source to be trusted about size.
    history = []
    for turn in (data.get('history') or [])[-8:]:
        if isinstance(turn, dict) and turn.get('text'):
            history.append({'role': 'user' if turn.get('role') == 'user' else 'assistant',
                            'text': _trim_turn(str(turn['text']))})

    # SERVER-SIDE FALLBACK. The client sends the conversation, and a browser
    # running a cached older bundle sends nothing, which looks exactly like a
    # first question: "What about Eobanus?" then arrives with no idea what the
    # user was asking about, and the answer silently loses the thread. It did.
    #
    # The session cookie travels regardless of how old the loaded JavaScript is,
    # so the last few questions are kept there too. Questions only, capped and
    # truncated, because a session cookie is small and answers are long.
    try:
        remembered = [q for q in (session.get('tessa_qs') or []) if isinstance(q, str)]
    except Exception:
        remembered = []
    if not history and remembered:
        history = [{'role': 'user', 'text': q} for q in remembered]
    if question:
        try:
            session['tessa_qs'] = (remembered + [question[:300]])[-4:]
        except Exception:
            pass

    # An offer the assistant made last turn, so "yes" can be an acceptance
    # rather than a question with no content.
    #
    # The CLIENT is asked first, because it is the only one of the two that
    # actually works here: the session write happens inside the streaming
    # generator, after the cookie has already gone out with the headers, so it
    # never reaches the browser. The `done` event hands the phrase to the page
    # and the page sends it back.
    offered_phrase = None
    raw_offer = data.get('offered_phrase')
    if isinstance(raw_offer, str) and raw_offer.strip():
        offered_phrase = raw_offer.strip()[:120]
    if not offered_phrase:
        try:
            offered_phrase = session.get('tessa_offer')
        except Exception:
            offered_phrase = None

    def generate():
        if not question:
            yield _sse('error', {'error': 'question is required'})
            return
        try:
            for kind, payload in agent.answer_stream(question, history=history,
                                                     offered_phrase=offered_phrase):
                if kind == 'chunk':
                    yield _sse('chunk', {'text': payload})
                elif kind == 'step':
                    yield _sse('step', {'text': payload})
                else:
                    # Falls back to the guide when no search applies, so a
                    # question about how the tool works still gets answered.
                    if payload.get('needs_model_only'):
                        yield _sse('step', {'text': 'no search applies; explaining instead'})
                        for piece in model.stream(prompts.guide_system(),
                                                  _with_help(question),
                                                  max_tokens=model.MAX_TOKENS_GUIDE):
                            yield _sse('chunk', {'text': piece})
                        # The guide half now hands over too. Nothing was
                        # searched, so the actions come from what the QUESTION
                        # asks for -- resolved against texts the corpus really
                        # holds, and omitted where a name cannot be resolved.
                        yield _sse('done', {'searches_run': [],
                                            'fell_back_to_guide': True,
                                            'actions': actions.suggest(question)})
                        return
                    # Pass the terms worth marking through to the page, so a
                    # listing of Latin lines shows what actually matched.
                    _remember_offer(payload)
                    yield _sse('done', {**payload,
                                        'highlight': payload.get('highlight') or [],
                                        'actions': payload.get('actions') or []})
        except Exception as e:
            logger.error('[ASSISTANT] ask failed: %s', e)
            yield _sse('error', {'error': 'the assistant could not answer just now'})

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@assistant_bp.route('/assistant/guide', methods=['POST'])
def guide():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({'error': 'question is required'})

    canned = router.route(question)
    if canned:
        return jsonify({'answer': canned, 'source': 'reference', 'model_used': False})

    if not model.is_available():
        return jsonify({
            'answer': ("The assistant is not running just now. The Help page explains each "
                       "search, and Theme Search is the place to start when you know the "
                       "content but not the wording."),
            'source': 'fallback', 'model_used': False})

    text = model.complete(prompts.guide_system(), _with_help(question),
                          max_tokens=model.MAX_TOKENS_GUIDE)
    if not text:
        return jsonify({'error': 'the assistant could not answer just now',
                        'model_used': False})
    return jsonify({'answer': text, 'source': 'model', 'model_used': True})


@assistant_bp.route('/assistant/analyze', methods=['POST'])
def analyze():
    data = request.get_json(silent=True) or {}
    results = data.get('results') or []
    if not results:
        return jsonify({'error': 'results are required'})

    facts = findings.summarize_results(
        results, source_id=data.get('source'), target_id=data.get('target'))
    block = findings.format_for_narration(facts, passages=results)

    if not model.is_available():
        return jsonify({'facts': facts, 'answer': None, 'model_used': False,
                        'note': 'Computed findings only: the assistant is not running.'})

    ask = block
    if (data.get('question') or '').strip():
        ask = f"{block}\n\nThe scholar asks: {data['question'].strip()}"
    else:
        ask = f'{block}\n\nAnalyse what this evidence supports.'

    text = model.complete(prompts.ANALYZE_SYSTEM, ask,
                          max_tokens=model.MAX_TOKENS_ANALYZE)
    if not text:
        return jsonify({'facts': facts, 'answer': None, 'model_used': False,
                        'note': 'Computed findings only: generation failed.'})

    # Guardrails: the model may not introduce citations or numbers of its own.
    allowed = []
    for r in results:
        for side in ('source', 'target'):
            v = r.get(side)
            if isinstance(v, dict) and v.get('ref'):
                allowed.append(v['ref'])
    text, removed = model.strip_unsupported_references(text, allowed)
    ok_numbers, invented = model.numbers_preserved(block, text, question)

    return jsonify({
        'facts': facts,
        'answer': text,
        'model_used': True,
        'guardrails': {'references_removed': removed,
                       'unsupported_numbers': invented,
                       'clean': not removed and ok_numbers},
    })


# --------------------------------------------------------------------------
# Streaming variants
# --------------------------------------------------------------------------
# Total time to a finished paragraph on this CPU is 15-20 seconds, but the first
# words arrive in about two. Streaming therefore changes the experience far more
# than it changes the clock, since generation outpaces reading speed. The
# guardrails still run, on the assembled text, and their verdict is sent as a
# final event so the interface can flag or redact after the fact.


def _sse(event, payload):
    return f'data: {json.dumps({"type": event, **payload})}\n\n'


@assistant_bp.route('/assistant/guide-stream', methods=['POST'])
def guide_stream():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()

    def generate():
        if not question:
            yield _sse('error', {'error': 'question is required'})
            return
        canned = router.route(question)
        if canned:
            yield _sse('chunk', {'text': canned})
            yield _sse('done', {'source': 'reference', 'model_used': False})
            return
        if not model.is_available():
            yield _sse('chunk', {'text': 'The assistant is not running just now. '
                                         'The Help page explains each search.'})
            yield _sse('done', {'source': 'fallback', 'model_used': False})
            return
        for piece in model.stream(prompts.guide_system(), _with_help(question),
                                  max_tokens=model.MAX_TOKENS_GUIDE):
            yield _sse('chunk', {'text': piece})
        yield _sse('done', {'source': 'model', 'model_used': True})

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@assistant_bp.route('/assistant/analyze-stream', methods=['POST'])
def analyze_stream():
    data = request.get_json(silent=True) or {}
    results = data.get('results') or []

    def generate():
        if not results:
            yield _sse('error', {'error': 'results are required'})
            return
        facts = findings.summarize_results(
            results, source_id=data.get('source'), target_id=data.get('target'))
        # Send the computed findings first: they are true regardless of what the
        # model does next, and they give the reader something immediately.
        yield _sse('facts', {'facts': facts})
        if not model.is_available():
            yield _sse('done', {'model_used': False,
                                'note': 'Computed findings only: the assistant is not running.'})
            return
        block = findings.format_for_narration(facts, passages=results)
        ask = block
        if (data.get('question') or '').strip():
            ask = f"{block}\n\nThe scholar asks: {data['question'].strip()}"
        else:
            ask = f'{block}\n\nAnalyse what this evidence supports.'

        collected = []
        for piece in model.stream(prompts.ANALYZE_SYSTEM, ask,
                                  max_tokens=model.MAX_TOKENS_ANALYZE):
            collected.append(piece)
            yield _sse('chunk', {'text': piece})

        text = ''.join(collected)
        allowed = []
        for r in results:
            for side in ('source', 'target'):
                v = r.get(side)
                if isinstance(v, dict) and v.get('ref'):
                    allowed.append(v['ref'])
        _, removed = model.strip_unsupported_references(text, allowed)
        ok_numbers, invented = model.numbers_preserved(block, text, question)
        yield _sse('done', {'model_used': True,
                            'guardrails': {'references_removed': removed,
                                           'unsupported_numbers': invented,
                                           'clean': not removed and ok_numbers}})

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
