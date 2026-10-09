"""Secondary scholarship for a passage: the Reader's Scholarship tab and the
connector's find_scholarship / get_commentary tools.

    GET /api/scholarship?work=&ref_start=&ref_end=[&work2=&ref2_start=&ref2_end=]
        articles, chapters and books from the open metadata services, ranked
        (band 1 cites both passages, 2 both works, 3 one passage), each with
        DOI and any legal open copy; plus the site's own commentaries at the
        span. The reader's library link is built client-side from a setting.
    GET /api/scholarship/commentary?work=&ref_start=&ref_end=
        the public-domain commentaries' notes at the span.
    POST /api/scholarship/translate  {work, ref, text, commentator, language}
        a machine translation of one note the site already holds at that
        work and ref, by the local model, marked as such; cached, so a note
        is translated once. `text` must match that note's own text exactly
        (checked against what commentary_at returns): the route translates
        notes the site holds, never arbitrary client-supplied text.
"""
import hashlib
import json
import os
import time

import requests
from flask import Blueprint, jsonify, request

from backend import scholarship as S
from backend.work_names import base_work
from backend.logging_config import get_logger

logger = get_logger('scholarship')
scholarship_bp = Blueprint('scholarship', __name__)

LLM_URL = os.environ.get('TESSERAE_LOCAL_LLM', 'http://127.0.0.1:8081/v1/chat/completions')
TRANSLATION_DISCLAIMER = 'Machine translation by a local model, unreviewed.'
LANGUAGE_NAMES = {'la': 'Latin', 'grc': 'Greek', 'he': 'Hebrew', 'ar': 'Arabic', 'fa': 'Persian',
                  'ur': 'Urdu', 'cop': 'Coptic', 'en': 'English', 'de': 'German', 'fr': 'French', 'it': 'Italian'}
_XLAT_DIR = os.path.join(S.CACHE_DIR, 'translations')


def _args():
    a = request.args
    return {k: (a.get(k) or '').strip() or None for k in ('work', 'ref_start', 'ref_end', 'work2', 'ref2_start', 'ref2_end', 'quote')}


@scholarship_bp.route('/scholarship')
def scholarship():
    p = _args()
    if not p['work'] or not p['ref_start']:
        return jsonify({'error': 'work and ref_start are required', 'results': []})
    try:
        limit = max(1, min(50, int(request.args.get('limit') or 20)))
    except ValueError:
        limit = 20
    out = S.find(p['work'], p['ref_start'], p['ref_end'], p['work2'], p['ref2_start'], p['ref2_end'], limit=limit, quote=p['quote'])
    out['commentary'] = S.commentary_at(p['work'], p['ref_start'], p['ref_end'])
    if p['work2'] and p['ref2_start']:
        out['commentary2'] = S.commentary_at(p['work2'], p['ref2_start'], p['ref2_end'])
    return jsonify(out)


@scholarship_bp.route('/scholarship/commentary')
def commentary():
    p = _args()
    if not p['work'] or not p['ref_start']:
        return jsonify({'error': 'work and ref_start are required', 'commentary': []})
    return jsonify({'work': p['work'], 'ref_start': p['ref_start'], 'ref_end': p['ref_end'],
                    'commentary': S.commentary_at(p['work'], p['ref_start'], p['ref_end'])})


