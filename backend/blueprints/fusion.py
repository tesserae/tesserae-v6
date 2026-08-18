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

from flask import Blueprint, request, Response, jsonify
from flask_login import current_user
import os
import io
import re
import math
import json
import hashlib
from backend.utils import resolve_text_path, get_text_metadata
import time

from backend.logging_config import get_logger
from backend.services import get_user_location, log_search
import threading
from backend.cache import (get_cached_results, save_cached_results,
                           get_cache_key, ensure_cache_dir, CACHE_DIR)
from backend.concurrency_gate import SearchSlot
from backend.search_cancellation import SearchCancellation, SearchCancelled

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

    req_user_id = current_user.id if current_user and current_user.is_authenticated else None
    req_city, req_country, req_ip = get_user_location()

    def generate():
        slot = None
        cancellation = None
        try:
            cancellation = SearchCancellation(data.get('search_id'))
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
            freq_basis = data.get('freq_basis', 'corpus')  # corpus | meter | text_pair
            if freq_basis not in ('corpus', 'meter', 'text_pair'):
                freq_basis = 'corpus'
            if max_results <= 0:
                max_results = 5000  # enforce cap for browser payload size

            # Optional user-supplied per-channel weight overrides (Advanced UI).
            # Sanitized here (numbers only, known channels only, clamped) so the
            # rest of the pipeline can trust it. Empty dict => no overrides =>
            # default weight profile (behavior unchanged).
            from backend.fusion import (sanitize_channel_weights,
                                        sanitize_channel_keys,
                                        get_channels_for_language)
            channel_weights = sanitize_channel_weights(data.get('channel_weights'))

            # Optional per-channel ON/OFF switches (Advanced UI). The request
            # carries disabled_channels — the channels the user turned OFF. A
            # disabled channel is excluded from running entirely (a true off,
            # unlike weight=0 which still runs and can pull pairs in via
            # convergence). We turn that into enabled_channels, the KEEP-set
            # passed downstream: (channels available for this language) minus
            # (the ones the user disabled). Sending the OFF list (rather than
            # the keep list) means channels the UI never exposes — e.g.
            # `quotation` — stay on unless explicitly disabled, and a search
            # with nothing turned off is byte-identical to today.
            disabled_channels = sanitize_channel_keys(data.get('disabled_channels'))
            available_for_lang = set(get_channels_for_language(language))
            enabled_channels = None  # None => no restriction (default behavior)
            if disabled_channels:
                effective_disabled = disabled_channels & available_for_lang
                keep = available_for_lang - effective_disabled
                # Only a real restriction if it actually drops a channel that
                # would otherwise run AND leaves at least one running. If the
                # user turned everything off, fall back to the full set (guard
                # rail) rather than running an empty search.
                if effective_disabled and keep:
                    enabled_channels = keep

            if not source_id or not target_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Please select both source and target texts'})}\n\n"
                return

            # Path resolution
            source_path = resolve_text_path(_texts_dir, language, source_id)
            target_path = resolve_text_path(_texts_dir, language, target_id)

            if not source_path or not target_path:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Text files not found'})}\n\n"
                return

            # Check cache (keyed on fusion-specific settings)
            skip_cache = data.get('skip_cache', False)
            cache_settings = {
                'match_type': 'fusion',
                # The merged result shape changed when single-line window
                # duplicates began being removed.  Keep old cached fusion
                # results from being served after deployment.
                'result_version': 2,
                'mode': mode,
                'max_results': max_results,
                'language': language,
                'source_unit_type': source_unit_type,
                'target_unit_type': target_unit_type,
                'use_meter': use_meter,
                'freq_basis': freq_basis,
            }
            # Only add to the cache key when the user actually supplied custom
            # weights, so default-weight searches keep their existing cache
            # entries (and never read/write a custom-weight result by mistake).
            if channel_weights:
                cache_settings['channel_weights'] = channel_weights
            # Same for the on/off filter: only key on it when it meaningfully
            # restricts the channel set (enabled_channels is None otherwise).
            # Sorted list => stable, JSON-serializable, order-independent key.
            if enabled_channels:
                cache_settings['enabled_channels'] = sorted(enabled_channels)
            cached_results, cached_meta = (None, None) if skip_cache else \
                get_cached_results(source_id, target_id, language, cache_settings)
            if cached_results is not None:
                yield send_event("progress", {
                    "step": "Loading cached fusion results", "detail": ""
                })
                display = cached_results[:max_results] if max_results > 0 else cached_results
                meta = cached_meta or {}
                
                # Log the cached search
                log_search('fusion_search', language, source_id, target_id, None,
                           'fusion', len(cached_results), True, req_user_id, req_city, req_country, req_ip)
                           
                yield f"data: {json.dumps({'type': 'complete', 'results': display, 'total_matches': len(cached_results), 'source_lines': meta.get('source_lines', 0), 'target_lines': meta.get('target_lines', 0), 'elapsed_time': round(time.time() - start_time, 2), 'cached': True, 'fusion': True})}\n\n"
                return

            # Concurrency gate: wait for a slot before starting heavy work.
            # Yields "queued" SSE events while waiting so the frontend can
            # show the user a message instead of appearing frozen.
            slot = SearchSlot(cancellation=cancellation)
            try:
                for queued_event in slot.acquire():
                    cancellation.check()
                    yield send_event("queued", {
                        "step": "Search queued — server is busy",
                        "detail": queued_event.get("reason", ""),
                        "wait_time": queued_event.get("wait_time", 0),
                    })
            except TimeoutError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return
            cancellation.check()

            # Register metadata for Active Search Inspector
            slot.set_metadata({
                'source_id': source_id,
                'target_id': target_id,
                'language': language,
                'match_type': f'fusion ({mode})',
            })

            # Load text units
            yield send_event("progress", {
                "step": "Loading source text",
                "detail": source_id.replace('.tess', ''),
            })
            cancellation.check()
            source_units = _get_processed_units(source_id, language, source_unit_type, _text_processor)

            yield send_event("progress", {
                "step": "Loading target text",
                "detail": target_id.replace('.tess', ''),
            })
            cancellation.check()
            target_units = _get_processed_units(target_id, language, target_unit_type, _text_processor)
            cancellation.check()

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
                cancellation=cancellation,
                channel_weights=channel_weights,
                enabled_channels=enabled_channels,
            ):
                if slot.is_cancelled():
                    yield f"data: {json.dumps({'type': 'cancelled', 'message': 'Search terminated by administrator'})}\n\n"
                    return

                if event_type == "channel_start":
                    phase = evt_data['phase']
                    label = "window pass" if phase == "window" else f"{evt_data['step']}/{evt_data['total']} channels"
                    yield send_event("progress", {
                        "step": f"Running {evt_data['channel']} ({label})",
                        "detail": "",
                        "fusion_batch": {
                            "phase": phase,
                            "channel": evt_data['channel'],
                            "index": evt_data['step'],
                            "total": evt_data['total'],
                            "status": "running",
                        },
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
                        "fusion_batch": {
                            "phase": phase,
                            "channel": evt_data['channel'],
                            "index": evt_data['step'],
                            "total": evt_data['total'],
                            "status": "skipped" if evt_data.get('skipped') else "done",
                            "result_count": evt_data.get('count', 0),
                        },
                    })

                elif event_type == "intermediate":
                    yield f"data: {json.dumps({'type': 'intermediate', 'results': evt_data['results'], 'total_matches': evt_data['total_results'], 'channels_done': evt_data['channels_done'], 'channels_total': evt_data.get('channels_total', 9), 'phase': evt_data['phase'], 'elapsed': round(time.time() - start_time, 1)})}\n\n"

                elif event_type == "heartbeat":
                    # SSE comment: transmitted as bytes (keeps TCP alive) but
                    # silently ignored by all SSE parsers and our frontend
                    # TextDecoder reader.  Prevents proxy/browser read timeouts
                    # during slow channels (edit_distance, sound, semantic).
                    yield ": keep-alive\n\n"

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
            log_search('fusion_search', language, source_id, target_id, None,
                       'fusion', len(final_results), False, req_user_id, req_city, req_country, req_ip)

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

        except GeneratorExit:
            if cancellation is not None:
                cancellation.cancel()
            raise
        except SearchCancelled:
            return
        except Exception as e:
            logger.error(f"Fusion search error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if slot is not None:
                slot.release()
            if cancellation is not None:
                cancellation.close()

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
    })


