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
from flask import Blueprint, jsonify, request

from backend.logging_config import get_logger
from backend.assistant import findings, model, prompts, router

logger = get_logger('blueprints.assistant')

assistant_bp = Blueprint('assistant', __name__)


@assistant_bp.route('/assistant/status')
def status():
    return jsonify({
        'available': model.is_available(),
        'router_only': not model.is_available(),
        'note': ('The assistant explains the searches and reads results. It works from '
                 'the search engine output only, and it does not know classical '
                 'scholarship independently.'),
    })


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

    text = model.complete(prompts.GUIDE_SYSTEM, question,
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
    ok_numbers, invented = model.numbers_preserved(block, text)

    return jsonify({
        'facts': facts,
        'answer': text,
        'model_used': True,
        'guardrails': {'references_removed': removed,
                       'unsupported_numbers': invented,
                       'clean': not removed and ok_numbers},
    })