@scholarship_bp.route('/scholarship/sources')
def sources():
    """Every commentary held, grouped by commentator, with edition, source
    and licence, for the credits page: what the site shows must be credited
    where it came from.

    `languages` is additive: the distinct languages those commentaries
    cover, so the Reader's Scholarship tab can offer itself only where
    there is something to show, derived from data rather than a hard-coded
    list."""
    rows = S.commentary_sources()
    # The languages of the WORKS commented on, not the language a commentary
    # is written in (Leaf's English notes are on the Greek Iliad). Scripture
    # keys (bible.*) count for every language that holds a Bible version.
    texts_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'texts')
    work_lang = {}
    try:
        for lang in os.listdir(texts_root):
            d = os.path.join(texts_root, lang)
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if fn.endswith('.tess'):
                    work_lang.setdefault(base_work(fn[:-5]), set()).add(lang)
    except OSError:
        pass
    langs_present = set(os.listdir(texts_root)) if os.path.isdir(texts_root) else set()
    bible_langs = {'he', 'grc', 'cop', 'en', 'la'} & langs_present
    languages = set()
    for row in rows:
        for w in row.get('works') or []:
            if str(w).startswith('bible.'):
                languages.update(bible_langs)
            languages.update(work_lang.get(w, ()))
    languages = sorted(languages)
    return jsonify({'commentaries': rows, 'languages': languages})


def _held_note(work, ref, text, commentator=None):
    """The held commentary entry (its own commentator and language) for a
    note at this work and ref whose text exactly matches `text`, or None.

    This is the route's only access check: it never translates text the
    caller supplies on its own, only a note commentary_at() already serves
    for that span, so the local model is never asked to translate arbitrary
    text a request happens to send it."""
    if not work or not ref or not text:
        return None
    for entry in S.commentary_at(work, ref, ref):
        if commentator and (entry.get('commentator') or '').strip().lower() != commentator.strip().lower():
            continue
        for note in entry.get('notes') or []:
            if (note.get('text') or '').strip() == text:
                return {'commentator': entry.get('commentator'), 'language': entry.get('language')}
    return None


@scholarship_bp.route('/scholarship/translate', methods=['POST'])
def translate():
    d = request.get_json(silent=True) or {}
    work = (d.get('work') or '').strip()
    ref = (d.get('ref') or '').strip()
    text = (d.get('text') or '').strip()
    commentator = (d.get('commentator') or '').strip()
    if not work or not ref or not text:
        return jsonify({'available': False, 'reason': 'work, ref and text are required'}), 400
    if len(text) > 4000:
        text = text[:4000]
    held = _held_note(work, ref, text, commentator)
    if held is None:
        return jsonify({'available': False,
                        'reason': 'That text is not one of the notes held for this work and ref.'}), 400
    who = commentator or held.get('commentator') or 'the commentator'
    os.makedirs(_XLAT_DIR, exist_ok=True)
    key = hashlib.md5((work + '|' + ref + '|' + text).encode('utf-8')).hexdigest()  # nosec B324
    path = os.path.join(_XLAT_DIR, key + '.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            return jsonify(json.load(fh))
    # One user message, instruction then text: tried as a system message
    # first, and the local model echoed the original back instead of
    # translating it; a single user message gets a clean translation.
    if len(text) > 1500:
        text = text[:1500]
    lang_code = (d.get('language') or held.get('language') or '').strip().lower()
    lang = LANGUAGE_NAMES.get(lang_code) or 'original'
    label = 'Note' if lang == 'original' else lang
    prompt = (f'Translate the following {"" if lang == "original" else lang + " "}note by {who}, a commentator on '
              'the passage cited, into plain English. Output only the English translation, nothing else; do not '
              f'repeat the {lang}. Keep the word or phrase the note comments on in quotation marks at the start.'
              f'\n\n{label}:\n' + text + '\n\nEnglish:')
    try:
        r = requests.post(LLM_URL, json={'model': 'qwen3', 'temperature': 0, 'max_tokens': 500,
                                         'messages': [{'role': 'user', 'content': prompt}]}, timeout=60)
        r.raise_for_status()
        english = r.json()['choices'][0]['message']['content'].strip()
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.warning('note translation failed: %s', e)
        return jsonify({'available': False, 'reason': 'The local translation model did not answer.'})
    out = {'available': True, 'text': english, 'disclaimer': TRANSLATION_DISCLAIMER, 'made': time.strftime('%Y-%m-%d')}
    try:
        tmp = f'{path}.{os.getpid()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass
    return jsonify(out)