# ---------------------------------------------------------------------------
# GET job/poll fusion search — for assistants that can only fetch a URL.
#
# The streaming POST /search-fusion above is ideal for browsers and dev tools,
# but many consumer AI assistants can only issue a GET and read the response.
# This exposes the same fusion search as a poll-able GET: it returns cached
# results immediately when available, otherwise it starts the search in a
# background thread and returns {status:"running"} — the caller polls the same
# URL until {status:"complete"}. Cross-worker de-duplication uses a marker file
# in the (shared, file-based) cache dir; the results cache is shared too, so a
# pair already run in the web app is available here instantly.
# ---------------------------------------------------------------------------

_FUSION_MARKER_TTL = 1800  # 30 min; a 'running' marker older than this is stale


def _poll_use_meter(source_id, target_id, language):
    """The web auto-enables meter when both texts are Latin poetry (via
    /api/check-meter -> is_suitable_for_meter). The GET poll must decide it the
    SAME way, or GET and POST land on different cache entries and report
    different parallel counts for the same pair."""
    try:
        from backend.metrical_scanner import is_suitable_for_meter
    except ImportError:
        from metrical_scanner import is_suitable_for_meter
    try:
        return bool(is_suitable_for_meter(source_id, target_id, language))
    except Exception:
        return False


