"""
Tesserae V6 - Text Processor

Core module for parsing .tess text files and performing linguistic analysis.
Supports Latin, Greek, and English texts.

Key Responsibilities:
    - Parse .tess format: Extract lines with CTS/TEI references
    - Tokenization: Split text into words, handling punctuation and enclitics
    - Lemmatization: Convert inflected forms to dictionary headwords
    - POS tagging: Part-of-speech annotation for feature matching
    - Unit generation: Create searchable units (lines or phrases)

Lemmatization Strategy:
    1. Primary: Static lookup tables from Universal Dependencies treebanks
       - Fast, consistent, covers most vocabulary
       - Latin: ~40k mappings, Greek: ~58k mappings
    2. Fallback: CLTK (Latin/Greek) or NLTK (English) when available
       - Handles novel words not in lookup tables

.tess File Format:
    Each line: <reference> text content
    Example: <vergil.aeneid.1.1> Arma virumque cano Troiae qui primus ab oris
    
    References can be CTS URNs or simple book.line notation.
"""

# =============================================================================
# IMPORTS
# =============================================================================
import re
import os
import json
import unicodedata
from backend.logging_config import get_logger

logger = get_logger('text_processor')


# =============================================================================
# LEMMA LOOKUP TABLES
# =============================================================================
# Pre-loaded dictionaries mapping surface forms to lemmas
# Built from Universal Dependencies Latin/Greek treebanks for accuracy
# Loaded lazily on first use to speed up server startup
LATIN_LEMMA_TABLE = None
GREEK_LEMMA_TABLE = None
LATIN_REVERSE_LEMMA = None
GREEK_REVERSE_LEMMA = None
_lemma_tables_loaded = False

# =============================================================================
# LANGUAGE HANDLER REGISTRY (for plugin languages like Coptic)
# =============================================================================
_LANGUAGE_HANDLERS = {}

def register_language_handler(code, handler):
    """Register a language handler for a given language code.
    Handler must provide: tokenize_and_lemmatize(text), lemmatize_word(word),
    split_into_phrases(text), ends_sentence(text).
    """
    _LANGUAGE_HANDLERS[code] = handler
    logger.info(f'Registered language handler: {code}')

def load_lemma_tables():
    """Load pre-computed lemma lookup tables from UD treebanks (lazy loading)"""
    global LATIN_LEMMA_TABLE, GREEK_LEMMA_TABLE, _lemma_tables_loaded
    global LATIN_REVERSE_LEMMA, GREEK_REVERSE_LEMMA
    
    if _lemma_tables_loaded:
        return
    
    LATIN_LEMMA_TABLE = {}
    GREEK_LEMMA_TABLE = {}
    LATIN_REVERSE_LEMMA = {}
    GREEK_REVERSE_LEMMA = {}
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    latin_path = os.path.join(base_dir, 'data', 'lemma_tables', 'latin_lemmas.json')
    greek_path = os.path.join(base_dir, 'data', 'lemma_tables', 'greek_lemmas.json')
    
    if os.path.exists(latin_path):
        try:
            with open(latin_path, 'r', encoding='utf-8') as f:
                LATIN_LEMMA_TABLE = json.load(f)
            for form, lemma in LATIN_LEMMA_TABLE.items():
                if lemma not in LATIN_REVERSE_LEMMA:
                    LATIN_REVERSE_LEMMA[lemma] = set()
                LATIN_REVERSE_LEMMA[lemma].add(form)
            logger.info(f"Loaded {len(LATIN_LEMMA_TABLE)} Latin lemma mappings from UD treebanks")
        except Exception as e:
            logger.error(f"Failed to load Latin lemma table: {e}")
    else:
        logger.warning(f"Latin lemma table not found at {latin_path}")
    
    if os.path.exists(greek_path):
        try:
            with open(greek_path, 'r', encoding='utf-8') as f:
                GREEK_LEMMA_TABLE = json.load(f)
            for form, lemma in GREEK_LEMMA_TABLE.items():
                if lemma not in GREEK_REVERSE_LEMMA:
                    GREEK_REVERSE_LEMMA[lemma] = set()
                GREEK_REVERSE_LEMMA[lemma].add(form)
            logger.info(f"Loaded {len(GREEK_LEMMA_TABLE)} Greek lemma mappings from UD treebanks")
        except Exception as e:
            logger.error(f"Failed to load Greek lemma table: {e}")
    else:
        logger.warning(f"Greek lemma table not found at {greek_path}")
    
    _lemma_tables_loaded = True

