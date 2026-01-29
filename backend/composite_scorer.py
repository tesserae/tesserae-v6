"""
Tesserae V6 - Composite Scoring System

Multi-signal correlation for high-precision parallel detection.
Combines lemma, semantic, sound, and edit distance matching with high thresholds,
then ranks parallels by how many signals confirm the connection.

Confidence Tiers (4-signal system):
- GOLD: 4 signals (all) - highest confidence
- SILVER: 3 signals - high confidence  
- BRONZE: 2 signals - moderate confidence
- COPPER: 1 signal - low confidence

This module is designed for batch processing and visualization,
where precision matters more than recall.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import json


class ConfidenceTier(Enum):
    """Confidence tier based on number of confirming signals"""
    GOLD = 4    # All four signals (lemma + semantic + sound + edit_distance)
    SILVER = 3  # Three signals
    BRONZE = 2  # Two signals
    COPPER = 1  # One signal
    NONE = 0    # Below thresholds


@dataclass
class CompositeThresholds:
    """
    Thresholds for each match type.
    Only parallels meeting these thresholds are included.
    Values should be calibrated against known scholarly parallels.
    """
    lemma_min_score: float = 7.0           # V3 score threshold (typically 0-15 range)
    semantic_min_score: float = 0.7        # Cosine similarity threshold (0-1)
    sound_min_score: float = 0.6           # Trigram Jaccard threshold (0-1)
    edit_distance_min_score: float = 0.5   # Normalized edit distance similarity (0-1)
    lemma_min_matches: int = 2             # Minimum shared lemmas
    
    def to_dict(self) -> dict:
        return {
            'lemma_min_score': self.lemma_min_score,
            'semantic_min_score': self.semantic_min_score,
            'sound_min_score': self.sound_min_score,
            'edit_distance_min_score': self.edit_distance_min_score,
            'lemma_min_matches': self.lemma_min_matches
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CompositeThresholds':
        return cls(
            lemma_min_score=data.get('lemma_min_score', 7.0),
            semantic_min_score=data.get('semantic_min_score', 0.7),
            sound_min_score=data.get('sound_min_score', 0.6),
            edit_distance_min_score=data.get('edit_distance_min_score', 0.5),
            lemma_min_matches=data.get('lemma_min_matches', 2)
        )


@dataclass
class NormalizedMatch:
    """
    Normalized match format for correlation across match types.
    All match types are converted to this format before correlation.
    """
    source_unit_ref: str      # e.g., "Aen. 1.1" or unit index as string
    target_unit_ref: str      # e.g., "Met. 1.1" or unit index as string
    source_text: str          # Actual text content
    target_text: str          # Actual text content
    match_type: str           # 'lemma', 'semantic', or 'sound'
    score: float              # Normalized score for this match type
    match_count: int = 0      # Number of matched items (lemmas, trigrams, etc.)
    extra_data: Dict = field(default_factory=dict)  # Match-type-specific data


@dataclass
class CompositeMatch:
    """
    A parallel that may have multiple confirming signals.
    """
    source_text_id: str        # e.g., "vergil.aeneid.part.1"
    target_text_id: str        # e.g., "ovid.metamorphoses.part.1"
    source_unit_ref: str       # Line/phrase reference
    target_unit_ref: str       # Line/phrase reference
    source_snippet: str        # Actual text
    target_snippet: str        # Actual text
    
    # Individual signal scores (None if not computed or below threshold)
    lemma_score: Optional[float] = None
    lemma_matches: Optional[int] = None
    semantic_score: Optional[float] = None
    sound_score: Optional[float] = None
    edit_distance_score: Optional[float] = None
    
    # Which signals confirmed this parallel
    signals: Set[str] = field(default_factory=set)  # {'lemma', 'semantic', 'sound', 'edit_distance'}
    
    @property
    def confidence_tier(self) -> ConfidenceTier:
        """Get confidence tier based on number of signals"""
        count = len(self.signals)
        if count >= 4:
            return ConfidenceTier.GOLD
        elif count == 3:
            return ConfidenceTier.SILVER
        elif count == 2:
            return ConfidenceTier.BRONZE
        elif count == 1:
            return ConfidenceTier.COPPER
        return ConfidenceTier.NONE
    
    @property
    def composite_score(self) -> float:
        """
        Combined score for ranking within tiers.
        Weights: lemma (normalized to 0-1) + semantic + sound + edit_distance
        """
        score = 0.0
        if self.lemma_score is not None:
            score += min(self.lemma_score / 10.0, 1.0)  # Normalize lemma score
        if self.semantic_score is not None:
            score += self.semantic_score
        if self.sound_score is not None:
            score += self.sound_score
        if self.edit_distance_score is not None:
            score += self.edit_distance_score
        return score
    
    def to_dict(self) -> dict:
        return {
            'source_text_id': self.source_text_id,
            'target_text_id': self.target_text_id,
            'source_unit_ref': self.source_unit_ref,
            'target_unit_ref': self.target_unit_ref,
            'source_snippet': self.source_snippet,
            'target_snippet': self.target_snippet,
            'lemma_score': self.lemma_score,
            'lemma_matches': self.lemma_matches,
            'semantic_score': self.semantic_score,
            'sound_score': self.sound_score,
            'edit_distance_score': self.edit_distance_score,
            'signals': list(self.signals),
            'confidence_tier': self.confidence_tier.name,
            'composite_score': self.composite_score
        }


# ============================================================================
# ADAPTERS: Convert existing match formats to normalized format
# ============================================================================

def normalize_lemma_matches(
    scored_matches: List[Dict],
    source_units: List[Dict],
    target_units: List[Dict],
    thresholds: CompositeThresholds
) -> List[NormalizedMatch]:
    """
    Normalize scored lemma matches to common format.
    
    Input format (from scorer.score_matches):
    {
        'source': {'ref': str, 'text': str, ...},
        'target': {'ref': str, 'text': str, ...},
        'overall_score': float,
        'matched_words': [{'lemma': str, ...}],
        ...
    }
    
    Also handles pre-scored format with indices:
    {
        'source_idx': int,
        'target_idx': int,
        'matched_lemmas': [...],
        ...
    }
    """
    normalized = []
    
    for idx, m in enumerate(scored_matches):
        score = m.get('overall_score', m.get('base_score', 0))
        matched_words = m.get('matched_words', [])
        match_count = len(matched_words) if matched_words else len(m.get('matched_lemmas', []))
        
        # Apply thresholds
        if score < thresholds.lemma_min_score:
            continue
        if match_count < thresholds.lemma_min_matches:
            continue
        
        # Handle post-scored format (with source/target dicts)
        if 'source' in m and 'target' in m:
            source = m.get('source', {})
            target = m.get('target', {})
            source_ref = source.get('ref', '')
            target_ref = target.get('ref', '')
            source_text = source.get('text', '')
            target_text = target.get('text', '')
        # Handle pre-scored format (with indices)
        elif 'source_idx' in m and 'target_idx' in m:
            src_idx = m['source_idx']
            tgt_idx = m['target_idx']
            if src_idx < len(source_units) and tgt_idx < len(target_units):
                src_unit = source_units[src_idx]
                tgt_unit = target_units[tgt_idx]
                source_ref = src_unit.get('ref', f'idx:{src_idx}')
                target_ref = tgt_unit.get('ref', f'idx:{tgt_idx}')
                source_text = src_unit.get('text', '')
                target_text = tgt_unit.get('text', '')
            else:
                continue
        else:
            continue
        
        # Ensure we have valid refs for correlation (fallback to match index)
        if not source_ref:
            source_ref = f'match:{idx}:src'
        if not target_ref:
            target_ref = f'match:{idx}:tgt'
        
        normalized.append(NormalizedMatch(
            source_unit_ref=source_ref,
            target_unit_ref=target_ref,
            source_text=source_text,
            target_text=target_text,
            match_type='lemma',
            score=score,
            match_count=match_count,
            extra_data={
                'matched_lemmas': [w.get('lemma', '') for w in matched_words] if matched_words else m.get('matched_lemmas', []),
                'base_score': m.get('base_score', 0),
                'features': m.get('features', {})
            }
        ))
    
    return normalized


def normalize_semantic_matches(
    matches: List[Dict],
    source_units: List[Dict],
    target_units: List[Dict],
    thresholds: CompositeThresholds
) -> List[NormalizedMatch]:
    """
    Normalize semantic matches to common format.
    
    Input format (from find_semantic_matches, before scoring):
    {
        'source_idx': int,
        'target_idx': int,
        'semantic_score': float,
        'match_basis': 'semantic'
    }
    
    OR (after scoring):
    {
        'source': {'ref': str, 'text': str},
        'target': {'ref': str, 'text': str},
        'overall_score': float,
        'semantic_score': float
    }
    """
    normalized = []
    
    for idx, m in enumerate(matches):
        # Handle both pre-scored (with idx) and post-scored (with source/target) formats
        if 'source_idx' in m:
            # Pre-scored format
            src_idx = m['source_idx']
            tgt_idx = m['target_idx']
            
            if src_idx >= len(source_units) or tgt_idx >= len(target_units):
                continue
                
            src_unit = source_units[src_idx]
            tgt_unit = target_units[tgt_idx]
            
            score = m.get('semantic_score', 0)
            source_ref = src_unit.get('ref', f'idx:{src_idx}')
            target_ref = tgt_unit.get('ref', f'idx:{tgt_idx}')
            source_text = src_unit.get('text', '')
            target_text = tgt_unit.get('text', '')
        elif 'source' in m and 'target' in m:
            # Post-scored format
            source = m.get('source', {})
            target = m.get('target', {})
            score = m.get('semantic_score', m.get('overall_score', 0))
            source_ref = source.get('ref', '')
            target_ref = target.get('ref', '')
            source_text = source.get('text', '')
            target_text = target.get('text', '')
        else:
            continue
        
        # Apply threshold
        if score < thresholds.semantic_min_score:
            continue
        
        # Ensure valid refs for correlation
        if not source_ref:
            source_ref = f'sem:{idx}:src'
        if not target_ref:
            target_ref = f'sem:{idx}:tgt'
        
        normalized.append(NormalizedMatch(
            source_unit_ref=source_ref,
            target_unit_ref=target_ref,
            source_text=source_text,
            target_text=target_text,
            match_type='semantic',
            score=score,
            match_count=1,  # Semantic is unit-to-unit
            extra_data={'semantic_score': score}
        ))
    
    return normalized


def normalize_sound_matches(
    matches: List[Dict],
    source_units: List[Dict],
    target_units: List[Dict],
    thresholds: CompositeThresholds
) -> List[NormalizedMatch]:
    """
    Normalize sound matches to common format.
    
    Input format (from find_sound_matches, before scoring):
    {
        'source_idx': int,
        'target_idx': int,
        'sound_score': float,
        'shared_trigrams': [...],
        'match_basis': 'sound'
    }
    
    OR (after scoring from scorer._score_sound_match):
    {
        'source': {'ref': str, 'text': str},
        'target': {'ref': str, 'text': str},
        'overall_score': float,
        'matched_words': [{'lemma': '[tri] tok~tok', 'trigram': 'tri'}, ...]
    }
    """
    normalized = []
    
    for idx, m in enumerate(matches):
        # Handle both pre-scored and post-scored formats
        if 'source_idx' in m:
            # Pre-scored format (from matcher.find_sound_matches)
            src_idx = m['source_idx']
            tgt_idx = m['target_idx']
            
            if src_idx >= len(source_units) or tgt_idx >= len(target_units):
                continue
                
            src_unit = source_units[src_idx]
            tgt_unit = target_units[tgt_idx]
            
            score = m.get('sound_score', 0)
            source_ref = src_unit.get('ref', f'idx:{src_idx}')
            target_ref = tgt_unit.get('ref', f'idx:{tgt_idx}')
            source_text = src_unit.get('text', '')
            target_text = tgt_unit.get('text', '')
            shared_trigrams = m.get('shared_trigrams', [])
            trigram_count = len(shared_trigrams) if isinstance(shared_trigrams, list) else 0
        elif 'source' in m and 'target' in m:
            # Post-scored format (from scorer._score_sound_match)
            source = m.get('source', {})
            target = m.get('target', {})
            score = m.get('overall_score', m.get('sound_score', 0))
            source_ref = source.get('ref', '')
            target_ref = target.get('ref', '')
            source_text = source.get('text', '')
            target_text = target.get('text', '')
            
            # Extract trigrams from matched_words (scorer format: [{'trigram': 'abc', ...}])
            matched_words = m.get('matched_words', [])
            if matched_words and isinstance(matched_words, list):
                shared_trigrams = [w.get('trigram', '') for w in matched_words if w.get('trigram')]
                trigram_count = len(shared_trigrams)
            else:
                shared_trigrams = []
                trigram_count = 0
        else:
            continue
        
        # Apply threshold
        if score < thresholds.sound_min_score:
            continue
        
        # Ensure valid refs for correlation
        if not source_ref:
            source_ref = f'snd:{idx}:src'
        if not target_ref:
            target_ref = f'snd:{idx}:tgt'
        
        normalized.append(NormalizedMatch(
            source_unit_ref=source_ref,
            target_unit_ref=target_ref,
            source_text=source_text,
            target_text=target_text,
            match_type='sound',
            score=score,
            match_count=trigram_count,
            extra_data={'shared_trigrams': shared_trigrams}
        ))
    
    return normalized


def normalize_edit_distance_matches(
    matches: List[Dict],
    source_units: List[Dict],
    target_units: List[Dict],
    thresholds: CompositeThresholds
) -> List[NormalizedMatch]:
    """
    Normalize edit distance matches to common format.
    
    Input format (from matcher.find_edit_distance_matches or scorer):
    {
        'source_idx': int,
        'target_idx': int,
        'edit_distance_score': float,  # Normalized similarity (0-1)
        'edit_distance': int,           # Raw Levenshtein distance
        ...
    }
    
    OR (after scoring):
    {
        'source': {'ref': str, 'text': str},
        'target': {'ref': str, 'text': str},
        'overall_score': float,
        'edit_distance_similarity': float
    }
    """
    normalized = []
    
    for idx, m in enumerate(matches):
        # Handle both pre-scored and post-scored formats
        if 'source_idx' in m:
            # Pre-scored format (from matcher)
            src_idx = m['source_idx']
            tgt_idx = m['target_idx']
            
            if src_idx >= len(source_units) or tgt_idx >= len(target_units):
                continue
                
            src_unit = source_units[src_idx]
            tgt_unit = target_units[tgt_idx]
            
            score = m.get('edit_distance_score', m.get('edit_distance_similarity', 0))
            source_ref = src_unit.get('ref', f'idx:{src_idx}')
            target_ref = tgt_unit.get('ref', f'idx:{tgt_idx}')
            source_text = src_unit.get('text', '')
            target_text = tgt_unit.get('text', '')
            edit_distance = m.get('edit_distance', 0)
        elif 'source' in m and 'target' in m:
            # Post-scored format
            source = m.get('source', {})
            target = m.get('target', {})
            score = m.get('edit_distance_similarity', m.get('edit_distance_score', m.get('overall_score', 0)))
            source_ref = source.get('ref', '')
            target_ref = target.get('ref', '')
            source_text = source.get('text', '')
            target_text = target.get('text', '')
            edit_distance = m.get('edit_distance', 0)
        else:
            continue
        
        # Apply threshold
        if score < thresholds.edit_distance_min_score:
            continue
        
        # Ensure valid refs for correlation
        if not source_ref:
            source_ref = f'edt:{idx}:src'
        if not target_ref:
            target_ref = f'edt:{idx}:tgt'
        
        normalized.append(NormalizedMatch(
            source_unit_ref=source_ref,
            target_unit_ref=target_ref,
            source_text=source_text,
            target_text=target_text,
            match_type='edit_distance',
            score=score,
            match_count=edit_distance,
            extra_data={'edit_distance': edit_distance}
        ))
    
    return normalized


# ============================================================================
# CORRELATION: Combine signals from different match types
# ============================================================================

def create_correlation_key(source_ref: str, target_ref: str) -> str:
    """
    Create a unique key for correlating matches across types.
    Uses unit references which are stable across match types.
    """
    return f"{source_ref}||{target_ref}"


def correlate_normalized_matches(
    lemma_matches: List[NormalizedMatch],
    semantic_matches: List[NormalizedMatch],
    sound_matches: List[NormalizedMatch],
    edit_distance_matches: List[NormalizedMatch],
    source_text_id: str,
    target_text_id: str
) -> List[CompositeMatch]:
    """
    Correlate normalized matches from different match types to find multi-signal parallels.
    
    Args:
        lemma_matches: Normalized lemma matches
        semantic_matches: Normalized semantic matches
        sound_matches: Normalized sound matches
        edit_distance_matches: Normalized edit distance matches
        source_text_id: Source text identifier
        target_text_id: Target text identifier
        
    Returns:
        List of CompositeMatch objects, sorted by tier then score
    """
    # Index matches by source-target unit pair
    match_index: Dict[str, CompositeMatch] = {}
    
    # Process lemma matches
    for m in lemma_matches:
        key = create_correlation_key(m.source_unit_ref, m.target_unit_ref)
        
        if key not in match_index:
            match_index[key] = CompositeMatch(
                source_text_id=source_text_id,
                target_text_id=target_text_id,
                source_unit_ref=m.source_unit_ref,
                target_unit_ref=m.target_unit_ref,
                source_snippet=m.source_text,
                target_snippet=m.target_text
            )
        
        match_index[key].lemma_score = m.score
        match_index[key].lemma_matches = m.match_count
        match_index[key].signals.add('lemma')
    
    # Process semantic matches
    for m in semantic_matches:
        key = create_correlation_key(m.source_unit_ref, m.target_unit_ref)
        
        if key not in match_index:
            match_index[key] = CompositeMatch(
                source_text_id=source_text_id,
                target_text_id=target_text_id,
                source_unit_ref=m.source_unit_ref,
                target_unit_ref=m.target_unit_ref,
                source_snippet=m.source_text,
                target_snippet=m.target_text
            )
        
        match_index[key].semantic_score = m.score
        match_index[key].signals.add('semantic')
        
        # Update snippets if not already set
        if not match_index[key].source_snippet:
            match_index[key].source_snippet = m.source_text
        if not match_index[key].target_snippet:
            match_index[key].target_snippet = m.target_text
    
    # Process sound matches
    for m in sound_matches:
        key = create_correlation_key(m.source_unit_ref, m.target_unit_ref)
        
        if key not in match_index:
            match_index[key] = CompositeMatch(
                source_text_id=source_text_id,
                target_text_id=target_text_id,
                source_unit_ref=m.source_unit_ref,
                target_unit_ref=m.target_unit_ref,
                source_snippet=m.source_text,
                target_snippet=m.target_text
            )
        
        match_index[key].sound_score = m.score
        match_index[key].signals.add('sound')
        
        if not match_index[key].source_snippet:
            match_index[key].source_snippet = m.source_text
        if not match_index[key].target_snippet:
            match_index[key].target_snippet = m.target_text
    
    # Process edit distance matches
    for m in edit_distance_matches:
        key = create_correlation_key(m.source_unit_ref, m.target_unit_ref)
        
        if key not in match_index:
            match_index[key] = CompositeMatch(
                source_text_id=source_text_id,
                target_text_id=target_text_id,
                source_unit_ref=m.source_unit_ref,
                target_unit_ref=m.target_unit_ref,
                source_snippet=m.source_text,
                target_snippet=m.target_text
            )
        
        match_index[key].edit_distance_score = m.score
        match_index[key].signals.add('edit_distance')
        
        if not match_index[key].source_snippet:
            match_index[key].source_snippet = m.source_text
        if not match_index[key].target_snippet:
            match_index[key].target_snippet = m.target_text
    
    # Convert to list and sort by tier (desc) then composite score (desc)
    results = list(match_index.values())
    results.sort(key=lambda x: (x.confidence_tier.value, x.composite_score), reverse=True)
    
    return results


def find_composite_matches(
    scored_lemma_matches: List[Dict],
    semantic_matches: List[Dict],
    sound_matches: List[Dict],
    edit_distance_matches: List[Dict],
    source_units: List[Dict],
    target_units: List[Dict],
    source_text_id: str,
    target_text_id: str,
    thresholds: Optional[CompositeThresholds] = None
) -> List[CompositeMatch]:
    """
    High-level function to find composite matches from raw match results.
    
    This is the main entry point for batch processing.
    
    Args:
        scored_lemma_matches: Results from scorer.score_matches (lemma type)
        semantic_matches: Results from find_semantic_matches (pre or post-scored)
        sound_matches: Results from find_sound_matches or scorer (sound type)
        edit_distance_matches: Results from edit distance matching
        source_units: Source text units
        target_units: Target text units
        source_text_id: Source text identifier
        target_text_id: Target text identifier
        thresholds: Optional custom thresholds
        
    Returns:
        List of CompositeMatch objects sorted by confidence tier then score
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    
    # Normalize all matches
    norm_lemma = normalize_lemma_matches(scored_lemma_matches, source_units, target_units, thresholds)
    norm_semantic = normalize_semantic_matches(semantic_matches, source_units, target_units, thresholds)
    norm_sound = normalize_sound_matches(sound_matches, source_units, target_units, thresholds)
    norm_edit_distance = normalize_edit_distance_matches(edit_distance_matches, source_units, target_units, thresholds)
    
    # Correlate
    return correlate_normalized_matches(
        norm_lemma, norm_semantic, norm_sound, norm_edit_distance,
        source_text_id, target_text_id
    )


