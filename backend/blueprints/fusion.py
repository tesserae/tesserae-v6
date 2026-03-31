"""
Tesserae V6 — Fusion Search Blueprint

Exposes multi-channel weighted fusion search as a streaming API endpoint.
Uses the core logic in backend/fusion.py, which was ported from the
evaluation scripts (Config D: 90.7% recall on benchmark pairs).

Endpoint:
    POST /api/search-fusion  — SSE stream with progressive results

Progressive streaming: instead of waiting for all channels to complete,
the endpoint yields intermediate fused results after each channel finishes.
Fast channels (lemma, exact) run first, so users see results within seconds.
"""

from flask import Blueprint, request, Response
from flask_login import current_user
import os
import json
import time

from backend.logging_config import get_logger
from backend.services import get_user_location, log_search
from backend.cache import get_cached_results, save_cached_results
from backend.concurrency_gate import SearchSlot

logger = get_logger('fusion')

fusion_bp = Blueprint('fusion', __name__)

# Module-level references (injected via init_fusion_blueprint)
_matcher = None
_scorer = None
_text_processor = None
_texts_dir = None
_get_processed_units = None


def init_fusion_blueprint(matcher, scorer, text_processor, texts_dir,
                          get_processed_units_fn):
    """Initialize blueprint with required dependencies."""
    global _matcher, _scorer, _text_processor, _texts_dir, _get_processed_units
    _matcher = matcher
    _scorer = scorer
    _text_processor = text_processor
    _texts_dir = texts_dir
    _get_processed_units = get_processed_units_fn


