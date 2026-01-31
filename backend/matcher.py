"""
Tesserae V6 - Matcher

Core matching engine for finding shared vocabulary between texts.
Identifies word-level correspondences using various matching strategies.

Match Types:
    - lemma: Match by dictionary form (e.g., "arma" matches "armis", "armorum")
    - exact: Match only identical surface forms
    - sound: Phonetic similarity via character trigrams

Stoplist Generation:
    Uses Zipf's law elbow detection to automatically identify
    high-frequency function words to exclude from matching.

Stoplist Basis Options:
    - corpus: Use corpus-wide frequencies (default)
    - source: Use source text frequencies only
    - target: Use target text frequencies only
    - source_target: Use combined source+target frequencies
"""
import unicodedata

def normalize_greek(text):
    """Strip accents/diacritics from Greek text for stoplist comparison"""
    # NFD decomposes characters, then we filter out combining marks
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()

def normalize_latin(text):
    """Normalize Latin text for stoplist comparison (u/v equivalence)"""
    # Classical Latin texts often use 'u' where modern editions use 'v'
    return text.lower().replace('v', 'u')

from collections import defaultdict, Counter
import math
from backend.zipf import find_zipf_elbow
from backend.feature_extractor import feature_extractor

DEFAULT_LATIN_STOP_WORDS_LIST = [
    'et', 'in', 'est', 'non', 'ut', 'cum', 'ad', 'sed', 'si', 'quod',
    'qui', 'quae', 'que', 'de', 'ex', 'per', 'ab', 'ac', 'atque',
    'aut', 'nec', 'neque', 'enim', 'nam', 'iam', 'tamen', 'autem',
    'quidem', 'hic', 'haec', 'hoc', 'ille', 'illa', 'illud', 'is', 
    'ea', 'id', 'ipse', 'ipsa', 'ipsum', 'se', 'suus', 'sua', 'suum',
    'esse', 'sum', 'fui', 'sunt', 'erat', 'erant', 'fuit', 'a', 'o',
    'te', 'tu', 'me', 'ego', 'nos', 'vos', 'noster', 'vester',
    'omnis', 'omnia', 'omnes', 'nullus', 'nulla', 'nullum',
    'unus', 'duo', 'tres', 'primus', 'secundus', 'tertius',
    'ubi', 'nunc', 'sic', 'tam', 'tum', 'ita', 'ibi', 'hinc', 'inde',
    'quo', 'qua', 'quam', 'quando', 'unde', 'cur', 'ergo', 'igitur'
]

