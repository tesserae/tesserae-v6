"""
Tesserae V6 - Corpus Blueprint
Routes for corpus and text management
"""
from flask import Blueprint, jsonify, request
import os
import re
import json
import threading
from pathlib import Path

from backend.logging_config import get_logger
from backend.utils import (
    get_text_metadata,
    build_text_hierarchy,
    safe_listdir,
    enrich_metadata_with_author_dates,
    normalize_author_date_key,
    load_provenance,
    resolve_text_path,
    apply_text_list_filters,
    infer_coptic_dialect,
)
from backend.frequency_cache import get_corpus_frequencies, recalculate_language_frequencies
from backend.work_names import base_work
import backend.restricted_texts as restricted_texts

logger = get_logger('corpus')

AUTHOR_DATES_FILE = Path(__file__).parent.parent / "author_dates.json"
TEXT_SOURCES_FILE = Path(__file__).parent.parent / "text_sources.json"
TEXT_CREDITS_PAGE_SIZES = {25, 50, 100, 500}

_author_dates_cache = None
_author_dates_mtime = None

def get_author_dates():
    """Load and cache author dates."""
    global _author_dates_cache, _author_dates_mtime
    current_mtime = AUTHOR_DATES_FILE.stat().st_mtime if AUTHOR_DATES_FILE.exists() else None
    if _author_dates_cache is None or _author_dates_mtime != current_mtime:
        if AUTHOR_DATES_FILE.exists():
            with open(AUTHOR_DATES_FILE, 'r', encoding='utf-8') as f:
                _author_dates_cache = json.load(f)
        else:
            _author_dates_cache = {}
        _author_dates_mtime = current_mtime
    return _author_dates_cache


# Per worker process, not shared across mod_wsgi processes: each one parses the
# file once, then again only when its (path, mtime_ns, size) changes -- e.g. the
# admin upload rewriting it. Callers must not mutate the returned list.
_text_sources_cache = (None, [])
_text_sources_lock = threading.Lock()

def get_text_sources():
    """Load text_sources.json, reparsing only when the file changes."""
    global _text_sources_cache
    try:
        st = TEXT_SOURCES_FILE.stat()
    except FileNotFoundError:
        logger.warning("text_sources.json not found at %s", TEXT_SOURCES_FILE)
        return []
    key = (str(TEXT_SOURCES_FILE), st.st_mtime_ns, st.st_size)
    if _text_sources_cache[0] == key:
        return _text_sources_cache[1]
    with _text_sources_lock:
        if _text_sources_cache[0] != key:
            # A parse error propagates (as before) and leaves the old key, so
            # the next request retries rather than serving stale data.
            with open(TEXT_SOURCES_FILE, 'r', encoding='utf-8') as f:
                _text_sources_cache = (key, json.load(f))
        return _text_sources_cache[1]


corpus_bp = Blueprint('corpus', __name__)

_texts_dir = None
_text_processor = None
_get_processed_units = None


def natural_sort_key(s):
    """Sort strings with embedded numbers in natural order"""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(s))]


# Orientation blurbs per work: what a text is, for readers who meet it here
# first. Curated in data/text_descriptions.json, keyed language -> base work
# id. Cached against the file's mtime so an edit shows up without a restart.
DESCRIPTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'text_descriptions.json')
_descriptions_cache = {'mtime': None, 'data': {}}


def load_descriptions():
    try:
        mtime = os.path.getmtime(DESCRIPTIONS_PATH)
    except OSError:
        return {}
    if _descriptions_cache['mtime'] != mtime:
        try:
            with open(DESCRIPTIONS_PATH, encoding='utf-8') as f:
                data = json.load(f)
            _descriptions_cache['data'] = {
                k: v for k, v in data.items() if not k.startswith('_')}
            _descriptions_cache['mtime'] = mtime
        except (OSError, ValueError):
            logger.warning('text_descriptions.json unreadable', exc_info=True)
            return _descriptions_cache['data']
    return _descriptions_cache['data']