@fusion_bp.route('/search-fusion', methods=['POST'])
def search_fusion_stream():
    """Multi-channel weighted fusion search with progressive SSE streaming.

    SSE event types:
        progress     — status text for the loading spinner
        intermediate — partial fused results (after each channel completes)
        complete     — final merged results
        error        — search failure
    """
    data = request.get_json()

    def generate():
        slot = None
        try:
            from backend.fusion import iter_fusion_search

            start_time = time.time()

            def send_event(event_type, payload):
                payload["elapsed"] = round(time.time() - start_time, 1)
                return f"data: {json.dumps({'type': event_type, **payload})}\n\n"

            yield send_event("progress", {
                "step": "Initializing fusion search", "detail": ""
            })

            source_id = data.get('source')
            target_id = data.get('target')
            language = data.get('language', 'la')
            mode = data.get('mode', 'merged')       # line | window | merged
            max_results = data.get('max_results', 5000)
            source_unit_type = data.get('source_unit_type', 'line')
            target_unit_type = data.get('target_unit_type', 'line')
            use_meter = data.get('use_meter', False)
            freq_basis = data.get('freq_basis', 'corpus')  # corpus | meter
            if freq_basis not in ('corpus', 'meter'):
                freq_basis = 'corpus'
            if max_results <= 0:
                max_results = 5000  # enforce cap for browser payload size

            if not source_id or not target_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Please select both source and target texts'})}\n\n"
                return

            lang_dir = os.path.join(_texts_dir, language)
            source_path = os.path.join(lang_dir, source_id)
            target_path = os.path.join(lang_dir, target_id)

            if not os.path.exists(source_path) or not os.path.exists(target_path):
                yield f"data: {json.dumps({'type': 'error', 'message': 'Text files not found'})}\n\n"
                return

            # Check cache (keyed on fusion-specific settings)
            skip_cache = data.get('skip_cache', False)
            cache_settings = {
                'match_type': 'fusion',
                'mode': mode,
                'max_results': max_results,
                'language': language,
                'source_unit_type': source_unit_type,
                'target_unit_type': target_unit_type,
                'use_meter': use_meter,
                'freq_basis': freq_basis,
            }
            cached_results, cached_meta = (None, None) if skip_cache else \
                get_cached_results(source_id, target_id, language, cache_settings)
            if cached_results is not None:
                yield send_event("progress", {
                    "step": "Loading cached fusion results", "detail": ""
                })
                display = cached_results[:max_results] if max_results > 0 else cached_results
                meta = cached_meta or {}
                yield f"data: {json.dumps({'type': 'complete', 'results': display, 'total_matches': len(cached_results), 'source_lines': meta.get('source_lines', 0), 'target_lines': meta.get('target_lines', 0), 'elapsed_time': round(time.time() - start_time, 2), 'cached': True, 'fusion': True})}\n\n"
                return

            # Concurrency gate: wait for a slot before starting heavy work.
            # Yields "queued" SSE events while waiting so the frontend can
            # show the user a message instead of appearing frozen.
            slot = SearchSlot()
            try:
                for queued_event in slot.acquire():
                    yield send_event("queued", {
                        "step": "Search queued — server is busy",
                        "detail": queued_event.get("reason", ""),
                        "wait_time": queued_event.get("wait_time", 0),
                    })
            except TimeoutError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return

            # Load text units
            yield send_event("progress", {
                "step": "Loading source text",
                "detail": source_id.replace('.tess', ''),
            })
            source_units = _get_processed_units(source_id, language, source_unit_type, _text_processor)

            yield send_event("progress", {
                "step": "Loading target text",
                "detail": target_id.replace('.tess', ''),
            })
            target_units = _get_processed_units(target_id, language, target_unit_type, _text_processor)

            if not source_units or not target_units:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Could not process text units'})}\n\n"
                return

            yield send_event("progress", {
                "step": "Starting fusion search",
                "detail": f"{len(source_units)} \u00d7 {len(target_units)} units, mode={mode}",
            })

            # Stream events from the generator — yields progress and
            # intermediate results as each channel completes
            final_results = []
            for event_type, evt_data in iter_fusion_search(
                source_units=source_units,
                target_units=target_units,
                matcher=_matcher,
                scorer=_scorer,
                source_id=source_id,
                target_id=target_id,
                language=language,
                mode=mode,
                max_results=max_results,
                source_path=source_path,
                target_path=target_path,
                user_settings={'use_meter': use_meter},
                freq_basis=freq_basis,
            ):
                if event_type == "channel_start":
                    phase = evt_data['phase']
                    label = "window pass" if phase == "window" else f"{evt_data['step']}/{evt_data['total']} channels"
                    yield send_event("progress", {
                        "step": f"Running {evt_data['channel']} ({label})",
                        "detail": "",
                    })

                elif event_type == "channel_done":
                    phase = evt_data['phase']
                    label = "window pass" if phase == "window" else f"{evt_data['step']}/{evt_data['total']} channels"
                    if evt_data.get('skipped'):
                        step_text = f"{evt_data['channel']} skipped for large search ({label})"
                    else:
                        step_text = f"{evt_data['channel']} done \u2014 {evt_data['count']} results ({label})"
                    yield send_event("progress", {
                        "step": step_text,
                        "detail": "",
                    })

                elif event_type == "intermediate":
                    yield f"data: {json.dumps({'type': 'intermediate', 'results': evt_data['results'], 'total_matches': evt_data['total_results'], 'channels_done': evt_data['channels_done'], 'channels_total': evt_data.get('channels_total', 9), 'phase': evt_data['phase'], 'elapsed': round(time.time() - start_time, 1)})}\n\n"

                elif event_type == "complete":
                    final_results = evt_data["results"]

            # Cache final results
            metadata = {
                'source_lines': len(source_units),
                'target_lines': len(target_units),
                'mode': mode,
            }
            save_cached_results(
                source_id, target_id, language, cache_settings,
                final_results, metadata
            )

            # Log the search
            user_id = (current_user.id
                       if current_user and current_user.is_authenticated
                       else None)
            city, country = get_user_location()
            log_search('fusion_search', language, source_id, target_id, None,
                       'fusion', len(final_results), False, user_id, city, country)

            elapsed_time = round(time.time() - start_time, 2)

            complete = {
                "type": "complete",
                "results": final_results,
                "total_matches": len(final_results),
                "source_lines": len(source_units),
                "target_lines": len(target_units),
                "elapsed_time": elapsed_time,
                "fusion": True,
                "mode": mode,
            }
            yield f"data: {json.dumps(complete)}\n\n"

        except Exception as e:
            logger.error(f"Fusion search error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if slot is not None:
                slot.release()

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
    })