# ============================================================================
# AGGREGATION: For network visualizations
# ============================================================================

def aggregate_text_connections(
    composite_matches: List[CompositeMatch]
) -> Dict[str, Dict]:
    """
    Aggregate composite matches into text-level connection statistics.
    Used for network visualizations.
    
    Returns dict with structure:
    {
        'source_text::target_text': {
            'source_text_id': str,
            'target_text_id': str,
            'total_parallels': int,
            'gold_count': int,
            'silver_count': int,
            'bronze_count': int,
            'connection_strength': float  # Weighted score
        }
    }
    """
    connections: Dict[str, Dict] = {}
    
    for match in composite_matches:
        key = f"{match.source_text_id}::{match.target_text_id}"
        
        if key not in connections:
            connections[key] = {
                'source_text_id': match.source_text_id,
                'target_text_id': match.target_text_id,
                'total_parallels': 0,
                'gold_count': 0,
                'silver_count': 0,
                'bronze_count': 0,
                'copper_count': 0,
                'connection_strength': 0.0
            }
        
        conn = connections[key]
        conn['total_parallels'] += 1
        
        tier = match.confidence_tier
        if tier == ConfidenceTier.GOLD:
            conn['gold_count'] += 1
            conn['connection_strength'] += 4.0
        elif tier == ConfidenceTier.SILVER:
            conn['silver_count'] += 1
            conn['connection_strength'] += 3.0
        elif tier == ConfidenceTier.BRONZE:
            conn['bronze_count'] += 1
            conn['connection_strength'] += 2.0
        elif tier == ConfidenceTier.COPPER:
            conn['copper_count'] += 1
            conn['connection_strength'] += 1.0
    
    return connections