def _default_fusion_cache_settings(language, max_results, use_meter=False):
    """cache_settings for a plain default fusion search — MUST match the default
    path of POST /search-fusion so GET and POST share the same cache entries.
    result_version and use_meter are part of that key: the stream stamps
    result_version=2 (single-line window dedup) and sets use_meter from the
    request (the web sends meter-on for poetry), so both must appear here too."""
    return {
        'match_type': 'fusion',
        'result_version': 2,
        'mode': 'merged',
        'max_results': max_results,
        'language': language,
        'source_unit_type': 'line',
        'target_unit_type': 'line',
        'use_meter': use_meter,
        'freq_basis': 'corpus',
    }


def _slim_fusion_result(r):
    s = r.get('source', {}) or {}
    t = r.get('target', {}) or {}
    channels = r.get('channels')
    score = round(r.get('fused_score', 0), 2)
    matched = r.get('matched_lemmas') or r.get('matched_words')
    # Emit BOTH the short poll-route names (score/matched) and the SSE field
    # names (fused_score/matched_words/matched_lemmas/channel_count) so a client
    # written against the streaming POST /search-fusion shape works unchanged
    # against this GET poll route. Results arrive pre-sorted by fused_score.
    return {
        'score': score,
        'fused_score': score,
        'channels': channels,
        'channel_count': len(channels) if channels else 0,
        'source': {'ref': s.get('ref'), 'text': s.get('text')},
        'target': {'ref': t.get('ref'), 'text': t.get('text')},
        'matched': matched,
        'matched_words': r.get('matched_words'),
        'matched_lemmas': r.get('matched_lemmas'),
    }


def _fusion_marker(job_key, kind):
    return os.path.join(CACHE_DIR, f"fusion_{kind}_{job_key}.marker")


def _fusion_status_path(job_key):
    return os.path.join(CACHE_DIR, f"fusion_status_{job_key}.json")


def _write_fusion_status(job_key, event_type, evt_data):
    """Persist the latest real progress from the fusion generator so the GET
    poll can report honest stage info. Only channel/intermediate events carry
    usable data. We record the phase (line -> window), the number of similarity
    signals (channels) completed vs. this phase's total, the current signal, and
    the running candidate count. We deliberately do NOT compute a time-percentage
    or ETA: channel costs are very unequal and the total step count isn't known
    until the run finishes, so any smooth percent would be fabricated."""
    status = None
    if event_type in ('channel_start', 'channel_done'):
        step = evt_data.get('step') or 0
        status = {
            'phase': evt_data.get('phase'),
            'current_signal': evt_data.get('channel'),
            'signals_done': max(0, step - (1 if event_type == 'channel_start' else 0)),
            'signals_total': evt_data.get('total'),
        }
    elif event_type == 'intermediate':
        status = {
            'phase': evt_data.get('phase'),
            'signals_done': evt_data.get('channels_done'),
            'signals_total': evt_data.get('channels_total'),
            'candidates_so_far': evt_data.get('total_results'),
        }
    if status is None:
        return
    status = {k: v for k, v in status.items() if v is not None}
    try:
        with open(_fusion_status_path(job_key), 'w', encoding='utf-8') as f:
            json.dump(status, f)
    except IOError:
        pass


def _read_fusion_status(job_key):
    try:
        with open(_fusion_status_path(job_key), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, ValueError):
        return None


def _clear_fusion_status(job_key):
    try:
        os.remove(_fusion_status_path(job_key))
    except OSError:
        pass


