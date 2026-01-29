"""
Tesserae V6 - Feature Extractor
Extracts and scores additional features beyond lemma matching:
- Part of Speech (POS) matching (low weight, tie-breaker only)
- Edit distance (Levenshtein similarity) - boost or alternative mode
- Sound matching via character trigrams (alliteration, assonance, rhyme)
- Metrical scansion (hexameter patterns for Latin poetry)
"""
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from collections import defaultdict, Counter
import json
import os

DEFAULT_FEATURE_WEIGHTS = {
    'lemma': 1.0,
    'pos': 0.05,
    'edit_distance': 0.3,
    'sound': 0.4,
    'meter': 0.35,
    'syntax': 0.5,
    'bigram_boost': 0.5,
    'enabled_features': ['lemma', 'edit_distance', 'sound'],
    'fuzzy_threshold': 80,
    'trigram_threshold': 0.3
}

WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), 'feature_weights.json')

def load_feature_weights():
    """Load feature weights from JSON config file"""
    try:
        if os.path.exists(WEIGHTS_FILE):
            with open(WEIGHTS_FILE, 'r') as f:
                weights = json.load(f)
                for key in DEFAULT_FEATURE_WEIGHTS:
                    if key not in weights:
                        weights[key] = DEFAULT_FEATURE_WEIGHTS[key]
                return weights
    except Exception as e:
        print(f"Error loading feature weights: {e}")
    return DEFAULT_FEATURE_WEIGHTS.copy()