def init_corpus_blueprint(texts_dir, text_processor, get_processed_units_fn):
    """Initialize blueprint with required dependencies"""
    global _texts_dir, _text_processor, _get_processed_units
    _texts_dir = texts_dir
    _text_processor = text_processor
    _get_processed_units = get_processed_units_fn


@corpus_bp.route('/texts')
def get_texts():
    """Get all texts for a language"""
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(_texts_dir, language)
    
    if not os.path.exists(lang_dir):
        return jsonify([])
    
    author_dates = get_author_dates().get(language, {})
    
    texts = []
    for filename in sorted(safe_listdir(lang_dir)):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            metadata['language'] = language
            enrich_metadata_with_author_dates(metadata, author_dates)
            # Coptic: expose the dialect (sahidic / bohairic) so a cross-dialect
            # comparison (which shares no vocabulary) is legible in the listing.
            if language == 'cop':
                metadata['dialect'] = infer_coptic_dialect(filename, metadata.get('author'))
            # Licensed for indexing and search only (data/restricted_texts.json):
            # the file sits on disk and behaves like any other text, but the
            # client must show its credit line wherever a passage of it appears.
            if restricted_texts.is_restricted(filename):
                metadata['restricted'] = True
                metadata['credit'] = restricted_texts.credit_for(filename)
            texts.append(metadata)

    texts.sort(key=lambda x: (x['author'], x['title']))

    # Optional server-side author filter / pagination / compaction (absent params
    # → full list, so the web app is unaffected).
    texts = apply_text_list_filters(texts, request.args)

    return jsonify(texts)


@corpus_bp.route('/authors')
def get_authors():
    """Get all authors with their works"""
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(_texts_dir, language)
    
    if not os.path.exists(lang_dir):
        return jsonify([])
    
    author_dates = get_author_dates().get(language, {})
    
    authors = {}
    for filename in safe_listdir(lang_dir):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            metadata['language'] = language
            enrich_metadata_with_author_dates(metadata, author_dates)
            author = metadata['author']
            if author not in authors:
                authors[author] = {'works': [], 'year': metadata.get('year'), 'era': metadata.get('era')}
            authors[author]['works'].append(metadata)
    
    result = []
    for author in sorted(authors.keys()):
        result.append({
            'name': author,
            'year': authors[author].get('year'),
            'era': authors[author].get('era'),
            'works': sorted(authors[author]['works'], key=lambda x: natural_sort_key(x['title']))
        })
    
    return jsonify(result)