def get_latin_lemma_table():
    """Get Latin lemma table, loading if necessary"""
    global LATIN_LEMMA_TABLE
    if LATIN_LEMMA_TABLE is None:
        load_lemma_tables()
    return LATIN_LEMMA_TABLE if LATIN_LEMMA_TABLE is not None else {}

def get_greek_lemma_table():
    """Get Greek lemma table, loading if necessary"""
    global GREEK_LEMMA_TABLE
    if GREEK_LEMMA_TABLE is None:
        load_lemma_tables()
    return GREEK_LEMMA_TABLE if GREEK_LEMMA_TABLE is not None else {}

def get_reverse_lemma_table(language='la'):
    """Get reverse lemma table (lemma -> set of inflected forms), loading if necessary"""
    global LATIN_REVERSE_LEMMA, GREEK_REVERSE_LEMMA
    if LATIN_REVERSE_LEMMA is None:
        load_lemma_tables()
    if language == 'la':
        return LATIN_REVERSE_LEMMA if LATIN_REVERSE_LEMMA is not None else {}
    elif language == 'grc':
        return GREEK_REVERSE_LEMMA if GREEK_REVERSE_LEMMA is not None else {}
    return {}

# =============================================================================
# LAZY LOADING FOR CLTK/NLTK MODELS
# =============================================================================
# These models are loaded lazily (on first use) to speed up server startup
# This allows the Flask server to start immediately and pass health checks

_cltk_latin_lemmatizer = None
_cltk_greek_lemmatizer = None
_stanza_grc_nlp = None  # Stanza Ancient Greek PROIEL model (97% Koine accuracy)
_nltk_english_lemmatizer = None
_cltk_latin_pos_tagger = None
_cltk_greek_pos_tagger = None
_models_initialized = False

def _init_nlp_models():
    """Initialize NLP models lazily on first use"""
    global _cltk_latin_lemmatizer, _cltk_greek_lemmatizer, _nltk_english_lemmatizer
    global _cltk_latin_pos_tagger, _cltk_greek_pos_tagger, _models_initialized
    
    if _models_initialized:
        return
    _models_initialized = True
    
    # CLTK Latin
    try:
        from cltk.lemmatize.lat import LatinBackoffLemmatizer
        _cltk_latin_lemmatizer = LatinBackoffLemmatizer()
        logger.info("CLTK LatinBackoffLemmatizer loaded successfully")
    except Exception as e:
        logger.warning(f"CLTK Latin not available ({e})")
    
    # CLTK Latin POS
    try:
        from cltk.tag.pos import POSTag
        _cltk_latin_pos_tagger = POSTag('lat')
        logger.info("CLTK Latin POS tagger loaded successfully")
    except Exception as e:
        logger.warning(f"CLTK Latin POS tagger not available ({e})")
    
    # CLTK Greek
    try:
        from cltk.lemmatize.grc import GreekBackoffLemmatizer
        _cltk_greek_lemmatizer = GreekBackoffLemmatizer()
        logger.info("CLTK GreekBackoffLemmatizer loaded successfully")
    except Exception as e:
        logger.warning(f"CLTK Greek not available ({e})")
    
    # CLTK Greek POS
    try:
        from cltk.tag.pos import POSTag
        _cltk_greek_pos_tagger = POSTag('grc')
        logger.info("CLTK Greek POS tagger loaded successfully")
    except Exception as e:
        logger.warning(f"CLTK Greek POS tagger not available ({e})")
    
    # NLTK English
    try:
        import nltk
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)
        from nltk.stem import WordNetLemmatizer
        _nltk_english_lemmatizer = WordNetLemmatizer()
        logger.info("NLTK WordNetLemmatizer and POS tagger loaded successfully")
    except Exception as e:
        logger.warning(f"NLTK English not available ({e})")