def get_tier_statistics(composite_matches: List[CompositeMatch]) -> Dict:
    """Get statistics about confidence tier distribution"""
    stats = {
        'total': len(composite_matches),
        'gold': 0,
        'silver': 0,
        'bronze': 0,
        'copper': 0,
        'gold_percentage': 0.0,
        'silver_percentage': 0.0,
        'bronze_percentage': 0.0,
        'copper_percentage': 0.0
    }
    
    for m in composite_matches:
        tier = m.confidence_tier
        if tier == ConfidenceTier.GOLD:
            stats['gold'] += 1
        elif tier == ConfidenceTier.SILVER:
            stats['silver'] += 1
        elif tier == ConfidenceTier.BRONZE:
            stats['bronze'] += 1
        elif tier == ConfidenceTier.COPPER:
            stats['copper'] += 1
    
    if stats['total'] > 0:
        stats['gold_percentage'] = round(100 * stats['gold'] / stats['total'], 1)
        stats['silver_percentage'] = round(100 * stats['silver'] / stats['total'], 1)
        stats['bronze_percentage'] = round(100 * stats['bronze'] / stats['total'], 1)
        stats['copper_percentage'] = round(100 * stats['copper'] / stats['total'], 1)
    
    return stats


# ============================================================================
# METHODOLOGY: For transparency panel
# ============================================================================