DEFAULT_GREEK_STOP_WORDS_LIST = [
    # Particles and conjunctions
    'και', 'δε', 'τε', 'γαρ', 'μεν', 'δη', 'ου', 'ουκ', 'ουχ', 'μη',
    'αλλα', 'αλλ', 'ουδε', 'μηδε', 'ουτε', 'μητε', 'ειτε', 'ητοι',
    'νυ', 'τοι', 'περ', 'γε', 'κε', 'κεν', 'ρα',
    # Prepositions
    'εν', 'εις', 'εκ', 'εξ', 'προς', 'απο', 'περι', 'κατα',
    'μετα', 'δια', 'υπο', 'υπερ', 'παρα', 'επι', 'αντι', 'συν', 'προ',
    # Elided forms (base without final vowel)
    'αλλ', 'αρ', 'επ', 'απ', 'κατ', 'μετ', 'παρ', 'υπ', 'αμφ', 'αντ',
    # Article forms (all cases)
    'ο', 'η', 'το', 'οι', 'αι', 'τα', 'τον', 'την', 'του', 'της',
    'τω', 'τη', 'τοις', 'ταις', 'τους', 'τας', 'των',
    # Relative/demonstrative pronouns
    'ος', 'ης', 'ον', 'οστις', 'ητις', 'οτι', 'ως', 'αν', 'ει',
    'ου', 'ης', 'ω', 'ην', 'οις', 'αις', 'ους', 'ας', 'ων', 'α',
    # αυτος forms (all cases)
    'αυτος', 'αυτη', 'αυτο', 'αυτον', 'αυτην', 'αυτου', 'αυτης',
    'αυτω', 'αυτοι', 'αυται', 'αυτα', 'αυτους', 'αυτας', 'αυτων', 'αυτοις', 'αυταις',
    # ουτος forms
    'ουτος', 'αυτη', 'τουτο', 'τουτον', 'ταυτην', 'τουτου', 'ταυτης',
    'τουτω', 'ταυτη', 'ουτοι', 'αυται', 'ταυτα', 'τουτους', 'ταυτας', 'τουτων', 'τουτοις', 'ταυταις',
    # εκεινος forms  
    'εκεινος', 'εκεινη', 'εκεινο', 'εκεινον', 'εκεινην', 'εκεινου', 'εκεινης',
    'εκεινω', 'εκεινοι', 'εκειναι', 'εκεινα', 'εκεινους', 'εκεινας', 'εκεινων', 'εκεινοις', 'εκειναις',
    # Personal pronouns
    'εγω', 'εμε', 'με', 'εμου', 'μου', 'εμοι', 'μοι',
    'συ', 'σε', 'σου', 'σοι',
    'ημεις', 'ημας', 'ημων', 'ημιν',
    'υμεις', 'υμας', 'υμων', 'υμιν',
    # τις/τι (indefinite/interrogative)
    'τις', 'τι', 'τινα', 'τινος', 'τινι', 'τινες', 'τινων', 'τισι', 'τισιν',
    # ειμι (to be) forms
    'εστι', 'εστιν', 'ειμι', 'ην', 'ησαν', 'ει', 'εσμεν', 'εστε', 'εισι', 'εισιν',
    # Common verbs - βαινω (go), φημι (say), ερχομαι (come)
    'βη', 'βαν', 'βας', 'βησαν', 'εβη', 'φη', 'εφη', 'φησι', 'ηλθε', 'ηλθον',
    # Common adverbs
    'νυν', 'ετι', 'ουν', 'αρα', 'τοτε', 'ποτε', 'πω', 'πως', 'που', 'οπου', 'οθεν',
    'ενθα', 'ενθεν', 'οπως', 'ωστε', 'ουτω', 'ουτως'
]

DEFAULT_ENGLISH_STOP_WORDS_LIST = [
    # Modern common words
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
    'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
    'when', 'make', 'can', 'like', 'no', 'just', 'him', 'know', 'take', 'into',
    'your', 'some', 'could', 'them', 'see', 'other', 'than', 'then', 'now', 'its',
    'is', 'am', 'are', 'was', 'were', 'been', 'being', 'has', 'had', 'having',
    # Early Modern / Archaic English (Shakespeare, Milton, etc.)
    'thou', 'thee', 'thy', 'thine', 'thyself', 'ye', 'art', 'doth', 'dost',
    'hath', 'hast', 'shalt', 'wilt', 'canst', 'wouldst', 'shouldst', 'couldst',
    'didst', 'hadst', 'mayst', 'mightst', 'wast', 'wert', 'wherefore', 'wherein',
    'whereon', 'thereof', 'therein', 'herein', 'hereby', 'hither', 'thither',
    'whither', 'hence', 'thence', 'ere', 'oft', 'nay', 'yea', 'aye', 'prithee',
    'methinks', 'forsooth', 'verily', 'tis', 'twas', 'twere', 'twill', 'twould',
    'o', 'oh', 'ah', 'alas', 'lo', 'behold', 'nought', 'naught', 'upon', 'unto',
    'hither', 'hence', 'thus', 'such', 'each', 'every', 'both', 'own', 'same',
    'much', 'more', 'most', 'yet', 'still', 'even', 'also', 'too', 'very',
    'here', 'how', 'why', 'where', 'whence', 'whether', 'while', 'whilst',
    'though', 'although', 'because', 'since', 'before', 'after', 'until', 'till',
    'shall', 'should', 'may', 'might', 'must', 'need', 'dare', 'let', 'lest',
    'nor', 'neither', 'either', 'none', 'any', 'many', 'few', 'less', 'least'
]