@corpus_bp.route('/corpus-status')
def get_corpus_status():
    """Get corpus expansion status and history."""
    import os
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    status_file = os.path.join(backend_dir, "corpus_status.json")
    if os.path.exists(status_file):
        with open(status_file, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Status file not found', 'path': status_file})


@corpus_bp.route('/provenance')
def get_provenance():
    """Get provenance information for texts."""
    text_id = request.args.get('text_id')
    
    provenance = load_provenance()
    
    if text_id:
        text_info = provenance.get('texts', {}).get(text_id)
        if text_info:
            source_key = text_info.get('source', '')
            source_info = provenance.get('sources', {}).get(source_key, {})
            return jsonify({
                'text': text_info,
                'source': source_info
            })
        return jsonify({'text': None, 'source': None})
    
    return jsonify({
        'sources': provenance.get('sources', {}),
        'texts': provenance.get('texts', {}),
        'total_tracked': len(provenance.get('texts', {}))
    })


def _work_facts(language, work, restricted):
    """Author/date/era/kind facts, and the edition's print and digital
    source, for the Reader's About panel -- one additive field on this
    lookup rather than a second route, since the client already calls this
    one for the orientation blurb. Matches against text_sources.json the
    same way the Sources page itself keys an entry (lowercased author +
    work display strings; there is no id the two files share). Returns
    None when the file cannot be read, so the caller can leave the key off
    rather than send a mostly-empty object.
    """
    if not _texts_dir:
        return None
    filename = work if str(work).endswith('.tess') else f'{work}.tess'
    filepath = os.path.join(_texts_dir, language, filename)
    if not os.path.exists(filepath):
        return None
    metadata = get_text_metadata(filepath)
    author_dates = get_author_dates().get(language, {})

    author_key = metadata.get('author_key', '')
    normalized_author_key = normalize_author_date_key(author_key)
    work_key = base_work(metadata.get('work_key') or '')
    info = (
        (author_dates.get(f'{author_key}.{work_key}') if work_key else None)
        or author_dates.get(author_key)
        or author_dates.get(author_key.lower())
        or author_dates.get(normalized_author_key)
        or {}
    )
    enrich_metadata_with_author_dates(metadata, author_dates)

    facts = {
        'author': metadata.get('author'),
        'work': metadata.get('work'),
        'part': metadata.get('part'),
        'year': metadata.get('year'),
        'era': metadata.get('era'),
        'date_note': info.get('note'),
        'kind': metadata.get('text_type'),
    }

    # A restricted work's print/e-text sourcing is not public information
    # (see _restricted_credit_entries above); its credit line already came
    # back as the top-level `credit` field, so no edition lookup here.
    if not restricted:
        author = (metadata.get('author') or '').strip().lower()
        title = (metadata.get('work') or metadata.get('title') or '').strip().lower()
        if author and title:
            for entry in get_text_sources():
                if (entry.get('author') or '').strip().lower() == author \
                        and (entry.get('work') or '').strip().lower() == title:
                    facts['edition'] = {
                        'print_source': entry.get('print_source'),
                        'e_source': entry.get('e_source'),
                        'e_source_url': entry.get('e_source_url'),
                    }
                    break
    return facts


@corpus_bp.route('/text-descriptions')
def get_text_descriptions():
    """Orientation blurbs for a language's works, or one work's blurb -- also
    the Reader header's text-metadata lookup, so a restricted work's credit
    line is exposed here too (?language=la&work=x -> restricted, credit),
    and (for the About panel) the author/date/era/kind facts and edition --
    see _work_facts above.

    ?language=la           -> {"descriptions": {work_id: blurb, ...}}
    ?language=la&work=x    -> {"description": blurb or null, "facts": {...}}
    The work key is the base id: no language directory, no .tess, no .part.
    """
    language = request.args.get('language', 'la')
    by_lang = load_descriptions().get(language, {})
    work = request.args.get('work')
    if work:
        # was re.sub(r'\.part\.\d+$', ...), which left 215 part files with a
        # label after the number (pindar.odes.part.2.nemeans) uncollapsed, so
        # their work's description was never found.
        base = base_work(work)
        restricted = restricted_texts.is_restricted(base)
        result = {'description': by_lang.get(base)}
        if restricted:
            result['restricted'] = True
            result['credit'] = restricted_texts.credit_for(base)
        facts = _work_facts(language, work, restricted)
        if facts:
            result['facts'] = facts
        return jsonify(result)
    return jsonify({'descriptions': by_lang})


_LANGUAGES_WITH_TEXTS = ('la', 'grc', 'en', 'cop', 'he', 'it', 'gmh', 'fro')
# Development languages join the list only when TESSERAE_LANGUAGES opts them in
# (see backend/app.py, where their handlers register under the same rule).
try:
    from backend.served_languages import allowed_languages as _served_allowed
    _LANGUAGES_WITH_TEXTS = _LANGUAGES_WITH_TEXTS + tuple(
        c for c in ('fa', 'ur', 'ar') if c in (_served_allowed() or set()))
except ImportError:
    pass


def _restricted_credit_entries():
    """One credits-page entry per restricted work actually on this server,
    built from the file itself (author/title, the same source the corpus
    listing uses) rather than from text_sources.json, which never carries a
    restricted work's provenance -- its print/e-text sourcing is not public
    information the way the rest of the corpus's is. What the Sources page
    owes a restricted work instead is the fixed credit line and the licence
    words, which is what this entry carries in place of e_source/print_source.
    """
    entries = []
    seen_ids = set()
    for language in _LANGUAGES_WITH_TEXTS:
        files = restricted_texts.filenames(language, texts_root=_texts_dir)
        # One row per WORK, not per file: a multi-file work's parts would
        # otherwise repeat the same credit line once per book.
        files.sort(key=lambda f: ('.part.' in f, f))  # whole file, if any, first
        for filename in files:
            text_id = base_work(filename[:-len('.tess')] if filename.endswith('.tess') else filename)
            if text_id in seen_ids:
                continue
            seen_ids.add(text_id)
            metadata = get_text_metadata(os.path.join(_texts_dir, language, filename))
            entries.append({
                'author': metadata.get('author', ''),
                'work': metadata.get('work') or metadata.get('title', ''),
                'restricted': True,
                'credit': restricted_texts.credit_for(filename),
                'license': restricted_texts.license_for(filename),
                'e_source': None,
                'print_source': None,
            })
    return entries


SOURCES_CREDITS_FILE = Path(__file__).parent.parent.parent / "data" / "sources_credits.json"
SOURCES_CREDITS_REQUIRED = ('collection', 'name', 'url', 'licence_name')


@corpus_bp.route('/sources-credits')
def get_sources_credits():
    """The Sources and credits records for every collection, from
    data/sources_credits.json (one record per source; each import adds one)."""
    try:
        with open(SOURCES_CREDITS_FILE, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except (OSError, ValueError):
        logger.exception('sources_credits.json unreadable')
        return jsonify({'error': 'Sources list unavailable'}), 500
    return jsonify({'records': records, 'total': len(records)})


@corpus_bp.route('/text-credits')
def get_text_credits():
    """Get a filtered page of text credits from the static provenance data."""
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 50))
    except (TypeError, ValueError):
        return jsonify({'error': 'offset and limit must be integers'}), 400

    if offset < 0:
        return jsonify({'error': 'offset must be zero or greater'}), 400
    if limit not in TEXT_CREDITS_PAGE_SIZES:
        return jsonify({'error': 'limit must be one of 25, 50, 100, or 500'}), 400

    query = request.args.get('query', '').strip().casefold()
    sources = get_text_sources() + _restricted_credit_entries()  # new list; cache untouched

    if query:
        sources = [
            entry for entry in sources
            if query in entry.get('author', '').casefold()
            or query in entry.get('work', '').casefold()
        ]

    return jsonify({
        'entries': sources[offset:offset + limit],
        'total': len(sources),
        'offset': offset,
        'limit': limit,
    })


