"""
Tesserae V6 - Base Classes and Interfaces
Abstract base classes for matchers, scorers, and text processors
Enables plugin-style additions of new algorithms
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
from enum import Enum


class MatchType(Enum):
    """Supported match types"""
    LEMMA = 'lemma'
    EXACT = 'exact'
    SOUND = 'sound'
    EDIT_DISTANCE = 'edit_distance'
    SEMANTIC = 'semantic'
    SYN = 'syn'  # Synonym matching
    
    @classmethod
    def from_string(cls, value: str) -> 'MatchType':
        """Safe conversion from string, with fallback to LEMMA"""
        try:
            return cls(value)
        except ValueError:
            return cls.LEMMA


class UnitType(Enum):
    """Text unit types for chunking"""
    LINE = 'line'
    PHRASE = 'phrase'


class StoplistBasis(Enum):
    """Stoplist calculation basis"""
    SOURCE_TARGET = 'source_target'
    SOURCE = 'source'
    TARGET = 'target'
    CORPUS = 'corpus'


@dataclass
class TextUnit:
    """Represents a unit of text (line or phrase)"""
    ref: str
    text: str
    tokens: List[str]
    lemmas: List[str]
    pos_tags: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchResult:
    """Result of a matching operation"""
    source_idx: int
    target_idx: int
    matched_lemmas: List[str]
    match_basis: str = 'lemma'
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredResult:
    """A fully scored search result"""
    source_ref: str
    source_text: str
    source_tokens: List[str]
    source_highlight_indices: List[int]
    target_ref: str
    target_text: str
    target_tokens: List[str]
    target_highlight_indices: List[int]
    matched_words: List[Dict[str, Any]]
    source_distance: int
    target_distance: int
    overall_score: float
    base_score: float
    features: Dict[str, Any]
    match_basis: str = 'lemma'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'source': {
                'ref': self.source_ref,
                'text': self.source_text,
                'tokens': self.source_tokens,
                'highlight_indices': self.source_highlight_indices
            },
            'target': {
                'ref': self.target_ref,
                'text': self.target_text,
                'tokens': self.target_tokens,
                'highlight_indices': self.target_highlight_indices
            },
            'matched_words': self.matched_words,
            'source_distance': self.source_distance,
            'target_distance': self.target_distance,
            'overall_score': self.overall_score,
            'base_score': self.base_score,
            'features': self.features,
            'match_basis': self.match_basis
        }


@dataclass
class SearchRequest:
    """Search request parameters"""
    source_text: str
    target_text: str
    language: str = 'la'
    match_type: MatchType = MatchType.LEMMA
    min_matches: int = 2
    max_distance: int = 999
    max_results: int = 500
    source_unit_type: UnitType = UnitType.LINE
    target_unit_type: UnitType = UnitType.LINE
    stoplist_basis: StoplistBasis = StoplistBasis.SOURCE_TARGET
    stoplist_size: int = 0
    custom_stopwords: str = ''
    feature_weights: Dict[str, float] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchRequest':
        """Create from dictionary (e.g., from JSON request)"""
        return cls(
            source_text=data.get('source', ''),
            target_text=data.get('target', ''),
            language=data.get('language', 'la'),
            match_type=MatchType.from_string(data.get('match_type', 'lemma')),
            min_matches=data.get('min_matches', 2),
            max_distance=data.get('max_distance', 999),
            max_results=data.get('max_results', 500),
            source_unit_type=UnitType(data.get('source_unit_type', 'line')),
            target_unit_type=UnitType(data.get('target_unit_type', 'line')),
            stoplist_basis=StoplistBasis(data.get('stoplist_basis', 'source_target')),
            stoplist_size=data.get('stoplist_size', 0),
            custom_stopwords=data.get('custom_stopwords', ''),
            feature_weights=data.get('feature_weights', {})
        )
    
    def to_settings_dict(self) -> Dict[str, Any]:
        """Convert to legacy settings dict format for backward compatibility"""
        return {
            'language': self.language,
            'match_type': self.match_type.value,
            'min_matches': self.min_matches,
            'max_distance': self.max_distance,
            'max_results': self.max_results,
            'source_unit_type': self.source_unit_type.value,
            'target_unit_type': self.target_unit_type.value,
            'stoplist_basis': self.stoplist_basis.value,
            'stoplist_size': self.stoplist_size,
            'custom_stopwords': self.custom_stopwords,
            **self.feature_weights
        }


class BaseMatcher(ABC):
    """Abstract base class for matching algorithms"""
    
    @property
    @abstractmethod
    def match_type(self) -> MatchType:
        """The type of matching this algorithm performs"""
        pass
    
    @property
    def name(self) -> str:
        """Human-readable name for this matcher"""
        return self.match_type.value
    
    @property
    def description(self) -> str:
        """Description of what this matcher does"""
        return f"{self.name} matcher"
    
    @abstractmethod
    def find_matches(
        self,
        source_units: List[Dict[str, Any]],
        target_units: List[Dict[str, Any]],
        settings: Optional[Dict[str, Any]] = None,
        corpus_frequencies: Optional[Dict[str, int]] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Find matches between source and target units.
        
        Args:
            source_units: List of source text units
            target_units: List of target text units
            settings: Optional matching settings
            corpus_frequencies: Optional corpus-wide word frequencies
            
        Returns:
            Tuple of (list of matches, stoplist size)
        """
        pass
    
    def build_stoplist(
        self,
        source_units: List[Dict[str, Any]],
        target_units: List[Dict[str, Any]],
        basis: str = 'source_target',
        language: str = 'la',
        corpus_frequencies: Optional[Dict[str, int]] = None
    ) -> Set[str]:
        """Build stoplist - can be overridden by subclasses"""
        return set()