def save_feature_weights(weights):
    """Save feature weights to JSON config file"""
    try:
        with open(WEIGHTS_FILE, 'w') as f:
            json.dump(weights, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving feature weights: {e}")
        return False

class FeatureExtractor:
    def __init__(self):
        self.weights = load_feature_weights()
    
    def reload_weights(self):
        """Reload weights from config file"""
        self.weights = load_feature_weights()
    
    def get_weights(self):
        """Get current feature weights"""
        return self.weights.copy()
    
    def set_weights(self, new_weights):
        """Update and save feature weights"""
        self.weights.update(new_weights)
        return save_feature_weights(self.weights)
    
    def is_feature_enabled(self, feature_name):
        """Check if a feature is enabled"""
        return feature_name in self.weights.get('enabled_features', ['lemma'])
    
    def calculate_pos_score(self, source_unit, target_unit, matched_lemmas):
        """
        Calculate POS match score between source and target units.
        Returns score 0-1 based on how many matched lemmas share the same POS.
        """
        if not self.is_feature_enabled('pos'):
            return 0.0
        
        src_pos = source_unit.get('pos_tags', [])
        tgt_pos = target_unit.get('pos_tags', [])
        src_lemmas = source_unit.get('lemmas', [])
        tgt_lemmas = target_unit.get('lemmas', [])
        
        if not src_pos or not tgt_pos:
            return 0.0
        
        pos_matches = 0
        total_matches = 0
        
        for lemma in matched_lemmas:
            src_indices = [i for i, l in enumerate(src_lemmas) if l == lemma]
            tgt_indices = [i for i, l in enumerate(tgt_lemmas) if l == lemma]
            
            if src_indices and tgt_indices:
                src_idx = src_indices[0]
                tgt_idx = tgt_indices[0]
                
                if src_idx < len(src_pos) and tgt_idx < len(tgt_pos):
                    src_pos_tag = self._normalize_pos(src_pos[src_idx])
                    tgt_pos_tag = self._normalize_pos(tgt_pos[tgt_idx])
                    
                    if src_pos_tag == tgt_pos_tag:
                        pos_matches += 1
                    total_matches += 1
        
        if total_matches == 0:
            return 0.0
        
        return pos_matches / total_matches
    
    def _normalize_pos(self, pos_tag):
        """
        Normalize POS tags to broad categories for comparison.
        Different taggers use different schemes, so we normalize to:
        NOUN, VERB, ADJ, ADV, PREP, CONJ, PRON, OTHER
        """
        if not pos_tag:
            return 'OTHER'
        
        pos_tag = pos_tag.upper()
        
        if pos_tag.startswith('N') or pos_tag in ('NN', 'NNS', 'NNP', 'NNPS', 'NOUN'):
            return 'NOUN'
        elif pos_tag.startswith('V') or pos_tag in ('VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ', 'VERB'):
            return 'VERB'
        elif pos_tag.startswith('ADJ') or pos_tag in ('JJ', 'JJR', 'JJS'):
            return 'ADJ'
        elif pos_tag.startswith('ADV') or pos_tag in ('RB', 'RBR', 'RBS'):
            return 'ADV'
        elif pos_tag in ('IN', 'PREP', 'ADP'):
            return 'PREP'
        elif pos_tag in ('CC', 'CONJ', 'CCONJ', 'SCONJ'):
            return 'CONJ'
        elif pos_tag.startswith('PR') or pos_tag in ('PRP', 'PRP$', 'WP', 'WP$', 'PRON'):
            return 'PRON'
        elif pos_tag in ('DET', 'DT', 'WDT'):
            return 'DET'
        else:
            return 'OTHER'
    
    def calculate_edit_distance_score(self, source_unit, target_unit, matched_lemmas):
        """
        Calculate edit distance similarity for matched tokens.
        Returns score 0-1 based on character-level similarity.
        Useful for catching morphological variants and near-matches.
        """
        if not self.is_feature_enabled('edit_distance'):
            return 0.0
        
        src_tokens = source_unit.get('tokens', [])
        tgt_tokens = target_unit.get('tokens', [])
        src_lemmas = source_unit.get('lemmas', [])
        tgt_lemmas = target_unit.get('lemmas', [])
        
        if not src_tokens or not tgt_tokens:
            return 0.0
        
        total_similarity = 0.0
        count = 0
        
        for lemma in matched_lemmas:
            src_idx = next((i for i, l in enumerate(src_lemmas) if l == lemma), None)
            tgt_idx = next((i for i, l in enumerate(tgt_lemmas) if l == lemma), None)
            
            if src_idx is not None and tgt_idx is not None:
                if src_idx < len(src_tokens) and tgt_idx < len(tgt_tokens):
                    src_token = src_tokens[src_idx]
                    tgt_token = tgt_tokens[tgt_idx]
                    
                    similarity = fuzz.ratio(src_token, tgt_token) / 100.0
                    total_similarity += similarity
                    count += 1
        
        if count == 0:
            return 0.0
        
        return total_similarity / count
    
    def find_fuzzy_matches(self, source_tokens, target_tokens, threshold=None):
        """
        Find fuzzy matches between tokens using edit distance.
        Returns list of (src_token, tgt_token, similarity) tuples.
        Threshold is 0-100 (higher = more similar required).
        """
        if threshold is None:
            threshold = self.weights.get('fuzzy_threshold', 80)
        
        fuzzy_matches = []
        
        for src_token in source_tokens:
            if len(src_token) < 3:
                continue
            
            for tgt_token in target_tokens:
                if len(tgt_token) < 3:
                    continue
                
                similarity = fuzz.ratio(src_token, tgt_token)
                if similarity >= threshold and src_token != tgt_token:
                    fuzzy_matches.append({
                        'source_token': src_token,
                        'target_token': tgt_token,
                        'similarity': similarity / 100.0
                    })
        
        return fuzzy_matches
    
    def get_trigrams(self, token):
        """
        Extract character trigrams from a token.
        Returns set of 3-character sequences.
        """
        if len(token) < 3:
            return set()
        token = token.lower()
        return set(token[i:i+3] for i in range(len(token) - 2))
    
    def get_unit_trigrams(self, tokens):
        """
        Get all trigrams for a list of tokens.
        Returns dict mapping trigram -> list of tokens containing it.
        """
        trigram_index = defaultdict(list)
        for token in tokens:
            if len(token) < 3:
                continue
            for trigram in self.get_trigrams(token):
                trigram_index[trigram].append(token)
        return trigram_index
    
    def calculate_trigram_similarity(self, token1, token2):
        """
        Calculate Jaccard similarity between two tokens based on trigrams.
        Returns 0-1 score.
        """
        tri1 = self.get_trigrams(token1)
        tri2 = self.get_trigrams(token2)
        
        if not tri1 or not tri2:
            return 0.0
        
        intersection = len(tri1 & tri2)
        union = len(tri1 | tri2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_sound_matches(self, source_tokens, target_tokens, threshold=None):
        """
        Find sound-similar matches between tokens using trigram overlap.
        Captures alliteration, assonance, consonance, rhyme patterns.
        Returns list of match dicts with similarity scores.
        """
        if threshold is None:
            threshold = self.weights.get('trigram_threshold', 0.3)
        
        sound_matches = []
        
        for src_token in source_tokens:
            if len(src_token) < 3:
                continue
            src_trigrams = self.get_trigrams(src_token)
            if not src_trigrams:
                continue
            
            for tgt_token in target_tokens:
                if len(tgt_token) < 3:
                    continue
                
                similarity = self.calculate_trigram_similarity(src_token, tgt_token)
                
                if similarity >= threshold:
                    shared_trigrams = src_trigrams & self.get_trigrams(tgt_token)
                    sound_matches.append({
                        'source_token': src_token,
                        'target_token': tgt_token,
                        'similarity': similarity,
                        'shared_trigrams': list(shared_trigrams)[:5]
                    })
        
        return sound_matches
    
    def calculate_sound_score(self, source_unit, target_unit, matched_lemmas=None):
        """
        Calculate sound similarity score between source and target units.
        Uses trigram overlap as proxy for phonetic similarity.
        Returns 0-1 score.
        """
        src_tokens = source_unit.get('tokens', [])
        tgt_tokens = target_unit.get('tokens', [])
        
        if not src_tokens or not tgt_tokens:
            return 0.0
        
        src_tokens = [t for t in src_tokens if len(t) >= 3]
        tgt_tokens = [t for t in tgt_tokens if len(t) >= 3]
        
        if not src_tokens or not tgt_tokens:
            return 0.0
        
        total_similarity = 0.0
        count = 0
        
        for src_token in src_tokens:
            best_match = 0.0
            for tgt_token in tgt_tokens:
                sim = self.calculate_trigram_similarity(src_token, tgt_token)
                if sim > best_match:
                    best_match = sim
            if best_match > 0:
                total_similarity += best_match
                count += 1
        
        if count == 0:
            return 0.0
        
        return min(total_similarity / count, 1.0)
    
    def calculate_syntax_score(self, source_unit, target_unit, matched_lemmas, language='la'):
        """
        Calculate syntactic similarity between source and target units.
        Uses Universal Dependencies treebank data when available.
        Returns 0-1 score based on dependency pattern matching + syntax info.
        """
        try:
            from backend.syntax_parser import get_syntax_matcher
        except ImportError:
            from syntax_parser import get_syntax_matcher
        
        src_text = source_unit.get('text', '')
        tgt_text = target_unit.get('text', '')
        
        if not src_text or not tgt_text:
            return 0.0, None, None
        
        syntax_matcher = get_syntax_matcher()
        # Only use treebank data - Stanza is unreliable for classical poetry
        score, src_sent, tgt_sent, from_treebank = syntax_matcher.get_syntax_score(
            src_text, tgt_text, language, matched_lemmas, treebank_only=True
        )
        
        # If not from verified treebank data, don't return syntax info
        # This prevents showing unreliable Stanza parses
        if not from_treebank:
            return 0.0, None, None
        
        src_info = None
        tgt_info = None
        
        if src_sent:
            src_info = {
                'structure': list(src_sent.get_structure_signature()),
                'roles': {k: v['deprel'] for k, v in src_sent.get_lemma_roles().items()},
                'word_roles': {k: v['deprel'] for k, v in src_sent.get_all_word_roles().items()},
                'roles_set': list(src_sent.get_roles_set()),
                'from_treebank': True
            }
        if tgt_sent:
            tgt_info = {
                'structure': list(tgt_sent.get_structure_signature()),
                'roles': {k: v['deprel'] for k, v in tgt_sent.get_lemma_roles().items()},
                'word_roles': {k: v['deprel'] for k, v in tgt_sent.get_all_word_roles().items()},
                'roles_set': list(tgt_sent.get_roles_set()),
                'from_treebank': True
            }
        
        return score, src_info, tgt_info
    
    def calculate_meter_score(self, source_unit, target_unit, source_id='', target_id=''):
        """
        Calculate metrical similarity between source and target verses.
        Uses MQDQ pre-computed scansions when available, falls back to CLTK.
        Returns 0-1 score based on pattern matching + scansion info.
        """
        try:
            from backend.metrical_scanner import get_scansion_for_line, calculate_metrical_similarity
        except ImportError:
            from metrical_scanner import get_scansion_for_line, calculate_metrical_similarity
        
        src_text = source_unit.get('text', '')
        tgt_text = target_unit.get('text', '')
        src_ref = source_unit.get('ref', '')
        tgt_ref = target_unit.get('ref', '')
        
        if not src_text or not tgt_text:
            return 0.0, None, None
        
        # Use get_scansion_for_line which checks MQDQ first, then falls back to CLTK
        # Parse the locus to extract text_id and line_number
        src_scan = self._get_scansion_with_mqdq(src_ref, src_text, source_id)
        tgt_scan = self._get_scansion_with_mqdq(tgt_ref, tgt_text, target_id)
        
        if not src_scan or not tgt_scan:
            return 0.0, None, None
        
        similarity = calculate_metrical_similarity(
            src_scan.get('pattern', ''),
            tgt_scan.get('pattern', '')
        )
        
        return similarity, src_scan, tgt_scan
    
    def _get_scansion_with_mqdq(self, ref, text, text_id):
        """Helper to get scansion using MQDQ lookup first, then CLTK fallback."""
        try:
            from backend.metrical_scanner import get_scansion_for_line
        except ImportError:
            from metrical_scanner import get_scansion_for_line
        
        if not ref:
            return None
        
        ref_clean = ref.strip('<>').strip()
        
        # Extract line number from ref (e.g., "luc. 1.607" -> "1.607")
        parts = ref_clean.split()
        if len(parts) >= 2:
            line_num = parts[-1]  # Last part is typically the line number
        else:
            # Try splitting by period for refs like "luc.1.607"
            ref_parts = ref_clean.replace(' ', '').split('.')
            if len(ref_parts) >= 2:
                line_num = '.'.join(ref_parts[1:])  # Everything after author
            else:
                return None
        
        # Use text_id (filename) to construct author.work for lookup
        # text_id is like "lucan.bellum_civile.part.1.tess"
        if text_id:
            # Extract author.work from filename
            fname = text_id.replace('.tess', '')
            fname_parts = fname.split('.')
            if len(fname_parts) >= 2:
                # Handle "author.work.part.N" format
                if 'part' in fname_parts:
                    part_idx = fname_parts.index('part')
                    author_work = '.'.join(fname_parts[:part_idx])
                else:
                    author_work = '.'.join(fname_parts[:2])
                
                return get_scansion_for_line(author_work, line_num, text)
        
        return None
    
    def extract_features(self, source_unit, target_unit, matched_lemmas, settings=None, source_id='', target_id='', language='la'):
        """
        Extract all enabled features for a match pair.
        Returns dict with individual feature scores and combined weighted score.
        Respects per-request settings for which features are enabled.
        """
        settings = settings or {}
        use_pos = settings.get('use_pos', False)
        use_edit = settings.get('use_edit_distance', True)
        use_sound = settings.get('use_sound', True)
        use_meter = settings.get('use_meter', False)
        use_syntax = settings.get('use_syntax', False)
        
        features = {
            'lemma_count': len(matched_lemmas) if matched_lemmas else 0,
            'pos_score': 0.0,
            'edit_distance_score': 0.0,
            'sound_score': 0.0,
            'meter_score': 0.0,
            'syntax_score': 0.0,
            'source_scansion': None,
            'target_scansion': None,
            'source_syntax': None,
            'target_syntax': None,
            'combined_score': 0.0
        }
        
        if use_pos and matched_lemmas:
            features['pos_score'] = self.calculate_pos_score(
                source_unit, target_unit, matched_lemmas
            )
        
        if use_edit and matched_lemmas:
            features['edit_distance_score'] = self.calculate_edit_distance_score(
                source_unit, target_unit, matched_lemmas
            )
        
        if use_sound:
            features['sound_score'] = self.calculate_sound_score(
                source_unit, target_unit, matched_lemmas
            )
        
        if use_meter:
            meter_score, src_scan, tgt_scan = self.calculate_meter_score(
                source_unit, target_unit, source_id, target_id
            )
            features['meter_score'] = meter_score
            features['source_scansion'] = src_scan
            features['target_scansion'] = tgt_scan
        
        if use_syntax and matched_lemmas:
            syntax_score, src_syntax, tgt_syntax = self.calculate_syntax_score(
                source_unit, target_unit, matched_lemmas, language
            )
            features['syntax_score'] = syntax_score
            features['source_syntax'] = src_syntax
            features['target_syntax'] = tgt_syntax
        
        lemma_weight = self.weights.get('lemma', 1.0)
        pos_weight = self.weights.get('pos', 0.05) if use_pos else 0
        edit_weight = self.weights.get('edit_distance', 0.3) if use_edit else 0
        sound_weight = self.weights.get('sound', 0.4) if use_sound else 0
        meter_weight = self.weights.get('meter', 0.35) if use_meter else 0
        syntax_weight = self.weights.get('syntax', 0.5) if use_syntax else 0
        
        lemma_score = min(features['lemma_count'] / 5.0, 1.0) if features['lemma_count'] else 0
        
        total_weight = lemma_weight + pos_weight + edit_weight + sound_weight + meter_weight + syntax_weight
        if total_weight > 0:
            features['combined_score'] = min((
                lemma_weight * lemma_score +
                pos_weight * features['pos_score'] +
                edit_weight * features['edit_distance_score'] +
                sound_weight * features['sound_score'] +
                meter_weight * features['meter_score'] +
                syntax_weight * features['syntax_score']
            ) / total_weight, 1.0)
        
        return features
    
    def boost_score(self, base_score, features, settings=None):
        """
        Apply feature-based boost to base score.
        Returns adjusted score incorporating additional feature information.
        Respects per-request settings for which features are enabled.
        """
        if not features:
            return base_score
        
        settings = settings or {}
        boost = 1.0
        
        use_pos = settings.get('use_pos', False)
        use_edit = settings.get('use_edit_distance', True)
        use_sound = settings.get('use_sound', True)
        use_meter = settings.get('use_meter', False)
        use_syntax = settings.get('use_syntax', False)
        
        if use_pos and features.get('pos_score', 0) > 0.5:
            boost += 0.02 * features['pos_score']
        
        if use_edit and features.get('edit_distance_score', 0) > 0.7:
            boost += 0.1 * features['edit_distance_score']
        
        if use_sound and features.get('sound_score', 0) > 0.3:
            boost += 0.15 * features['sound_score']
        
        if use_meter and features.get('meter_score', 0) > 0.4:
            boost += 0.2 * features['meter_score']
        
        if use_syntax and features.get('syntax_score', 0) > 0.4:
            boost += 0.25 * features['syntax_score']
        
        result = base_score * boost
        return min(result, 1.0)


feature_extractor = FeatureExtractor()