DEFAULT_LATIN_STOP_WORDS = set(DEFAULT_LATIN_STOP_WORDS_LIST)
DEFAULT_GREEK_STOP_WORDS = set(DEFAULT_GREEK_STOP_WORDS_LIST)
DEFAULT_ENGLISH_STOP_WORDS = set(DEFAULT_ENGLISH_STOP_WORDS_LIST)

class Matcher:
    def __init__(self):
        self.synonym_dict = {}
        self.stoplist_cache = {}
    
    def load_synonyms(self, filepath):
        """Load synonym dictionary for semantic matching"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        word = parts[0]
                        synonyms = parts[1].split(',')
                        self.synonym_dict[word] = set(synonyms)
        except FileNotFoundError:
            pass
    
    def build_stoplist(self, source_units, target_units, stoplist_basis='source_target', language='la', corpus_frequencies=None, match_type='lemma'):
        """Build stoplist using Zipf elbow detection based on specified text basis"""
        # For exact match, use tokens; otherwise use lemmas
        use_tokens = (match_type == 'exact')
        feature_key = 'tokens' if use_tokens else 'lemmas'
        
        if stoplist_basis == 'corpus' and corpus_frequencies and not use_tokens:
            freq = Counter()
            freq.update(corpus_frequencies)
        elif stoplist_basis == 'source':
            all_features = []
            for unit in source_units:
                all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
            freq = Counter(all_features)
        elif stoplist_basis == 'target':
            all_features = []
            for unit in target_units:
                all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
            freq = Counter(all_features)
        else:
            all_features = []
            for unit in source_units + target_units:
                all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
            freq = Counter(all_features)
        
        # Exact match on tokens needs more aggressive stoplist since token distributions
        # are more gradual than lemma distributions (accents create variants, and 
        # articles/pronouns/conjunctions have many inflected forms)
        if use_tokens:
            # For tokens: Zipf elbow often finds early cutoff, but function words
            # extend much further due to inflection. Use both elbow detection AND
            # a frequency-based minimum to catch all high-frequency function words
            zipf_stops = find_zipf_elbow(freq, min_stopwords=50, max_stopwords=120)
            
            # Additionally, stop all tokens appearing 40+ times - this catches
            # articles, pronouns, conjunctions, common verbs like φάτο ("said"),
            # forms of "or" (ἤ, ἠέ), demonstratives (τάδε), etc.
            # For exact match, we need aggressive filtering since inflected forms
            # spread frequency across many surface tokens
            high_freq_stops = set(word for word, count in freq.items() if count >= 40)
            zipf_stops = zipf_stops.union(high_freq_stops)
        else:
            zipf_stops = find_zipf_elbow(freq, min_stopwords=10, max_stopwords=50)
        
        if language == 'la':
            base_stops = DEFAULT_LATIN_STOP_WORDS
        elif language == 'grc':
            base_stops = DEFAULT_GREEK_STOP_WORDS
        else:
            base_stops = DEFAULT_ENGLISH_STOP_WORDS
        
        return zipf_stops.union(base_stops)
    
    def build_stoplist_auto(self, source_units, target_units, language='la'):
        """Build automatic stoplist using Zipf elbow detection (backward compatible)"""
        return self.build_stoplist(source_units, target_units, 'source_target', language)
    
    def build_stoplist_manual(self, units, stoplist_size=10, language='la', match_type='lemma'):
        """Build manual stoplist with fixed size"""
        if stoplist_size == 0:
            return set()
        
        # For exact match, use tokens; otherwise use lemmas
        use_tokens = (match_type == 'exact')
        feature_key = 'tokens' if use_tokens else 'lemmas'
        
        all_features = []
        for unit in units:
            all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
        
        freq = Counter(all_features)
        
        if language == 'la':
            base_stops = set(DEFAULT_LATIN_STOP_WORDS_LIST[:stoplist_size])
        elif language == 'grc':
            base_stops = set(DEFAULT_GREEK_STOP_WORDS_LIST[:stoplist_size])
        else:
            base_stops = set(DEFAULT_ENGLISH_STOP_WORDS_LIST[:stoplist_size])
        
        top_freq = set(w for w, _ in freq.most_common(stoplist_size))
        
        return base_stops.union(top_freq)
    
    def find_matches(self, source_units, target_units, settings=None, corpus_frequencies=None):
        """Find matching lemmas between source and target texts"""
        settings = settings or {}
        min_matches = settings.get('min_matches', 2)
        match_type = settings.get('match_type', 'lemma')
        stoplist_basis = settings.get('stoplist_basis', 'source_target')
        language = settings.get('language', 'la')
        max_distance = settings.get('max_distance', 999)
        stoplist_size = settings.get('stoplist_size', 0)
        custom_stopwords = settings.get('custom_stopwords', '')
        
        if match_type == 'sound':
            return self.find_sound_matches(source_units, target_units, settings)
        
        if stoplist_size == -1:
            stop_words = set()
        elif stoplist_size > 0:
            stop_words = self.build_stoplist_manual(source_units + target_units, stoplist_size, language, match_type)
        else:
            stop_words = self.build_stoplist(source_units, target_units, stoplist_basis, language, corpus_frequencies, match_type)
        
        if custom_stopwords:
            custom_list = [w.strip().lower() for w in custom_stopwords.split(',') if w.strip()]
            stop_words = stop_words.union(set(custom_list))
        
        # Create normalized stopwords sets for language-specific matching
        if language == 'grc':
            normalized_stop_words = set(normalize_greek(w) for w in stop_words)
        elif language == 'la':
            normalized_stop_words = set(normalize_latin(w) for w in stop_words)
        else:
            normalized_stop_words = set(w.lower() for w in stop_words)
        
        def is_stopword(word):
            """Check if word is a stopword, using language-specific normalization"""
            if word in stop_words:
                return True
            if language == 'grc':
                normalized = normalize_greek(word)
                if normalized in normalized_stop_words:
                    return True
                clean_word = normalized.rstrip("'᾽'")
                if clean_word in normalized_stop_words:
                    return True
            elif language == 'la':
                # Latin u/v normalization
                normalized = normalize_latin(word)
                if normalized in normalized_stop_words:
                    return True
            return False
        
        target_index = defaultdict(list)
        for i, unit in enumerate(target_units):
            if match_type == 'exact':
                features = set(unit['tokens'])
            else:
                features = set(unit['lemmas'])
            
            for feature in features:
                if not is_stopword(feature) and len(feature) > 2:
                    target_index[feature].append(i)
                    
                    if match_type == 'syn' and feature in self.synonym_dict:
                        for syn in self.synonym_dict[feature]:
                            target_index[syn].append(i)
        
        matches = []
        
        for src_idx, src_unit in enumerate(source_units):
            if match_type == 'exact':
                src_features = set(f for f in src_unit['tokens'] 
                                  if not is_stopword(f) and len(f) > 2)
            else:
                src_features = set(f for f in src_unit['lemmas'] 
                                  if not is_stopword(f) and len(f) > 2)
            
            target_matches = defaultdict(set)
            
            for feature in src_features:
                if feature in target_index:
                    for tgt_idx in target_index[feature]:
                        target_matches[tgt_idx].add(feature)
                
                if match_type == 'syn' and feature in self.synonym_dict:
                    for syn in self.synonym_dict[feature]:
                        if syn in target_index:
                            for tgt_idx in target_index[syn]:
                                target_matches[tgt_idx].add(feature)
            
            for tgt_idx, matched_features in target_matches.items():
                if len(matched_features) >= min_matches:
                    src_distance = self._get_feature_span(src_unit, matched_features, match_type)
                    tgt_distance = self._get_feature_span(target_units[tgt_idx], matched_features, match_type)
                    
                    if src_distance <= max_distance and tgt_distance <= max_distance:
                        matches.append({
                            'source_idx': src_idx,
                            'target_idx': tgt_idx,
                            'matched_lemmas': list(matched_features)
                        })
        
        return matches, len(stop_words)
    
    def find_sound_matches(self, source_units, target_units, settings=None):
        """
        Find matches based on sound similarity using character trigrams.
        This is an alternative to lemma/exact matching for detecting alliteration,
        rhyme, assonance, and other phonetic patterns.
        
        Performance safeguards:
        - Pre-computes trigram sets for all units
        - Uses similarity floor to skip low-quality pairs early
        - Per-source top-N targeting ensures coverage across all source units
        - Returns top N results by score
        """
        settings = settings or {}
        min_sound_score = settings.get('min_sound_score', 0.25)
        max_results = settings.get('max_results', 500)
        top_n_per_source = settings.get('sound_top_n', 10)
        
        src_trigram_cache = []
        for src_unit in source_units:
            src_tokens = [t for t in src_unit.get('tokens', []) if len(t) >= 3]
            src_trigrams = set()
            for token in src_tokens:
                src_trigrams.update(feature_extractor.get_trigrams(token))
            src_trigram_cache.append((src_tokens, src_trigrams))
        
        tgt_trigram_cache = []
        for tgt_unit in target_units:
            tgt_tokens = [t for t in tgt_unit.get('tokens', []) if len(t) >= 3]
            tgt_trigrams = set()
            for token in tgt_tokens:
                tgt_trigrams.update(feature_extractor.get_trigrams(token))
            tgt_trigram_cache.append((tgt_tokens, tgt_trigrams))
        
        matches = []
        
        for src_idx, (src_tokens, src_trigrams) in enumerate(src_trigram_cache):
            if not src_trigrams:
                continue
            
            src_candidates = []
            for tgt_idx, (tgt_tokens, tgt_trigrams) in enumerate(tgt_trigram_cache):
                if not tgt_trigrams:
                    continue
                
                intersection = len(src_trigrams & tgt_trigrams)
                union = len(src_trigrams | tgt_trigrams)
                unit_similarity = intersection / union if union > 0 else 0
                
                if unit_similarity >= min_sound_score:
                    src_candidates.append((tgt_idx, tgt_tokens, unit_similarity))
            
            src_candidates.sort(key=lambda x: x[2], reverse=True)
            for tgt_idx, tgt_tokens, unit_similarity in src_candidates[:top_n_per_source]:
                tgt_trigrams = tgt_trigram_cache[tgt_idx][1]
                shared_trigrams = list(src_trigrams & tgt_trigrams)
                shared_trigrams.sort(key=lambda t: sum(1 for tok in src_tokens + tgt_tokens if t in tok.lower()), reverse=True)
                top_trigrams = shared_trigrams[:10]
                
                trigram_tokens = {}
                for tri in top_trigrams:
                    src_toks = [t for t in src_tokens if tri in t.lower()]
                    tgt_toks = [t for t in tgt_tokens if tri in t.lower()]
                    if src_toks and tgt_toks:
                        for st in src_toks[:2]:
                            for tt in tgt_toks[:2]:
                                if st.lower() != tt.lower():
                                    trigram_tokens[tri] = (st, tt)
                                    break
                            if tri in trigram_tokens:
                                break
                
                matches.append({
                    'source_idx': src_idx,
                    'target_idx': tgt_idx,
                    'matched_lemmas': [],
                    'match_basis': 'sound',
                    'sound_score': unit_similarity,
                    'shared_trigrams': top_trigrams,
                    'trigram_tokens': trigram_tokens
                })
        
        matches.sort(key=lambda x: x.get('sound_score', 0), reverse=True)
        
        if max_results > 0:
            matches = matches[:max_results]
        
        return matches, 0
    
    def find_edit_distance_matches(self, source_units, target_units, settings=None):
        """
        Find matches based on edit distance (fuzzy string matching).
        Like Filum from QCL: finds phrases with multiple fuzzy word matches.
        Requires min_matches (default 2) fuzzy word pairs per match.
        """
        import time
        settings = settings or {}
        min_similarity = settings.get('min_edit_similarity', 0.7)
        min_matches = settings.get('min_matches', 2)
        max_results = settings.get('max_results', 500)
        top_n_per_source = settings.get('edit_top_n', 10)
        stoplist_size = settings.get('stoplist_size', 0)
        
        num_source = len(source_units)
        num_target = len(target_units)
        total_comparisons = num_source * num_target
        
        print(f"[EDIT_DISTANCE] source_units={num_source}, target_units={num_target}, total_comparisons={total_comparisons}")
        print(f"[EDIT_DISTANCE] stoplist_size={stoplist_size}")
        
        MAX_COMPARISONS = 5_000_000
        if total_comparisons > MAX_COMPARISONS:
            print(f"[EDIT_DISTANCE] WARNING: {total_comparisons:,} comparisons exceeds limit of {MAX_COMPARISONS:,}")
            raise ValueError(f"Edit distance search too large: {num_source:,} x {num_target:,} = {total_comparisons:,} comparisons. Try using individual books instead of complete texts, or use lemma matching.")
        
        # Build stoplist from token frequencies if stoplist_size > 0
        stop_words = set()
        if stoplist_size > 0:
            token_freq = Counter()
            for unit in source_units:
                for token in unit.get('tokens', []):
                    if len(token) >= 3:
                        token_freq[normalize_greek(token)] += 1
            for unit in target_units:
                for token in unit.get('tokens', []):
                    if len(token) >= 3:
                        token_freq[normalize_greek(token)] += 1
            
            # Take top N most frequent tokens as stopwords
            most_common = token_freq.most_common(stoplist_size)
            stop_words = set(word for word, count in most_common)
            print(f"[EDIT_DISTANCE] Built stoplist with {len(stop_words)} words. Top 10: {list(stop_words)[:10]}")
        
        matches = []
        start_time = time.time()
        last_progress = 0
        
        for src_idx, src_unit in enumerate(source_units):
            progress = int((src_idx / num_source) * 100)
            if progress >= last_progress + 10:
                elapsed = time.time() - start_time
                print(f"[EDIT_DISTANCE] Progress: {progress}% ({src_idx}/{num_source} source units) - {elapsed:.1f}s elapsed")
                last_progress = progress
            
            src_tokens = [t for t in src_unit.get('tokens', []) 
                         if len(t) >= 3 and normalize_greek(t) not in stop_words]
            if not src_tokens:
                continue
            
            src_candidates = []
            for tgt_idx, tgt_unit in enumerate(target_units):
                tgt_tokens = [t for t in tgt_unit.get('tokens', []) 
                             if len(t) >= 3 and normalize_greek(t) not in stop_words]
                if not tgt_tokens:
                    continue
                
                fuzzy_matches = feature_extractor.find_fuzzy_matches(
                    src_tokens, tgt_tokens, threshold=int(min_similarity * 100)
                )
                
                unique_src = set(m['source_token'] for m in fuzzy_matches)
                unique_tgt = set(m['target_token'] for m in fuzzy_matches)
                num_unique_pairs = min(len(unique_src), len(unique_tgt))
                
                if num_unique_pairs >= min_matches:
                    avg_sim = sum(m['similarity'] for m in fuzzy_matches) / len(fuzzy_matches)
                    src_candidates.append((tgt_idx, tgt_tokens, fuzzy_matches, avg_sim, num_unique_pairs))
            
            src_candidates.sort(key=lambda x: (x[4], x[3]), reverse=True)
            for tgt_idx, tgt_tokens, fuzzy_matches, avg_sim, num_pairs in src_candidates[:top_n_per_source]:
                matches.append({
                    'source_idx': src_idx,
                    'target_idx': tgt_idx,
                    'matched_lemmas': [],
                    'match_basis': 'edit_distance',
                    'edit_score': avg_sim,
                    'num_matches': num_pairs,
                    'fuzzy_matches': fuzzy_matches[:8]
                })
        
        matches.sort(key=lambda x: (x.get('num_matches', 0), x.get('edit_score', 0)), reverse=True)
        
        if max_results > 0:
            matches = matches[:max_results]
        
        return matches, len(stop_words)
    
    def _get_feature_span(self, unit, matched_features, match_type):
        """Get the minimal span covering all matched features in a unit (V3-style)"""
        if match_type == 'exact':
            features = unit['tokens']
        else:
            features = unit['lemmas']
        
        positions = []
        for i, feat in enumerate(features):
            if feat in matched_features:
                positions.append(i)
        
        if len(positions) < 2:
            return 1
        
        span = max(positions) - min(positions)
        return max(span, 1)