class TextProcessor:
    def __init__(self):
        # Models are loaded lazily on first use
        self._models_loaded = False
        self.use_cltk_latin = False
        self.use_cltk_greek = False
        self.use_nltk_english = False
        self.use_latin_pos = False
        self.use_greek_pos = False
        self.use_english_pos = False
        self.latin_lemmatizer = None
        self.greek_lemmatizer = None
        self.english_lemmatizer = None
        self.latin_pos_tagger = None
        self.greek_pos_tagger = None
        self.lemma_cache = {}
        self.pos_cache = {}
        self._processed_cache = {}
    
    def _ensure_models_loaded(self):
        """Lazily load NLP models on first use"""
        if self._models_loaded:
            return
        self._models_loaded = True
        
        # Initialize the models
        _init_nlp_models()
        
        # Copy references to instance
        self.latin_lemmatizer = _cltk_latin_lemmatizer
        self.greek_lemmatizer = _cltk_greek_lemmatizer
        self.english_lemmatizer = _nltk_english_lemmatizer
        self.latin_pos_tagger = _cltk_latin_pos_tagger
        self.greek_pos_tagger = _cltk_greek_pos_tagger
        
        # Set availability flags
        self.use_cltk_latin = _cltk_latin_lemmatizer is not None
        self.use_cltk_greek = _cltk_greek_lemmatizer is not None
        self.use_nltk_english = _nltk_english_lemmatizer is not None
        self.use_latin_pos = _cltk_latin_pos_tagger is not None
        self.use_greek_pos = _cltk_greek_pos_tagger is not None
        self.use_english_pos = _nltk_english_lemmatizer is not None
    
    def split_into_phrases(self, text, language='la'):
        """Split text into phrases based on sentence-ending punctuation (not colons)"""
        if language in _LANGUAGE_HANDLERS:
            return _LANGUAGE_HANDLERS[language].split_into_phrases(text)
        elif language == 'grc':
            # Greek: period, semicolon (;), ano teleia (·), question mark, exclamation
            phrase_delimiters = r'[.;·?!]'
        else:
            # Latin/English: period, semicolon, question mark, exclamation (NOT colon)
            phrase_delimiters = r'[.;?!]'

        phrases = re.split(phrase_delimiters, text)
        phrases = [p.strip() for p in phrases if p.strip() and len(p.strip().split()) >= 2]
        return phrases

    def _ends_sentence(self, text, language='la'):
        """Check if text ends with sentence-ending punctuation."""
        text = text.rstrip()
        if not text:
            return False
        if language in _LANGUAGE_HANDLERS:
            return _LANGUAGE_HANDLERS[language].ends_sentence(text)
        elif language == 'grc':
            return text[-1] in '.;·?!'
        else:
            return text[-1] in '.;?!'
    
    def _tokenize_and_lemmatize(self, text, language):
        """Helper: tokenize and lemmatize text for any language."""
        if language in _LANGUAGE_HANDLERS:
            return _LANGUAGE_HANDLERS[language].tokenize_and_lemmatize(text)
        elif language == 'grc':
            original_tokens, tokens = self.tokenize_greek(text, preserve_case=True)
            lemmas = self._greek_lemmatize(tokens)
        elif language == 'en':
            original_tokens, tokens = self.tokenize_english(text, preserve_case=True)
            lemmas = self._english_lemmatize(tokens)
        else:
            original_tokens, tokens = self.tokenize_latin(text, preserve_case=True)
            lemmas = self._latin_lemmatize(tokens)
        pos_tags = self._get_pos_tags(tokens, language)
        return original_tokens, tokens, lemmas, pos_tags

    def _coptic_subword_unit_or_none(self, tess_basename, ref, text):
        """Build a unit dict for a Coptic line from the SCRIPTORIUM sub-word
        cache, or return None if no cache entry exists.

        When the cache hits, ``tokens`` / ``lemmas`` come from CoNLL-U
        morpheme-level annotations (e.g. ``ⲙⲛⲛⲉⲣⲣⲱⲟⲩ`` -> ``ⲙⲛ`` + ``ⲛⲉ``
        + ``ⲣⲣⲱⲟⲩ``); the displayed ``text`` stays the raw bound-group line so
        the UI still shows readable Coptic. ``original_tokens`` is the
        whitespace-split bound-group form for callers that need it.
        """
        try:
            from backend.coptic.processor import get_subword_units_for_ref
        except ImportError:
            return None
        result = get_subword_units_for_ref(tess_basename, ref)
        if not result:
            return None
        tokens, lemmas = result
        return {
            'ref': ref,
            'text': text,
            'tokens': tokens,
            'original_tokens': text.split(),
            'lemmas': lemmas,
            'pos_tags': ['UNK'] * len(tokens),
        }

    def process_file(self, filepath, language='la', unit_type='line'):
        """Process a .tess file and return list of text units

        Args:
            filepath: Path to .tess file
            language: 'la', 'grc', or 'en'
            unit_type: 'line' for poetic lines, 'phrase' for sentences/phrases
        """
        units = []

        if unit_type == 'phrase':
            # Accumulate consecutive lines into sentence units.
            # A sentence ends when a line ends with sentence-ending punctuation (.;?!).
            # The ref for a multi-line sentence is "first_ref-last_ref".
            raw_lines = []
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    match = re.match(r'^<([^>]+)>\s*(.+)$', line)
                    if match:
                        raw_lines.append((match.group(1), match.group(2)))

            # Accumulate into sentences
            buf_refs = []
            buf_texts = []
            for ref, text in raw_lines:
                buf_refs.append(ref)
                buf_texts.append(text)
                if self._ends_sentence(text, language):
                    # Emit accumulated sentence
                    combined_text = ' '.join(buf_texts)
                    if len(buf_refs) == 1:
                        combined_ref = buf_refs[0]
                    else:
                        combined_ref = f"{buf_refs[0]}-{buf_refs[-1]}"
                    original_tokens, tokens, lemmas, pos_tags = self._tokenize_and_lemmatize(combined_text, language)
                    units.append({
                        'ref': combined_ref,
                        'text': combined_text,
                        'tokens': tokens,
                        'original_tokens': original_tokens,
                        'lemmas': lemmas,
                        'pos_tags': pos_tags,
                        'line_refs': list(buf_refs),
                    })
                    buf_refs = []
                    buf_texts = []

            # Flush any remaining lines (no sentence-ending punctuation at end of file)
            if buf_texts:
                combined_text = ' '.join(buf_texts)
                if len(buf_refs) == 1:
                    combined_ref = buf_refs[0]
                else:
                    combined_ref = f"{buf_refs[0]}-{buf_refs[-1]}"
                original_tokens, tokens, lemmas, pos_tags = self._tokenize_and_lemmatize(combined_text, language)
                units.append({
                    'ref': combined_ref,
                    'text': combined_text,
                    'tokens': tokens,
                    'original_tokens': original_tokens,
                    'lemmas': lemmas,
                    'pos_tags': pos_tags,
                    'line_refs': list(buf_refs),
                })

            return units

        # Coptic line-mode pulls sub-word tokens/lemmas from the SCRIPTORIUM
        # CoNLL-U cache (cache/lemmas/cop/<basename>.json) so that bound groups
        # are split into morphemes. Falls back per-line to runtime
        # bound-group tokenization when no cache entry is available.
        cop_basename = None
        if language == 'cop':
            cop_basename = os.path.basename(filepath)
            if cop_basename.endswith('.tess'):
                cop_basename = cop_basename[:-5]

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                match = re.match(r'^<([^>]+)>\s*(.+)$', line)
                if match:
                    ref = match.group(1)
                    text = match.group(2)
                    cached_unit = None
                    if cop_basename is not None:
                        cached_unit = self._coptic_subword_unit_or_none(cop_basename, ref, text)
                    if cached_unit is not None:
                        units.append(cached_unit)
                    else:
                        original_tokens, tokens, lemmas, pos_tags = self._tokenize_and_lemmatize(text, language)
                        units.append({
                            'ref': ref,
                            'text': text,
                            'tokens': tokens,
                            'original_tokens': original_tokens,
                            'lemmas': lemmas,
                            'pos_tags': pos_tags
                        })

        return units
    
    def process_line(self, text, language='la'):
        """Process a single line of text and return a unit dict with tokens, lemmas, pos_tags.
        Used for line-search feature where user provides arbitrary text."""
        if language in _LANGUAGE_HANDLERS:
            original_tokens, tokens, lemmas, pos_tags = _LANGUAGE_HANDLERS[language].tokenize_and_lemmatize(text)
            return {
                'ref': '',
                'text': text,
                'tokens': tokens,
                'original_tokens': original_tokens,
                'lemmas': lemmas,
                'pos_tags': pos_tags
            }
        elif language == 'grc':
            original_tokens, tokens = self.tokenize_greek(text, preserve_case=True)
            lemmas = self._greek_lemmatize(tokens)
            pos_tags = self._get_pos_tags(tokens, language)
        elif language == 'en':
            original_tokens, tokens = self.tokenize_english(text, preserve_case=True)
            lemmas = self._english_lemmatize(tokens)
            pos_tags = self._get_pos_tags(tokens, language)
        else:
            original_tokens, tokens = self.tokenize_latin(text, preserve_case=True)
            lemmas = self._latin_lemmatize(tokens)
            pos_tags = self._get_pos_tags(tokens, language)
        
        return {
            'ref': '',
            'text': text,
            'tokens': tokens,
            'original_tokens': original_tokens,
            'lemmas': lemmas,
            'pos_tags': pos_tags
        }
    
    def lemmatize_word(self, word, language='la'):
        """Lemmatize a single word and return a set of possible lemmas.
        Used for line-search feature."""
        word = word.lower()
        if language in _LANGUAGE_HANDLERS:
            lemma = _LANGUAGE_HANDLERS[language].lemmatize_word(word)
            return {lemma} if isinstance(lemma, str) else set(lemma)
        elif language == 'grc':
            lemmas = self._greek_lemmatize([word])
        elif language == 'en':
            lemmas = self._english_lemmatize([word])
        else:
            lemmas = self._latin_lemmatize([word])
        
        result = set()
        for lemma in lemmas:
            if isinstance(lemma, (list, set)):
                result.update(lemma)
            else:
                result.add(lemma)
        return result
    
    def tokenize_latin(self, text, preserve_case=False):
        """Tokenize Latin text into words
        
        Args:
            text: The text to tokenize
            preserve_case: If True, returns (original_tokens, normalized_tokens) tuple
        """
        # First extract original tokens before normalization
        original_text = re.sub(r'[^a-zA-Z\s]', '', text)
        original_tokens = original_text.split()
        
        # Normalize for matching
        text = text.lower()
        text = text.replace('j', 'i').replace('v', 'u')
        text = re.sub(r'[^a-z\s]', '', text)
        tokens = text.split()
        
        if preserve_case:
            return original_tokens, tokens
        return tokens
    
    def tokenize_greek(self, text, preserve_case=False):
        """Tokenize Greek text into words, preserving diacritics for lemmatization
        
        Args:
            text: The text to tokenize
            preserve_case: If True, returns (original_tokens, normalized_tokens) tuple
        """
        # First extract original tokens before lowercasing
        original_text = re.sub(r'[^\u0300-\u036f\u0370-\u03ff\u1f00-\u1fff\s]', '', text)
        original_tokens = original_text.split()
        
        # Normalize for matching (lowercase)
        text = text.lower()
        text = re.sub(r'[^\u0300-\u036f\u0370-\u03ff\u1f00-\u1fff\s]', '', text)
        tokens = text.split()
        
        if preserve_case:
            return original_tokens, tokens
        return tokens
    
    def tokenize_english(self, text, preserve_case=False):
        """Tokenize English text into words
        
        Args:
            text: The text to tokenize
            preserve_case: If True, returns (original_tokens, normalized_tokens) tuple
        """
        # Replace dashes and punctuation with spaces first (to properly split words)
        original_text = re.sub(r'[—–\-]+', ' ', text)  # em-dash, en-dash, hyphen -> space
        original_text = re.sub(r'[^a-zA-Z\s\']', ' ', original_text)  # other punct -> space
        original_text = re.sub(r"'s$|'s\s", ' ', original_text)
        original_text = re.sub(r'\s+', ' ', original_text)  # collapse multiple spaces
        original_tokens = [t for t in original_text.split() if len(t) > 1 or t.lower() in ('i', 'a')]
        
        # Normalize for matching
        text = text.lower()
        text = re.sub(r'[—–\-]+', ' ', text)  # em-dash, en-dash, hyphen -> space
        text = re.sub(r'[^a-z\s\']', ' ', text)  # other punct -> space
        text = re.sub(r"'s$|'s\s", ' ', text)
        text = re.sub(r'\s+', ' ', text)  # collapse multiple spaces
        tokens = text.split()
        tokens = [t for t in tokens if len(t) > 1 or t in ('i', 'a')]
        
        if preserve_case:
            return original_tokens, tokens
        return tokens
    
    def _normalize_greek_token(self, token):
        """Normalize Greek token for matching (remove diacritics)"""
        nfkd = unicodedata.normalize('NFKD', token)
        normalized = ''.join(c for c in nfkd if not unicodedata.combining(c))
        normalized = normalized.replace('ς', 'σ')
        return normalized
    
    def _latin_lemmatize(self, tokens):
        """Latin lemmatization using static lookup table, with CLTK fallback"""
        self._ensure_models_loaded()
        lemmas = []
        for token in tokens:
            cache_key = f"la:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue
            
            norm_token = token.lower().replace('j', 'i').replace('v', 'u')
            
            lemma = None
            stripped_base = None
            latin_table = get_latin_lemma_table()
            
            if norm_token in latin_table:
                lemma = latin_table[norm_token]
            else:
                # Try enclitic stripping ('que', 'ne', 'ue'), but only commit
                # to it when the stripped form actually resolves in the
                # lemma table. The previous version set stripped_base on any
                # `.endswith` match, which then propagated to the CLTK
                # fallback and the final fallback even for words that merely
                # end in '-ne' or '-ue' (vimine, paene, Cyrene). The wrong
                # truncated lemma got cached permanently. Only record
                # stripped_base when the stripping is productive.
                for enclitic in ['que', 'ne', 'ue']:
                    if norm_token.endswith(enclitic) and len(norm_token) > len(enclitic) + 1:
                        base = norm_token[:-len(enclitic)]
                        if base in latin_table:
                            lemma = latin_table[base]
                            stripped_base = base
                            break
                        elif base + 'm' in latin_table:
                            lemma = latin_table[base + 'm']
                            stripped_base = base
                            break
                        # base did not resolve in either form; do not commit
                        # to stripping. Leave stripped_base as None so the
                        # fallbacks below use the original token.

            if lemma is None and self.use_cltk_latin and self.latin_lemmatizer:
                try:
                    token_to_try = stripped_base if stripped_base else token
                    result = self.latin_lemmatizer.lemmatize([token_to_try])
                    raw_lemma = result[0][1] if result else (stripped_base or norm_token)
                    lemma = re.sub(r'\d+$', '', raw_lemma)
                except Exception:
                    lemma = stripped_base or norm_token

            if lemma is None:
                lemma = stripped_base or norm_token
            
            self.lemma_cache[cache_key] = lemma
            lemmas.append(lemma)
        
        return lemmas
    
    def _cltk_latin_lemmatize(self, tokens):
        """Use CLTK LatinBackoffLemmatizer"""
        lemmas = []
        for token in tokens:
            cache_key = f"la:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue
            
            try:
                result = self.latin_lemmatizer.lemmatize([token])
                if result and len(result) > 0:
                    lemma = re.sub(r'\d+$', '', result[0][1])
                else:
                    lemma = token
            except Exception:
                lemma = token
            
            self.lemma_cache[cache_key] = lemma
            lemmas.append(lemma)
        
        return lemmas
    
    def _greek_lemmatize(self, tokens):
        """Greek lemmatization: lookup table (690K entries) -> Stanza grc_proiel fallback (97% accuracy)"""
        self._ensure_models_loaded()
        lemmas = []
        stanza_batch = []  # tokens needing Stanza fallback
        stanza_indices = []  # their positions in lemmas list

        for token in tokens:
            cache_key = f"grc:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue

            norm_token = self._normalize_greek_token(token)
            greek_table = get_greek_lemma_table()

            if norm_token in greek_table:
                lemma = greek_table[norm_token]
                self.lemma_cache[cache_key] = lemma
                lemmas.append(lemma)
            else:
                # Placeholder; will be filled by Stanza batch
                lemmas.append(None)
                stanza_batch.append(token)
                stanza_indices.append(len(lemmas) - 1)

        # Batch Stanza fallback for all tokens not in lookup table
        if stanza_batch:
            stanza_lemmas = self._stanza_greek_lemmatize_batch(stanza_batch)
            for i, idx in enumerate(stanza_indices):
                lemma = stanza_lemmas[i] if i < len(stanza_lemmas) else self._normalize_greek_token(stanza_batch[i])
                lemmas[idx] = lemma
                cache_key = f"grc:{stanza_batch[i]}"
                self.lemma_cache[cache_key] = lemma

        # Final fallback: any remaining None -> normalized form
        for i in range(len(lemmas)):
            if lemmas[i] is None:
                lemmas[i] = self._normalize_greek_token(tokens[i])

        return lemmas

    def _stanza_greek_lemmatize_batch(self, tokens):
        """Use Stanza grc_proiel model (97% accuracy) for tokens not in lookup table.

        Lazy-loads on first call. Skipped during frequency cache init to avoid
        loading ~200MB model at startup.
        """
        global _stanza_grc_nlp
        # Skip Stanza during frequency cache init -- the 690K lookup table is
        # sufficient for counting lemma frequencies, and loading Stanza adds
        # ~200MB RAM + minutes of processing time at startup.
        if getattr(self, '_skip_stanza', False):
            return [self._normalize_greek_token(t) for t in tokens]
        if _stanza_grc_nlp is None and not getattr(self.__class__, '_stanza_grc_attempted', False):
            self.__class__._stanza_grc_attempted = True
            try:
                import stanza
                _stanza_grc_nlp = stanza.Pipeline(
                    'grc', package='proiel',
                    processors='tokenize,lemma',
                    tokenize_pretokenized=True,
                    verbose=False, use_gpu=False,
                )
                logger.info("Stanza Ancient Greek (PROIEL) pipeline loaded for fallback lemmatization")
            except Exception as e:
                logger.warning(f"Stanza Ancient Greek not available: {e}")
                _stanza_grc_nlp = None

        if _stanza_grc_nlp is None:
            # Fall back to CLTK or normalized form
            if self.use_cltk_greek and self.greek_lemmatizer:
                return [self._normalize_greek_token(
                    self.greek_lemmatizer.lemmatize([t])[0][1]
                    if self.greek_lemmatizer.lemmatize([t]) else t
                ) for t in tokens]
            return [self._normalize_greek_token(t) for t in tokens]

        try:
            # Process as a single pre-tokenized sentence
            doc = _stanza_grc_nlp([tokens])
            lemmas = []
            for sent in doc.sentences:
                for word in sent.words:
                    lemmas.append(self._normalize_greek_token(word.lemma) if word.lemma else self._normalize_greek_token(word.text))
            # Align output to input (Stanza may split differently)
            if len(lemmas) == len(tokens):
                return lemmas
            elif len(lemmas) > len(tokens):
                return lemmas[:len(tokens)]
            else:
                return lemmas + [self._normalize_greek_token(t) for t in tokens[len(lemmas):]]
        except Exception as e:
            logger.warning(f"Stanza Greek fallback failed: {e}")
            return [self._normalize_greek_token(t) for t in tokens]
    
    def _cltk_greek_lemmatize(self, tokens):
        """Use CLTK GreekBackoffLemmatizer"""
        lemmas = []
        for token in tokens:
            cache_key = f"grc:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue
            
            try:
                result = self.greek_lemmatizer.lemmatize([token])
                if result and len(result) > 0:
                    lemma = result[0][1]
                    lemma = self._normalize_greek_token(lemma)
                else:
                    lemma = self._normalize_greek_token(token)
            except Exception:
                lemma = self._normalize_greek_token(token)
            
            self.lemma_cache[cache_key] = lemma
            lemmas.append(lemma)
        
        return lemmas
    
    def _english_lemmatize(self, tokens):
        """English lemmatization using NLTK WordNet"""
        self._ensure_models_loaded()
        if self.use_nltk_english and self.english_lemmatizer:
            return self._nltk_english_lemmatize(tokens)
        else:
            return tokens
    
    def _nltk_english_lemmatize(self, tokens):
        """Use NLTK WordNetLemmatizer"""
        lemmas = []
        for token in tokens:
            cache_key = f"en:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue
            
            try:
                lemma_n = self.english_lemmatizer.lemmatize(token, pos='n')
                lemma_v = self.english_lemmatizer.lemmatize(token, pos='v')
                if lemma_v != token and len(lemma_v) < len(lemma_n):
                    lemma = lemma_v
                elif lemma_n != token:
                    lemma = lemma_n
                else:
                    lemma = lemma_v
            except Exception:
                lemma = token
            
            self.lemma_cache[cache_key] = lemma
            lemmas.append(lemma)
        
        return lemmas
    
    def tokenize(self, text):
        """Default tokenizer (Latin) for backward compatibility"""
        return self.tokenize_latin(text)
    
    def _get_pos_tags(self, tokens, language='la'):
        """Get POS tags for tokens based on language"""
        if not tokens:
            return []
        
        cache_key = (language, tuple(tokens))
        if cache_key in self.pos_cache:
            return self.pos_cache[cache_key]
        
        pos_tags = []
        
        try:
            import sys
            old_limit = sys.getrecursionlimit()
            if old_limit < 5000:
                sys.setrecursionlimit(5000)
            if language == 'la' and self.use_latin_pos and self.latin_pos_tagger:
                text_str = ' '.join(tokens) if isinstance(tokens, list) else tokens
                tagged = self.latin_pos_tagger.tag_tnt(text_str)
                if tagged and len(tagged) > 0:
                    pos_tags = [tag if tag else 'UNK' for _, tag in tagged]
                else:
                    pos_tags = ['UNK'] * len(tokens)
            elif language == 'grc' and self.use_greek_pos and self.greek_pos_tagger:
                text_str = ' '.join(tokens) if isinstance(tokens, list) else tokens
                tagged = self.greek_pos_tagger.tag_tnt(text_str)
                if tagged and len(tagged) > 0:
                    pos_tags = [tag if tag else 'UNK' for _, tag in tagged]
                else:
                    pos_tags = ['UNK'] * len(tokens)
            elif language == 'en' and self.use_english_pos:
                from nltk import pos_tag as nltk_pos_tag
                tagged = nltk_pos_tag(tokens)
                pos_tags = [tag for _, tag in tagged] if tagged else ['UNK'] * len(tokens)
            else:
                pos_tags = ['UNK'] * len(tokens)
        except RecursionError:
            pos_tags = ['UNK'] * len(tokens)
        except Exception as e:
            if not getattr(self, '_pos_error_logged', False):
                logger.error(f"POS tagging error for {language}: {e}")
                self._pos_error_logged = True
            pos_tags = ['UNK'] * len(tokens)
        
        if len(pos_tags) != len(tokens):
            pos_tags = (pos_tags + ['UNK'] * len(tokens))[:len(tokens)]
        
        self.pos_cache[cache_key] = pos_tags
        return pos_tags