class BaseScorer(ABC):
    """Abstract base class for scoring algorithms"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this scoring algorithm"""
        pass
    
    @property
    def description(self) -> str:
        """Description of the scoring algorithm"""
        return f"{self.name} scorer"
    
    @abstractmethod
    def score_matches(
        self,
        matches: List[Dict[str, Any]],
        source_units: List[Dict[str, Any]],
        target_units: List[Dict[str, Any]],
        settings: Optional[Dict[str, Any]] = None,
        source_id: str = '',
        target_id: str = ''
    ) -> List[Dict[str, Any]]:
        """
        Score a list of matches.
        
        Args:
            matches: List of match results from a matcher
            source_units: List of source text units
            target_units: List of target text units
            settings: Optional scoring settings
            source_id: Source text identifier
            target_id: Target text identifier
            
        Returns:
            List of scored results
        """
        pass


class MatcherRegistry:
    """Registry for matcher implementations - enables plugin-style additions"""
    
    _matchers: Dict[MatchType, BaseMatcher] = {}
    
    @classmethod
    def register(cls, matcher: BaseMatcher) -> None:
        """Register a matcher implementation"""
        cls._matchers[matcher.match_type] = matcher
    
    @classmethod
    def get(cls, match_type: MatchType) -> Optional[BaseMatcher]:
        """Get a matcher by type"""
        return cls._matchers.get(match_type)
    
    @classmethod
    def get_by_name(cls, name: str) -> Optional[BaseMatcher]:
        """Get a matcher by string name"""
        try:
            match_type = MatchType(name)
            return cls.get(match_type)
        except ValueError:
            return None
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered matcher names"""
        return [mt.value for mt in cls._matchers.keys()]
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered matchers (for testing)"""
        cls._matchers.clear()


class ScorerRegistry:
    """Registry for scorer implementations"""
    
    _scorers: Dict[str, BaseScorer] = {}
    _default: Optional[str] = None
    
    @classmethod
    def register(cls, scorer: BaseScorer, is_default: bool = False) -> None:
        """Register a scorer implementation"""
        cls._scorers[scorer.name] = scorer
        if is_default or cls._default is None:
            cls._default = scorer.name
    
    @classmethod
    def get(cls, name: Optional[str] = None) -> Optional[BaseScorer]:
        """Get a scorer by name, or the default if no name provided"""
        if name is None:
            name = cls._default
        return cls._scorers.get(name) if name else None
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered scorer names"""
        return list(cls._scorers.keys())
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered scorers (for testing)"""
        cls._scorers.clear()
        cls._default = None