def get_methodology_summary(thresholds: CompositeThresholds) -> Dict:
    """
    Generate methodology summary for transparency panel.
    Shows users exactly how the visualization data was computed.
    """
    return {
        'name': 'Tesserae V6 Multi-Signal Composite Scoring',
        'version': '1.1',
        'match_types': {
            'lemma': {
                'description': 'Shared vocabulary (dictionary forms)',
                'algorithm': 'V3-style scoring with IDF and distance penalty',
                'threshold': f'Score >= {thresholds.lemma_min_score}, Min matches >= {thresholds.lemma_min_matches}'
            },
            'semantic': {
                'description': 'Conceptual similarity via AI embeddings',
                'algorithm': 'SPhilBERTa cosine similarity (Latin/Greek), MiniLM (English)',
                'threshold': f'Score >= {thresholds.semantic_min_score}'
            },
            'sound': {
                'description': 'Phonetic similarity via character patterns',
                'algorithm': 'Character trigram Jaccard similarity',
                'threshold': f'Score >= {thresholds.sound_min_score}'
            },
            'edit_distance': {
                'description': 'Character-level string similarity',
                'algorithm': 'Normalized Levenshtein distance (1 - distance/max_len)',
                'threshold': f'Score >= {thresholds.edit_distance_min_score}'
            }
        },
        'ranking_system': {
            'GOLD': 'Parallel confirmed by all 4 signals (highest confidence)',
            'SILVER': 'Parallel confirmed by 3 signals (high confidence)',
            'BRONZE': 'Parallel confirmed by 2 signals (moderate confidence)',
            'COPPER': 'Parallel confirmed by 1 signal (low confidence)'
        },
        'notes': [
            'Thresholds are set high to prioritize precision over recall',
            'Cross-lingual matches (Greek↔Latin) use semantic_cross and are shown separately',
            'Thresholds will be calibrated against curated scholarly parallels'
        ]
    }


# Default thresholds (can be customized)
DEFAULT_THRESHOLDS = CompositeThresholds()