def _run_fusion_job(source_id, target_id, language, max_results, job_key):
    """Compute a default-settings fusion search and cache it (runs in a thread)."""
    slot = None
    cancellation = SearchCancellation()
    try:
        from backend.fusion import iter_fusion_search

        # Acquire concurrency slot and register metadata BEFORE loading text
        # units so the job is visible in the Active Search Inspector during the
        # entire computation, including unit processing which can take seconds.
        slot = SearchSlot()
        for _queued in slot.acquire():
            pass  # block until a concurrency slot frees up
        slot.set_metadata({
            'source_id': source_id,
            'target_id': target_id,
            'language': language,
            'match_type': 'fusion (poll)',
        })

        source_path = resolve_text_path(_texts_dir, language, source_id)
        target_path = resolve_text_path(_texts_dir, language, target_id)
        use_meter = _poll_use_meter(source_id, target_id, language)
        cache_settings = _default_fusion_cache_settings(language, max_results, use_meter)
        source_units = _get_processed_units(source_id, language, 'line', _text_processor)
        target_units = _get_processed_units(target_id, language, 'line', _text_processor)
        if not source_units or not target_units:
            raise ValueError('Could not process text units')
        final_results = []
        for event_type, evt_data in iter_fusion_search(
            source_units=source_units, target_units=target_units,
            matcher=_matcher, scorer=_scorer,
            source_id=source_id, target_id=target_id, language=language,
            mode='merged', max_results=max_results,
            source_path=source_path, target_path=target_path,
            user_settings={'use_meter': use_meter}, freq_basis='corpus',
            channel_weights={}, enabled_channels=None,
            cancellation=cancellation,
        ):
            if slot.is_cancelled():
                cancellation.cancel()
                logger.info("GET fusion job cancelled (%s x %s)", source_id, target_id)
                try:
                    with open(_fusion_marker(job_key, 'cancelled'), 'w', encoding='utf-8') as f:
                        f.write('Search terminated by administrator')
                except IOError:
                    pass
                # Slot is released by the finally block below.
                return

            # Record honest coarse progress for the GET poll (see _write_fusion_status).
            try:
                _write_fusion_status(job_key, event_type, evt_data)
            except (IOError, OSError) as e:
                logger.debug("Status write failed for fusion job %s: %s", job_key, e)
            if event_type == 'complete':
                final_results = evt_data['results']
        save_cached_results(
            source_id, target_id, language, cache_settings, final_results,
            {'source_lines': len(source_units), 'target_lines': len(target_units), 'mode': 'merged'},
        )
    except Exception as e:
        logger.error("GET fusion job failed (%s x %s): %s", source_id, target_id, e, exc_info=True)
        try:
            with open(_fusion_marker(job_key, 'error'), 'w', encoding='utf-8') as f:
                f.write(str(e)[:500])
        except IOError:
            pass
    finally:
        if slot is not None:
            slot.release()  # releases flock, deletes .lock + .cancel files
        try:
            os.remove(_fusion_marker(job_key, 'running'))
        except OSError:
            pass
        _clear_fusion_status(job_key)