@corpus_bp.route('/texts/hierarchy')
def get_texts_hierarchy():
    """Get hierarchical text structure: Author -> Work -> Parts"""
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(_texts_dir, language)
    
    if not os.path.exists(lang_dir):
        return jsonify({'authors': []})
    
    author_dates = get_author_dates().get(language, {})
    
    texts = []
    for filename in safe_listdir(lang_dir):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            enrich_metadata_with_author_dates(metadata, author_dates)
            texts.append(metadata)
    
    hierarchy = build_text_hierarchy(texts)
    
    result = []
    for author_key in sorted(hierarchy.keys()):
        author_data = hierarchy[author_key]
        author_key_lower = author_key.lower()
        author_year = author_dates.get(author_key_lower, {}).get('year')
        author_era = author_dates.get(author_key_lower, {}).get('era')
        works = []
        for work_key in sorted(author_data['works'].keys(), key=natural_sort_key):
            work_data = author_data['works'][work_key]
            works.append({
                'work_key': work_key,
                'work': work_data['work'],
                'whole_text': work_data['whole_text'],
                'parts': work_data['parts']
            })
        result.append({
            'author_key': author_key,
            'author': author_data['author'],
            'year': author_year if author_year is not None else author_dates.get(normalize_author_date_key(author_key), {}).get('year'),
            'era': author_era or author_dates.get(normalize_author_date_key(author_key), {}).get('era'),
            'works': works
        })
    
    return jsonify({'authors': result})


