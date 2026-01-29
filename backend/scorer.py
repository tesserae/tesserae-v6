"""
Tesserae V6 - Scorer

Implements the V3-style scoring algorithm for ranking textual parallels.
Score combines word rarity (IDF) with proximity metrics (distance between matches).

Scoring Formula:
    score = sum(log(corpus_size / word_frequency)) / (1 + log(distance))
    
    Where:
    - Higher IDF (rarer words) = higher score
    - Shorter distance between matches = higher score
    - More matching words = higher score

Additional Features:
    - Bigram boost: Rewards co-occurring word pairs
    - POS matching: Part-of-speech alignment bonus
    - Edit distance: Morphological similarity scoring
    - Sound matching: Phonetic pattern recognition

Reference:
    Based on Coffee et al. (2012) "Intertextuality in the Digital Age"
    and the original Tesserae V3 implementation by Chris Forstall.
"""
from collections import Counter
import math
from backend.feature_extractor import feature_extractor
from backend.bigram_frequency import calculate_bigram_boost, is_bigram_cache_available

class Scorer:
    def __init__(self):
        self.corpus_frequencies = {}
    
    def build_corpus_frequencies(self, units_list):
        """Build corpus-wide frequency table from multiple texts"""
        all_lemmas = []
        for units in units_list:
            for unit in units:
                all_lemmas.extend(unit['lemmas'])
        self.corpus_frequencies = Counter(all_lemmas)
        return self.corpus_frequencies
    
    def get_text_frequencies(self, units):
        """Get frequency table for a single text"""
        all_lemmas = []
        for unit in units:
            all_lemmas.extend(unit['lemmas'])
        return Counter(all_lemmas)
    
    def score_matches(self, matches, source_units, target_units, settings=None, source_id='', target_id=''):
        """Score matches using V3-style algorithm with frequency and distance"""
        settings = settings or {}
        self._current_source_id = source_id
        self._current_target_id = target_id
        freq_basis = settings.get('frequency_source', 'texts')
        match_type = settings.get('match_type', 'lemma')
        
        if freq_basis == 'corpus' and self.corpus_frequencies:
            freq = self.corpus_frequencies
            total_words = sum(self.corpus_frequencies.values())
        else:
            # For exact match, use token frequencies; otherwise use lemma frequencies
            if match_type == 'exact':
                all_tokens = []
                for unit in source_units:
                    all_tokens.extend(unit.get('tokens', []))
                for unit in target_units:
                    all_tokens.extend(unit.get('tokens', []))
                freq = Counter(all_tokens)
                total_words = len(all_tokens)
            else:
                all_lemmas = []
                for unit in source_units:
                    all_lemmas.extend(unit['lemmas'])
                for unit in target_units:
                    all_lemmas.extend(unit['lemmas'])
                freq = Counter(all_lemmas)
                total_words = len(all_lemmas)
        
        results = []
        
        for match in matches:
            src_unit = source_units[match['source_idx']]
            tgt_unit = target_units[match['target_idx']]
            matched_lemmas = match.get('matched_lemmas', [])
            match_basis = match.get('match_basis', 'lemma')
            
            if match_basis == 'sound' or match_type == 'sound':
                result = self._score_sound_match(match, src_unit, tgt_unit, settings)
                results.append(result)
            elif match_basis == 'edit_distance' or match_type == 'edit_distance':
                result = self._score_edit_distance_match(match, src_unit, tgt_unit, settings)
                results.append(result)
            elif match_basis == 'semantic_cross' or match_type == 'semantic_cross':
                result = self._score_crosslingual_match(match, src_unit, tgt_unit, settings)
                if result is not None:
                    results.append(result)
            elif match_basis == 'dictionary_cross' or match_type == 'dictionary_cross':
                result = self._score_dictionary_crosslingual_match(match, src_unit, tgt_unit, settings)
                if result is not None:
                    results.append(result)
            elif match_basis == 'semantic' or match_type == 'semantic':
                result = self._score_semantic_match(match, src_unit, tgt_unit, settings)
                if result is not None:
                    results.append(result)
            else:
                src_distance = self._calculate_distance(src_unit, matched_lemmas, freq)
                tgt_distance = self._calculate_distance(tgt_unit, matched_lemmas, freq)
                
                word_scores = []
                total_freq_score = 0
                
                src_highlight_indices = []
                tgt_highlight_indices = []
                
                # For exact match, compare against tokens; for lemma match, compare against lemmas
                if match_type == 'exact':
                    # Use normalized tokens for comparison
                    src_tokens = src_unit.get('tokens', [])
                    tgt_tokens = tgt_unit.get('tokens', [])
                    for i, token in enumerate(src_tokens):
                        if token in matched_lemmas or token.lower() in matched_lemmas:
                            src_highlight_indices.append(i)
                    for i, token in enumerate(tgt_tokens):
                        if token in matched_lemmas or token.lower() in matched_lemmas:
                            tgt_highlight_indices.append(i)
                else:
                    for i, lemma in enumerate(src_unit['lemmas']):
                        if lemma in matched_lemmas:
                            src_highlight_indices.append(i)
                    for i, lemma in enumerate(tgt_unit['lemmas']):
                        if lemma in matched_lemmas:
                            tgt_highlight_indices.append(i)
                
                for lemma in matched_lemmas:
                    lemma_freq = freq.get(lemma, 1)
                    idf = math.log((total_words + 1) / (lemma_freq + 1)) + 1
                    word_scores.append({
                        'lemma': lemma,
                        'frequency': lemma_freq,
                        'idf': idf
                    })
                    total_freq_score += idf
                
                distance_penalty = (src_distance + tgt_distance) / 2
                if distance_penalty > 0:
                    distance_factor = 1.0 / math.log(distance_penalty + 1)
                else:
                    distance_factor = 1.0
                
                raw_score = total_freq_score * distance_factor
                
                max_score = len(matched_lemmas) * math.log(total_words + 1) if total_words > 0 else 1
                normalized_score = min(raw_score / max_score, 1.0) if max_score > 0 else 0
                
                features = feature_extractor.extract_features(
                    src_unit, tgt_unit, matched_lemmas, settings,
                    source_id=self._current_source_id, target_id=self._current_target_id
                )
                
                boosted_score = feature_extractor.boost_score(normalized_score, features, settings)
                
                language = settings.get('language', 'la')
                bigram_boost = 0.0
                shared_rare_bigrams = []
                use_bigram_boost = settings.get('bigram_boost', False)
                if use_bigram_boost and is_bigram_cache_available(language):
                    bigram_weight = feature_extractor.weights.get('bigram_boost', 0.5)
                    src_lemmas = src_unit.get('lemmas', [])
                    tgt_lemmas = tgt_unit.get('lemmas', [])
                    bigram_boost = calculate_bigram_boost(src_lemmas, tgt_lemmas, language, bigram_weight)
                    if bigram_boost > 0:
                        boosted_score += bigram_boost
                        from backend.bigram_frequency import find_shared_rare_bigrams
                        rare_bgs = find_shared_rare_bigrams(src_lemmas, tgt_lemmas, language, min_rarity=0.8)
                        shared_rare_bigrams = [{'bigram': bg.replace('|', ' + '), 'rarity': round(r, 3)} for bg, r in rare_bgs]
                
                features['bigram_boost'] = bigram_boost
                features['shared_rare_bigrams'] = shared_rare_bigrams
                
                results.append({
                    'source': {
                        'ref': src_unit['ref'],
                        'text': src_unit['text'],
                        'tokens': src_unit['tokens'],
                        'highlight_indices': src_highlight_indices
                    },
                    'target': {
                        'ref': tgt_unit['ref'],
                        'text': tgt_unit['text'],
                        'tokens': tgt_unit['tokens'],
                        'highlight_indices': tgt_highlight_indices
                    },
                    'matched_words': word_scores,
                    'source_distance': src_distance,
                    'target_distance': tgt_distance,
                    'overall_score': boosted_score,
                    'base_score': normalized_score,
                    'features': features
                })
        
        return results
    
    def _score_sound_match(self, match, src_unit, tgt_unit, settings):
        """Score a sound-based match (trigram similarity)"""
        sound_score = match.get('sound_score', 0)
        shared_trigrams = match.get('shared_trigrams', [])
        trigram_tokens = match.get('trigram_tokens', {})
        
        src_highlight_indices = []
        tgt_highlight_indices = []
        
        for tri, (src_token, tgt_token) in trigram_tokens.items():
            for i, token in enumerate(src_unit['tokens']):
                if tri in token.lower() and i not in src_highlight_indices:
                    src_highlight_indices.append(i)
            for i, token in enumerate(tgt_unit['tokens']):
                if tri in token.lower() and i not in tgt_highlight_indices:
                    tgt_highlight_indices.append(i)
        
        word_scores = []
        for tri in shared_trigrams[:8]:
            if tri in trigram_tokens:
                src_tok, tgt_tok = trigram_tokens[tri]
                word_scores.append({
                    'lemma': f"[{tri}] {src_tok}~{tgt_tok}",
                    'frequency': 0,
                    'idf': 0,
                    'trigram': tri
                })
            else:
                word_scores.append({
                    'lemma': f"[{tri}]",
                    'frequency': 0,
                    'idf': 0,
                    'trigram': tri
                })
        
        features = {
            'lemma_count': 0,
            'pos_score': 0.0,
            'edit_distance_score': 0.0,
            'sound_score': sound_score,
            'combined_score': sound_score
        }
        
        return {
            'source': {
                'ref': src_unit['ref'],
                'text': src_unit['text'],
                'tokens': src_unit['tokens'],
                'highlight_indices': src_highlight_indices
            },
            'target': {
                'ref': tgt_unit['ref'],
                'text': tgt_unit['text'],
                'tokens': tgt_unit['tokens'],
                'highlight_indices': tgt_highlight_indices
            },
            'matched_words': word_scores,
            'shared_trigrams': shared_trigrams,
            'source_distance': 1,
            'target_distance': 1,
            'overall_score': sound_score,
            'base_score': sound_score,
            'features': features,
            'match_basis': 'sound'
        }
    
    def _score_edit_distance_match(self, match, src_unit, tgt_unit, settings):
        """Score an edit-distance-based match (fuzzy string matching)"""
        edit_score = match.get('edit_score', 0)
        fuzzy_matches = match.get('fuzzy_matches', [])
        
        src_highlight_indices = []
        tgt_highlight_indices = []
        
        for fm in fuzzy_matches:
            src_token = fm.get('source_token', '')
            tgt_token = fm.get('target_token', '')
            for i, token in enumerate(src_unit['tokens']):
                if token == src_token and i not in src_highlight_indices:
                    src_highlight_indices.append(i)
                    break
            for i, token in enumerate(tgt_unit['tokens']):
                if token == tgt_token and i not in tgt_highlight_indices:
                    tgt_highlight_indices.append(i)
                    break
        
        word_scores = []
        for fm in fuzzy_matches[:8]:
            similarity = fm.get('similarity', 0)
            pct = int(similarity * 100)
            word_scores.append({
                'lemma': f"{fm['source_token']}~{fm['target_token']} ({pct}%)",
                'frequency': 0,
                'idf': 0,
                'similarity': similarity
            })
        
        features = {
            'lemma_count': 0,
            'pos_score': 0.0,
            'edit_distance_score': edit_score,
            'sound_score': 0.0,
            'combined_score': edit_score
        }
        
        return {
            'source': {
                'ref': src_unit['ref'],
                'text': src_unit['text'],
                'tokens': src_unit['tokens'],
                'highlight_indices': src_highlight_indices
            },
            'target': {
                'ref': tgt_unit['ref'],
                'text': tgt_unit['text'],
                'tokens': tgt_unit['tokens'],
                'highlight_indices': tgt_highlight_indices
            },
            'matched_words': word_scores,
            'source_distance': 1,
            'target_distance': 1,
            'overall_score': edit_score,
            'base_score': edit_score,
            'features': features,
            'match_basis': 'edit_distance'
        }
    
    def _score_semantic_match(self, match, src_unit, tgt_unit, settings):
        """
        Score a semantic similarity match.
        Uses the pre-computed semantic similarity from SPhilBERTa embeddings.
        Also detects synonym pairs for word-level highlighting.
        
        Filtering: Stopwords (et, in, ad, etc.) are excluded from matches.
        Results require either 2+ content word matches or high similarity score (>0.92).
        """
        from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS, DEFAULT_ENGLISH_STOP_WORDS
        
        semantic_score = match.get('semantic_score', 0.5)
        language = settings.get('language', 'la')
        
        if language == 'la':
            stopwords = DEFAULT_LATIN_STOP_WORDS
        elif language == 'grc':
            stopwords = DEFAULT_GREEK_STOP_WORDS
        else:
            stopwords = DEFAULT_ENGLISH_STOP_WORDS
        
        source_tokens = src_unit.get('tokens', [])
        target_tokens = tgt_unit.get('tokens', [])
        source_lemmas = src_unit.get('lemmas', [])
        target_lemmas = tgt_unit.get('lemmas', [])
        
        matched_words = []
        source_highlights = []
        target_highlights = []
        content_match_count = 0
        
        source_lemma_lower = [l.lower() for l in source_lemmas]
        target_lemma_lower = [l.lower() for l in target_lemmas]
        
        for src_idx, src_lemma in enumerate(source_lemma_lower):
            if src_lemma in target_lemma_lower:
                if src_lemma in stopwords or len(src_lemma) <= 2:
                    continue
                
                tgt_idx = target_lemma_lower.index(src_lemma)
                source_highlights.append(src_idx)
                target_highlights.append(tgt_idx)
                
                src_token = source_tokens[src_idx] if src_idx < len(source_tokens) else src_lemma
                tgt_token = target_tokens[tgt_idx] if tgt_idx < len(target_tokens) else target_lemmas[tgt_idx]
                
                if not any(m.get('lemma') == source_lemmas[src_idx] for m in matched_words):
                    matched_words.append({
                        'lemma': source_lemmas[src_idx],
                        'source_word': src_token,
                        'target_word': tgt_token,
                        'type': 'exact',
                        'similarity': 1.0
                    })
                    content_match_count += 1
        
        try:
            from backend.synonym_dict import find_synonym_pairs_in_passages
            synonym_pairs = find_synonym_pairs_in_passages(source_lemmas, target_lemmas, language)
            
            for pair in synonym_pairs:
                src_lemma_lower = pair['source_lemma'].lower()
                tgt_lemma_lower = pair['target_lemma'].lower()
                if src_lemma_lower in stopwords or tgt_lemma_lower in stopwords:
                    continue
                if len(src_lemma_lower) <= 2 or len(tgt_lemma_lower) <= 2:
                    continue
                
                for idx in pair['source_indices']:
                    if idx not in source_highlights:
                        source_highlights.append(idx)
                for idx in pair['target_indices']:
                    if idx not in target_highlights:
                        target_highlights.append(idx)
                
                src_token = source_tokens[pair['source_indices'][0]] if pair['source_indices'] and pair['source_indices'][0] < len(source_tokens) else pair['source_lemma']
                tgt_token = target_tokens[pair['target_indices'][0]] if pair['target_indices'] and pair['target_indices'][0] < len(target_tokens) else pair['target_lemma']
                
                matched_words.append({
                    'lemma': f"{pair['source_lemma']}≈{pair['target_lemma']}",
                    'source_word': src_token,
                    'target_word': tgt_token,
                    'type': 'synonym',
                    'display': f"{pair['source_lemma']}≈{pair['target_lemma']}"
                })
                content_match_count += 1
        except Exception as e:
            print(f"Warning: Could not find synonyms: {e}")
        
        min_content_matches = settings.get('min_semantic_matches', 2)
        semantic_only_threshold = settings.get('semantic_only_threshold', 0.92)
        
        if content_match_count < min_content_matches and semantic_score < semantic_only_threshold:
            return None
        
        if not matched_words:
            matched_words = [{
                'type': 'semantic',
                'similarity': semantic_score,
                'display': f'Conceptual similarity ({int(semantic_score*100)}%)',
                'lemma': 'semantic'
            }]
        
        features = {
            'lemma_count': len([m for m in matched_words if m.get('type') == 'exact']),
            'pos_score': 0.0,
            'edit_distance_score': 0.0,
            'sound_score': 0.0,
            'semantic_score': semantic_score,
            'combined_score': semantic_score
        }
        
        return {
            'source': {
                'ref': src_unit['ref'],
                'text': src_unit['text'],
                'tokens': source_tokens,
                'highlight_indices': source_highlights
            },
            'target': {
                'ref': tgt_unit['ref'],
                'text': tgt_unit['text'],
                'tokens': target_tokens,
                'highlight_indices': target_highlights
            },
            'matched_words': matched_words,
            'source_distance': 0,
            'target_distance': 0,
            'overall_score': semantic_score,
            'base_score': semantic_score,
            'features': features,
            'match_basis': 'semantic'
        }
    
    def _score_crosslingual_match(self, match, src_unit, tgt_unit, settings):
        """
        Score a cross-lingual semantic similarity match (Greek ↔ Latin).
        Uses pre-computed SPhilBERTa cross-lingual similarity score.
        Also uses V3's Greek-Latin dictionary for word-level highlighting.
        """
        from backend.synonym_dict import find_greek_latin_matches
        
        semantic_score = match.get('semantic_score', 0.5)
        
        source_tokens = src_unit.get('tokens', [])
        target_tokens = tgt_unit.get('tokens', [])
        source_lemmas = src_unit.get('lemmas', [])
        target_lemmas = tgt_unit.get('lemmas', [])
        
        source_highlights = []
        target_highlights = []
        matched_words = []
        
        try:
            gl_matches = find_greek_latin_matches(source_lemmas, target_lemmas)
            for m in gl_matches:
                for idx in m.get('greek_indices', []):
                    if idx not in source_highlights:
                        source_highlights.append(idx)
                for idx in m.get('latin_indices', []):
                    if idx not in target_highlights:
                        target_highlights.append(idx)
                
                grc_word = source_tokens[m['greek_indices'][0]] if m['greek_indices'] and m['greek_indices'][0] < len(source_tokens) else m['greek_lemma']
                lat_word = target_tokens[m['latin_indices'][0]] if m['latin_indices'] and m['latin_indices'][0] < len(target_tokens) else m['latin_lemma']
                
                matched_words.append({
                    'type': 'cross_lingual',
                    'greek_lemma': m['greek_lemma'],
                    'latin_lemma': m['latin_lemma'],
                    'greek_word': grc_word,
                    'latin_word': lat_word,
                    'display': f"{m['greek_lemma']} → {m['latin_lemma']}"
                })
        except Exception as e:
            print(f"Warning: Could not find Greek-Latin matches: {e}")
        
        if not matched_words:
            matched_words = [{
                'type': 'semantic_cross',
                'similarity': semantic_score,
                'display': f'Semantic similarity ({int(semantic_score*100)}%)',
                'lemma': 'semantic_cross'
            }]
        
        features = {
            'lemma_count': len(matched_words),
            'pos_score': 0.0,
            'edit_distance_score': 0.0,
            'sound_score': 0.0,
            'semantic_score': semantic_score,
            'combined_score': semantic_score
        }
        
        return {
            'source': {
                'ref': src_unit['ref'],
                'text': src_unit['text'],
                'tokens': source_tokens,
                'highlight_indices': source_highlights
            },
            'target': {
                'ref': tgt_unit['ref'],
                'text': tgt_unit['text'],
                'tokens': target_tokens,
                'highlight_indices': target_highlights
            },
            'matched_words': matched_words,
            'source_distance': 0,
            'target_distance': 0,
            'overall_score': semantic_score,
            'base_score': semantic_score,
            'features': features,
            'match_basis': 'semantic_cross'
        }
    
    def _score_dictionary_crosslingual_match(self, match, src_unit, tgt_unit, settings):
        """
        Score a dictionary-based cross-lingual match (Greek ↔ Latin).
        Uses V3's Greek-Latin dictionary for word-level matching and highlighting.
        """
        source_tokens = src_unit.get('tokens', [])
        target_tokens = tgt_unit.get('tokens', [])
        
        word_matches = match.get('word_matches', [])
        match_count = match.get('match_count', len(word_matches))
        
        source_highlights = []
        target_highlights = []
        matched_words = []
        
        for m in word_matches:
            for idx in m.get('greek_indices', []):
                if idx not in source_highlights:
                    source_highlights.append(idx)
            for idx in m.get('latin_indices', []):
                if idx not in target_highlights:
                    target_highlights.append(idx)
            
            grc_word = source_tokens[m['greek_indices'][0]] if m.get('greek_indices') and m['greek_indices'][0] < len(source_tokens) else m.get('greek_lemma', '')
            lat_word = target_tokens[m['latin_indices'][0]] if m.get('latin_indices') and m['latin_indices'][0] < len(target_tokens) else m.get('latin_lemma', '')
            
            matched_words.append({
                'type': 'cross_lingual',
                'greek_lemma': m.get('greek_lemma', ''),
                'latin_lemma': m.get('latin_lemma', ''),
                'greek_word': grc_word,
                'latin_word': lat_word,
                'display': f"{m.get('greek_lemma', '')} → {m.get('latin_lemma', '')}"
            })
        
        score = match_count / max(len(source_tokens), len(target_tokens), 1)
        
        features = {
            'lemma_count': match_count,
            'pos_score': 0.0,
            'edit_distance_score': 0.0,
            'sound_score': 0.0,
            'semantic_score': 0.0,
            'combined_score': score
        }
        
        return {
            'source': {
                'ref': src_unit['ref'],
                'text': src_unit['text'],
                'tokens': source_tokens,
                'highlight_indices': source_highlights
            },
            'target': {
                'ref': tgt_unit['ref'],
                'text': tgt_unit['text'],
                'tokens': target_tokens,
                'highlight_indices': target_highlights
            },
            'matched_words': matched_words,
            'source_distance': 0,
            'target_distance': 0,
            'overall_score': score,
            'base_score': score,
            'features': features,
            'match_basis': 'dictionary_cross',
            'match_count': match_count
        }
    
    def _calculate_distance(self, unit, matched_lemmas, freq):
        """Calculate minimal window spanning all matched lemmas (V3-style)
        Returns the smallest span that contains at least one instance of each matched lemma
        """
        lemmas = unit['lemmas']
        
        all_positions = []
        for i, lemma in enumerate(lemmas):
            if lemma in matched_lemmas:
                all_positions.append(i)
        
        if len(all_positions) < 2:
            return 1
        
        min_pos = min(all_positions)
        max_pos = max(all_positions)
        span = max_pos - min_pos
        
        return max(span, 1)