@fusion_bp.route('/fusion-search', methods=['GET'])
def fusion_search_get():
    """Poll-able GET fusion search for URL-only assistants.

    GET /api/fusion-search?source=<id>&target=<id>&language=la

    Returns {status:"complete", parallels:[...]} when results are ready,
    otherwise starts the run and returns {status:"running"} — poll the same URL
    every ~20-30s until complete. Uses default fusion settings and shares the
    cache with the streaming POST endpoint, so any pair already run in the web
    app comes back instantly.
    """
    source_id = request.args.get('source')
    target_id = request.args.get('target')
    language = request.args.get('language', 'la')
    if not source_id or not target_id:
        return jsonify({'error': 'Provide source and target text ids (see /api/texts).'}), 400
    try:
        max_results = int(request.args.get('max', request.args.get('max_results', 5000)))
    except (TypeError, ValueError):
        max_results = 5000
    if max_results <= 0:
        max_results = 5000

    source_path = resolve_text_path(_texts_dir, language, source_id)
    target_path = resolve_text_path(_texts_dir, language, target_id)
    if not source_path or not target_path:
        return jsonify({'error': 'Text files not found for that source/target/language.'}), 404

    use_meter = _poll_use_meter(source_id, target_id, language)
    cache_settings = _default_fusion_cache_settings(language, max_results, use_meter)
    ensure_cache_dir()
    job_key = get_cache_key(source_id, target_id, language, cache_settings)

    cached_results, _meta = get_cached_results(source_id, target_id, language, cache_settings)
    if cached_results is not None:
        for kind in ('running', 'error', 'cancelled'):
            try:
                os.remove(_fusion_marker(job_key, kind))
            except OSError:
                pass
        _clear_fusion_status(job_key)

        # Optional server-side filters applied over the FULL result set (all
        # `max_results`) BEFORE the display cap, so single-poem / high-precision
        # questions aren't biased by the top-N slice. Ref filters match anywhere
        # in the (author-abbreviated) ref, so a trailing dot pins a number
        # exactly, e.g. source_ref_prefix="ecl. 1." matches "verg. ecl. 1.x"
        # but not "verg. ecl. 10.x".
        def _norm(s):
            return ' '.join((s or '').split()).lower()

        results = cached_results
        src_pfx = _norm(request.args.get('source_ref_prefix', ''))
        tgt_pfx = _norm(request.args.get('target_ref_prefix', ''))
        try:
            min_score = float(request.args.get('min_score')) if request.args.get('min_score') else None
        except (TypeError, ValueError):
            min_score = None
        if src_pfx:
            results = [r for r in results if src_pfx in _norm((r.get('source') or {}).get('ref'))]
        if tgt_pfx:
            results = [r for r in results if tgt_pfx in _norm((r.get('target') or {}).get('ref'))]
        if min_score is not None:
            results = [r for r in results if (r.get('fused_score') or 0) >= min_score]

        try:
            offset = max(0, int(request.args.get('offset', 0)))
        except (TypeError, ValueError):
            offset = 0
        try:
            limit = int(request.args.get('limit', 100))
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(limit, 500))
        page = results[offset:offset + limit]
        applied = {k: v for k, v in (('source_ref_prefix', src_pfx),
                                     ('target_ref_prefix', tgt_pfx),
                                     ('min_score', min_score)) if v}
        return jsonify({
            'status': 'complete', 'cached': True,
            'source': source_id, 'target': target_id, 'language': language,
            'count': len(results),            # matches after filters
            'total': len(cached_results),     # total computed before filters
            'offset': offset, 'limit': limit, 'showing': len(page),
            'filters': applied,
            'parallels': [_slim_fusion_result(r) for r in page],
        })

    # Admin cancellation: return a terminal cancelled status.
    # Unlike error markers (which are consumed once to allow retry), cancelled
    # markers persist until the client explicitly requests a retry via
    # ?retry=1, preventing polling clients from inadvertently restarting.
    cancel_marker = _fusion_marker(job_key, 'cancelled')
    if os.path.exists(cancel_marker):
        if request.args.get('retry') == '1':
            try:
                os.remove(cancel_marker)
            except OSError:
                pass
            # Fall through to start a new run below.
        else:
            return jsonify({
                'status': 'cancelled',
                'source': source_id, 'target': target_id,
                'message': 'This search was terminated by an administrator. '
                           'Add &retry=1 to this URL to start a fresh run.',
            })

    # Surface a prior failure once, then allow a retry on the next call.
    err_marker = _fusion_marker(job_key, 'error')
    if os.path.exists(err_marker):
        try:
            with open(err_marker, 'r', encoding='utf-8') as f:
                err = f.read()
        except IOError:
            err = 'unknown error'
        try:
            os.remove(err_marker)
        except OSError:
            pass
        return jsonify({'status': 'error', 'error': err,
                        'message': 'The fusion run failed; call again to retry.'}), 500

    # Already running (fresh marker)? Reuse the in-flight job — do NOT start a
    # second one — and report honest coarse progress.
    run_marker = _fusion_marker(job_key, 'running')
    if os.path.exists(run_marker) and (time.time() - os.path.getmtime(run_marker)) < _FUSION_MARKER_TTL:
        elapsed = int(time.time() - os.path.getmtime(run_marker))
        resp = {
            'status': 'running', 'source': source_id, 'target': target_id,
            'elapsed_seconds': elapsed,
            'message': 'Still computing on the Tesserae server (a full fusion search '
                       'typically takes ~2-3 minutes). It will finish and cache even if you '
                       'stop checking; call this same URL again in a minute or two.',
        }
        st = _read_fusion_status(job_key)
        if st:
            # Honest coarse progress. signals_done/signals_total = similarity
            # signals (channels) computed this phase — NOT a time percentage
            # (later signals are much slower). stage = 'line' then 'window'.
            for k in ('phase', 'current_signal', 'signals_done', 'signals_total', 'candidates_so_far'):
                if st.get(k) is not None:
                    resp['stage' if k == 'phase' else k] = st[k]
        return jsonify(resp)

    # Start a new background run.
    try:
        with open(run_marker, 'w', encoding='utf-8') as f:
            f.write('')
    except IOError:
        pass
    threading.Thread(
        target=_run_fusion_job,
        args=(source_id, target_id, language, max_results, job_key),
        daemon=True,
    ).start()
    return jsonify({'status': 'running', 'source': source_id, 'target': target_id,
                    'message': 'Fusion started. Poll this URL again in ~20-30s until status is '
                               '"complete". Large comparisons can take a few minutes; results are '
                               'cached afterward so repeats are instant.'})