@corpus_bp.route('/text/<path:text_id>')
def get_text_content(text_id):
    """Get content of a specific text"""
    language = request.args.get('language', 'la')
    unit_type = request.args.get('unit_type', 'line')
    
    filepath = resolve_text_path(_texts_dir, language, text_id)
    
    if not filepath:
        return jsonify({'error': 'Text not found'}), 404
    
    try:
        units = _get_processed_units(text_id, language, unit_type, _text_processor)
        metadata = get_text_metadata(filepath)
        
        return jsonify({
            'metadata': metadata,
            'units': units,
            'line_count': len(units)
        })
    except Exception as e:
        logger.error(f"Failed to get text content: {e}")
        return jsonify({'error': str(e)}), 500


# Which book file holds a line of a whole-file work (Reader, 2026-09-20).
# The Reader shows works held in books one book at a time. A link to the
# whole file with a line reference (a Similar Passages hit, a search result,
# the Similarity Map) has to open the book that holds that line, and the
# book number cannot be read off the reference: Alcuin's part 97 holds poems
# 97 to 101, Cicero's Verrines part 3 holds actio 2 book 2 (refs "2.2.x"),
# Hyperides' whole file tags lines "hyp. 1.1" while its parts say
# "hyp. speeches. 1.1". So the server looks the line up in the part files.
# Part files are read once per worker; the whole corpus of parts is small.
_book_refs_cache = {}
_TAG_RE = re.compile(r'^<+([^>]*)>')


def _ref_key(ref):
    """The locus of a reference, so that "hyp. 1.1" and "hyp. speeches. 1.1"
    compare equal: the last whitespace-separated token, lowercased."""
    ref = (ref or '').strip().lower()
    return ref.rsplit(None, 1)[-1] if ref else ''