@fusion_bp.route('/comparison-chart', methods=['GET'])
def comparison_chart():
    """Server-rendered distribution chart for a cached comparison — the same
    picture the web page draws (where the parallels fall in one text), returned
    as an image an AI agent can attach or embed in any medium.

    GET /api/comparison-chart?source=<id>&target=<id>&language=la
        &format=svg|png (default svg)  &side=source|target (default source)

    Reads the SHARED fusion cache, so a pair an agent just compared is instant.
    404s if the pair has not been computed yet (run the comparison first).
    """
    source_id = request.args.get('source')
    target_id = request.args.get('target')
    language = request.args.get('language', 'la')
    fmt = (request.args.get('format', 'svg') or 'svg').lower()
    side = (request.args.get('side', 'source') or 'source').lower()
    if side not in ('source', 'target'):
        side = 'source'
    if fmt not in ('svg', 'png'):
        fmt = 'svg'
    if not source_id or not target_id:
        return jsonify({'error': 'Provide source and target text ids (see /api/texts).'}), 400

    source_path = resolve_text_path(_texts_dir, language, source_id)
    target_path = resolve_text_path(_texts_dir, language, target_id)
    if not source_path or not target_path:
        return jsonify({'error': 'Text files not found for that source/target/language.'}), 404

    max_results = 5000
    use_meter = _poll_use_meter(source_id, target_id, language)
    cache_settings = _default_fusion_cache_settings(language, max_results, use_meter)
    cached_results, _meta = get_cached_results(source_id, target_id, language, cache_settings)
    if cached_results is None:
        return jsonify({'error': 'No cached comparison for this pair yet. Run the comparison '
                                 '(fusion-search or compare_texts) first, then request the chart.'}), 404

    meta = get_text_metadata(source_path if side == 'source' else target_path)
    work_label = meta.get('display_name') or meta.get('title') or (source_id if side == 'source' else target_id)

    # Distribution: parse each parallel's ref on `side` into (book, line) and bin
    # adaptively — a single book gets binned by line position, multiple books by
    # book — the same shape the site's in-comparison chart uses.
    def _ref_of(r):
        s = r.get(side) or {}
        return s.get('ref') or r.get(side + '_locus') or ''
    pts = []
    for r in cached_results:
        nums = [int(x) for x in re.findall(r'\d+', str(_ref_of(r)))]
        book = nums[0] if len(nums) >= 2 else None
        line = nums[-1] if nums else None
        pts.append((book, line))

    books = sorted({b for b, _ in pts if b is not None})
    if len(books) <= 1:
        lines = [l for _, l in pts if l is not None]
        if not lines:
            return jsonify({'error': 'Parallels carry no line references to chart.'}), 422
        max_line = max(lines)
        band = next((b for b in (10, 25, 50, 100, 200, 500, 1000) if math.ceil(max_line / b) <= 18), 1000)
        n_bands = max(1, math.ceil(max_line / band))
        counts = [0] * n_bands
        for _, l in pts:
            if l is not None:
                counts[min(n_bands - 1, (l - 1) // band)] += 1
        labels = [f"{i * band + 1}–{(i + 1) * band}" for i in range(n_bands)]
        xlabel = f"Line in {work_label}"
        title = f"Where the parallels fall in {work_label}"
    else:
        from collections import Counter
        c = Counter(b for b, _ in pts if b is not None)
        bs = sorted(c)
        counts = [c[b] for b in bs]
        labels = [f"Book {b}" for b in bs]
        xlabel = "Book"
        title = f"Parallels by book in {work_label}"

    try:
        from backend.inverted_index import get_corpus_version
        corpus_version = get_corpus_version(language)
    except Exception:
        corpus_version = None

    # Use the object-oriented Figure API (not pyplot) so this is thread-safe
    # under mod_wsgi — pyplot's global figure state would race across requests.
    from matplotlib.figure import Figure
    color = '#b91c1c' if side == 'source' else '#d97706'   # site red / amber
    fig = Figure(figsize=(7.2, 3.6), dpi=110)
    ax = fig.subplots()
    ax.bar(range(len(counts)), counts, color=color, edgecolor='white', linewidth=0.5)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Parallels', fontsize=9)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_title(title, fontsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.margins(x=0.01)
    stamp = 'Tesserae'
    if corpus_version:
        stamp += f" · corpus {corpus_version}"
    fig.text(0.99, 0.01, stamp, ha='right', va='bottom', fontsize=6, color='#9ca3af')
    fig.tight_layout()

    buf = io.BytesIO()
    if fmt == 'png':
        fig.savefig(buf, format='png', bbox_inches='tight')
        mime = 'image/png'
    else:
        fig.savefig(buf, format='svg', bbox_inches='tight')
        mime = 'image/svg+xml'
    buf.seek(0)
    return Response(buf.getvalue(), mimetype=mime,
                    headers={'Cache-Control': 'public, max-age=3600'})


_AUTHOR_DATES_CACHE = {}


def _author_dates(language):
    """{author_key: year} for a language, from author_dates.json (memoized).
    year is an int, negative for BCE; undated / sentinel entries are dropped."""
    if language in _AUTHOR_DATES_CACHE:
        return _AUTHOR_DATES_CACHE[language]
    out = {}
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'author_dates.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for k, v in (data.get(language) or {}).items():
            y = v.get('year')
            if isinstance(y, int) and y < 9999:
                out[k.lower()] = y
    except Exception:
        pass
    _AUTHOR_DATES_CACHE[language] = out
    return out


@fusion_bp.route('/comparison-history-chart', methods=['GET'])
def comparison_history_chart():
    """Server-rendered 'history strip' for a cached comparison: for each of the
    top shared parallels, WHERE ITS PHRASE RECURS across the corpus over time.
    One row per parallel, a shared date axis (BCE -> CE), a dot per corpus
    recurrence, with the two compared texts marked (source red, target amber,
    the rest of the tradition grey). Answers 'where does each of these echoes
    sit in literary history' in one image, instead of a chart per parallel.

    GET /api/comparison-history-chart?source=<id>&target=<id>&language=la
        &format=svg|png (default svg)  &top=<N up to 15> (default 10)
    Reads the SHARED fusion cache; 404 if the pair has not been computed yet.
    Result image is cached, so repeat requests are instant.
    """
    source_id = request.args.get('source')
    target_id = request.args.get('target')
    language = request.args.get('language', 'la')
    fmt = (request.args.get('format', 'svg') or 'svg').lower()
    if fmt not in ('svg', 'png'):
        fmt = 'svg'
    mime = 'image/png' if fmt == 'png' else 'image/svg+xml'
    try:
        top = int(request.args.get('top', 10))
    except (TypeError, ValueError):
        top = 10
    top = max(1, min(top, 15))
    if not source_id or not target_id:
        return jsonify({'error': 'Provide source and target text ids (see /api/texts).'}), 400
    if not (resolve_text_path(_texts_dir, language, source_id) and
            resolve_text_path(_texts_dir, language, target_id)):
        return jsonify({'error': 'Text files not found for that source/target/language.'}), 404

    try:
        from backend.inverted_index import get_corpus_version
        corpus_version = get_corpus_version(language)
    except Exception:
        corpus_version = None

    # Image cache: the per-parallel corpus lookups are the expensive part, so
    # cache the finished image keyed on the pair + top + format + corpus stamp.
    cache_dir = os.path.join(CACHE_DIR, 'history_charts')
    ck = hashlib.md5(f"{source_id}|{target_id}|{language}|{top}|{fmt}|{corpus_version}".encode()).hexdigest()  # nosec B324
    cpath = os.path.join(cache_dir, f"{ck}.{fmt}")
    if os.path.exists(cpath):
        with open(cpath, 'rb') as f:
            return Response(f.read(), mimetype=mime,
                            headers={'Cache-Control': 'public, max-age=3600'})

    use_meter = _poll_use_meter(source_id, target_id, language)
    cache_settings = _default_fusion_cache_settings(language, 5000, use_meter)
    cached_results, _meta = get_cached_results(source_id, target_id, language, cache_settings)
    if cached_results is None:
        return jsonify({'error': 'No cached comparison yet. Run the comparison '
                                 '(fusion-search or compare_texts) first, then request the chart.'}), 404

    from backend.inverted_index import find_co_occurring_lemmas
    from backend.matcher import (DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS,
                                 DEFAULT_ENGLISH_STOP_WORDS)
    from backend.blueprints.hapax import get_document_frequencies_batch
    stops = {'la': DEFAULT_LATIN_STOP_WORDS, 'grc': DEFAULT_GREEK_STOP_WORDS,
             'en': DEFAULT_ENGLISH_STOP_WORDS}.get(language, set())
    dates = _author_dates(language)
    src_norm = source_id.replace('.tess', '').lower()
    tgt_norm = target_id.replace('.tess', '').lower()
    # A phrase in more than this many corpus loci is a commonplace, not a
    # distinctive echo worth tracing — skip it (and it keeps each row legible).
    COMMONPLACE_CAP = 400

    def _content_lemmas(r):
        seen, uniq = set(), []
        for l in (r.get('matched_lemmas') or []):
            s = str(l)
            if s and s.lower() not in stops and s.lower() not in seen \
                    and re.match(r'^[^\W\d_]+$', s, re.UNICODE):
                seen.add(s.lower())
                uniq.append(s)
        return uniq

    scored = sorted(cached_results, key=lambda r: (r.get('fused_score') or r.get('score') or 0), reverse=True)
    rows = []
    for r in scored:
        if len(rows) >= top:
            break
        lems = _content_lemmas(r)
        if len(lems) < 2:
            continue
        # Query on the two RAREST shared words (most distinctive), which is both
        # faster and a truer phrase than the full lemma set. Forms absent from the
        # doc-freq table sort last, so real headwords are preferred.
        try:
            dfs = get_document_frequencies_batch(set(lems), language) or {}
        except Exception:
            dfs = {}
        pick = sorted(lems, key=lambda l: dfs.get(l) if dfs.get(l) is not None else 10 ** 9)[:2]
        try:
            matches = find_co_occurring_lemmas(pick, language, min_matches=2)
        except Exception:
            continue
        if not (2 <= len(matches) <= COMMONPLACE_CAP):
            continue
        years, src_years, tgt_years = [], [], []
        for m in matches:
            filename = m[0]
            y = dates.get(filename.split('.')[0].lower())
            if y is None:
                continue
            years.append(y)
            fn = filename.replace('.tess', '').lower()
            if fn == src_norm:
                src_years.append(y)
            elif fn == tgt_norm:
                tgt_years.append(y)
        if years:
            rows.append({'label': ' '.join(pick), 'years': years,
                         'src_years': src_years, 'tgt_years': tgt_years})

    if not rows:
        return jsonify({'error': 'No datable corpus recurrences to chart for the top parallels.'}), 422

    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter
    from matplotlib.lines import Line2D
    n = len(rows)
    fig = Figure(figsize=(8.6, max(2.6, 0.42 * n + 1.2)), dpi=110)
    ax = fig.subplots()
    for i, row in enumerate(rows):
        yy = n - 1 - i  # strongest parallel on top
        ax.scatter(row['years'], [yy] * len(row['years']), s=10, color='#9ca3af',
                   alpha=0.5, edgecolors='none', zorder=2)
        if row['tgt_years']:
            ax.scatter(row['tgt_years'], [yy] * len(row['tgt_years']), s=36, color='#d97706',
                       edgecolors='white', linewidth=0.4, zorder=4)
        if row['src_years']:
            ax.scatter(row['src_years'], [yy] * len(row['src_years']), s=36, color='#b91c1c',
                       edgecolors='white', linewidth=0.4, zorder=5)
    ax.set_yticks(range(n))
    ax.set_yticklabels([rows[n - 1 - j]['label'] for j in range(n)], fontsize=8)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlabel('Date (negative years are BCE)', fontsize=9)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _p=None: f"{int(-x)} BCE" if x < 0 else f"{int(x)} CE"))
    ax.set_title('Where these shared phrases recur across the corpus', fontsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', color='#f3f4f6', zorder=0)
    handles = [Line2D([0], [0], marker='o', color='w', markerfacecolor='#b91c1c', markersize=6, label='in the source'),
               Line2D([0], [0], marker='o', color='w', markerfacecolor='#d97706', markersize=6, label='in the target'),
               Line2D([0], [0], marker='o', color='w', markerfacecolor='#9ca3af', markersize=6, label='elsewhere in the corpus')]
    ax.legend(handles=handles, fontsize=7, loc='lower right', frameon=False)
    stamp = 'Tesserae' + (f" · corpus {corpus_version}" if corpus_version else '')
    fig.text(0.99, 0.005, stamp, ha='right', va='bottom', fontsize=6, color='#9ca3af')
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format=('png' if fmt == 'png' else 'svg'), bbox_inches='tight')
    data = buf.getvalue()
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cpath, 'wb') as f:
            f.write(data)
    except OSError:
        pass
    return Response(data, mimetype=mime, headers={'Cache-Control': 'public, max-age=3600'})


@fusion_bp.route('/fusion-default-weights', methods=['GET'])
def fusion_default_weights():
    """Return the default per-channel fusion weights for a language.

    Used by the Advanced "Channel weights" UI to pre-fill its inputs with the
    optimized defaults, and to know what "Reset to defaults" restores. Read-only
    and side-effect-free; does not affect any search.

    Query params:
        language — la (default) | grc | en | cop | ...

    Response: {"language": "la", "weights": {"lemma": 2.0, ...},
               "min": 0.0, "max": 20.0}

    Only channels that actually run for this language are returned (via
    get_channels_for_language), so the Advanced panel shows exactly the
    knobs that apply to the search — e.g. no syntax/dictionary for English.
    """
    from backend.fusion import (get_weight_profile, get_channels_for_language,
                                USER_WEIGHT_MIN, USER_WEIGHT_MAX)
    language = request.args.get('language', 'la')
    available = set(get_channels_for_language(language))
    weights = {ch: w for ch, w in get_weight_profile(language=language).items()
               if ch in available}
    return {
        'language': language,
        'weights': weights,
        'min': USER_WEIGHT_MIN,
        'max': USER_WEIGHT_MAX,
    }