def _book_files(language, base):
    """[(file name, set of refs, set of locus keys)] for the .part.N files."""
    key = (language, base)
    hit = _book_refs_cache.get(key)
    if hit is not None:
        return hit
    lang_dir = os.path.join(_texts_dir, language)
    out = []
    try:
        names = os.listdir(lang_dir)
    except OSError:
        names = []
    pat = re.compile(r'^' + re.escape(base) + r'\.part\.(\d+)(?:\.[^.]+)?\.tess$')
    numbered = []
    for name in names:
        m = pat.match(name)
        if m:
            numbered.append((int(m.group(1)), name))
    for _, name in sorted(numbered):
        refs, keys = set(), set()
        try:
            with open(os.path.join(lang_dir, name), encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    m = _TAG_RE.match(line)
                    if m:
                        refs.add(m.group(1).strip().lower())
                        keys.add(_ref_key(m.group(1)))
        except OSError:
            continue
        out.append((name, refs, keys))
    _book_refs_cache[key] = out
    return out


@corpus_bp.route('/text/<path:text_id>/book-for')
def get_book_for_line(text_id):
    """The book file of a whole-file work that holds a given line.

    Query: ref (the line reference, optional). Returns {"file": name} when a
    book holds the line, {"file": first book} when the work has books but the
    line was not found (or no ref was given), and {"file": null} when the
    work has no book files."""
    language = request.args.get('language', 'la')
    base = re.sub(r'\.tess$', '', text_id)
    if re.search(r'\.part\.\d+', base):
        return jsonify({'file': None, 'found': False})
    books = _book_files(language, base)
    if not books:
        return jsonify({'file': None, 'found': False})
    ref = (request.args.get('ref') or '').strip().lower()
    if ref:
        # The whole reference first: in a Bible or in Suetonius every book
        # starts at "1.1", so the locus alone would name the wrong book.
        for name, refs, _ in books:
            if ref in refs:
                return jsonify({'file': name, 'found': True})
        # Then the locus alone, for a whole file that tags its lines with a
        # different prefix from its parts (Hyperides).
        want = _ref_key(ref)
        for name, _, keys in books:
            if want in keys:
                return jsonify({'file': name, 'found': True})
    return jsonify({'file': books[0][0], 'found': False})


@corpus_bp.route('/frequencies/<language>')
def get_frequencies(language):
    """Get corpus frequencies for a language"""
    freq_data = get_corpus_frequencies(language, _text_processor)
    
    if not freq_data:
        return jsonify({'error': 'No frequency data available'}), 404
    
    top_n = request.args.get('top', type=int, default=100)
    frequencies = freq_data.get('frequencies', {})
    
    sorted_freqs = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    return jsonify({
        'language': language,
        'total_words': freq_data.get('total_words', 0),
        'unique_words': len(frequencies),
        'top_words': [{'word': w, 'count': c} for w, c in sorted_freqs]
    })


@corpus_bp.route('/frequencies/recalculate', methods=['POST'])
def recalculate_frequencies():
    """Recalculate corpus frequencies for a language"""
    data = request.get_json() or {}
    language = data.get('language', 'la')
    
    try:
        result = recalculate_language_frequencies(language, _text_processor)
        return jsonify({
            'success': True,
            'language': language,
            'total_words': result.get('total_words', 0) if result else 0
        })
    except Exception as e:
        logger.error(f"Failed to recalculate frequencies: {e}")
        return jsonify({'error': str(e)}), 500


@corpus_bp.route('/texts/preview', methods=['POST'])
def preview_text():
    """Preview text parsing before adding to corpus"""
    data = request.get_json() or {}
    content = data.get('content', '')
    language = data.get('language', 'la')
    author = data.get('author', '')
    work = data.get('work', '')
    
    if not content:
        return jsonify({'error': 'Content required'}), 400
    
    try:
        lines = content.strip().split('\n')
        preview_lines = []
        
        safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower()) if author else 'author'
        safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower()) if work else 'work'
        
        for i, line in enumerate(lines[:20], 1):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('<') and '>' in line:
                tag_end = line.index('>') + 1
                tag = line[:tag_end]
                text = line[tag_end:].strip()
            else:
                tag = f"<{safe_author}.{safe_work}.{i}>"
                text = line
            
            preview_lines.append({
                'line_num': i,
                'tag': tag,
                'text': text,
                'formatted': f"{tag} {text}"
            })
        
        return jsonify({
            'preview': preview_lines,
            'total_lines': len(lines),
            'suggested_filename': f"{safe_author}.{safe_work}.tess"
        })
    except Exception as e:
        logger.error(f"Failed to preview text: {e}")
        return jsonify({'error': str(e)}), 500


@corpus_bp.route('/texts/add', methods=['POST'])
def add_text():
    """Add a new text to the corpus (admin only)"""
    from backend.blueprints.admin import check_admin_auth
    
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    content = data.get('content', '')
    language = data.get('language', 'la')
    author = data.get('author', '')
    work = data.get('work', '')
    
    if not content or not author or not work:
        return jsonify({'error': 'Content, author, and work are required'}), 400
    
    try:
        safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower())
        safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower())
        filename = f"{safe_author}.{safe_work}.tess"
        
        lang_dir = os.path.join(_texts_dir, language)
        os.makedirs(lang_dir, exist_ok=True)
        filepath = os.path.join(lang_dir, filename)
        
        if os.path.exists(filepath):
            return jsonify({'error': f'Text "{author} - {work}" already exists'}), 409
        
        lines = content.strip().split('\n')
        formatted_lines = []
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            if line.startswith('<') and '>' in line:
                formatted_lines.append(line)
            else:
                tag = f"<{safe_author}.{safe_work}.{i}>"
                formatted_lines.append(f"{tag} {line}")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(formatted_lines))
        
        recalculate_language_frequencies(language, _text_processor)
        
        from backend.inverted_index import index_single_text
        index_result = index_single_text(filepath, language, _text_processor)
        
        # Clear search results cache for this language
        from backend.cache import clear_cache_for_language
        clear_cache_for_language(language)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'lines': len(formatted_lines),
            'indexed': index_result.get('status') == 'indexed' if index_result else False
        })
    except Exception as e:
        logger.error(f"Failed to add text: {e}")
        return jsonify({'error': str(e)}), 500
