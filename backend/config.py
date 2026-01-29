"""
Tesserae V6 - Configuration Module
Centralized settings and feature flags for forward compatibility
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class SearchDefaults:
    """Default search parameters"""
    min_matches: int = 2
    max_distance: int = 999
    max_results: int = 500
    stoplist_size: int = 0
    default_language: str = 'la'
    default_match_type: str = 'lemma'
    default_unit_type: str = 'line'
    default_stoplist_basis: str = 'source_target'


@dataclass
class FeatureWeightDefaults:
    """Default weights for feature-based scoring"""
    lemma_weight: float = 1.0
    pos_weight: float = 0.0
    edit_distance_weight: float = 0.0
    sound_weight: float = 0.0
    semantic_weight: float = 0.0
    scansion_weight: float = 0.0


@dataclass
class PerformanceConfig:
    """Performance-related settings"""
    cache_enabled: bool = True
    max_cache_size: int = 1000
    search_timeout_seconds: int = 300
    semantic_batch_size: int = 32
    sound_top_n_per_source: int = 10
    edit_top_n_per_source: int = 10


@dataclass
class FeatureFlags:
    """Feature flags for enabling/disabling functionality"""
    semantic_matching_enabled: bool = True
    sound_matching_enabled: bool = True
    edit_distance_matching_enabled: bool = True
    scansion_display_enabled: bool = True
    analytics_enabled: bool = True
    debug_mode: bool = False
    
    @classmethod
    def from_env(cls) -> 'FeatureFlags':
        """Create feature flags from environment variables"""
        return cls(
            semantic_matching_enabled=os.environ.get('TESSERAE_SEMANTIC_ENABLED', 'true').lower() == 'true',
            sound_matching_enabled=os.environ.get('TESSERAE_SOUND_ENABLED', 'true').lower() == 'true',
            edit_distance_matching_enabled=os.environ.get('TESSERAE_EDIT_ENABLED', 'true').lower() == 'true',
            scansion_display_enabled=os.environ.get('TESSERAE_SCANSION_ENABLED', 'true').lower() == 'true',
            analytics_enabled=os.environ.get('TESSERAE_ANALYTICS_ENABLED', 'true').lower() == 'true',
            debug_mode=os.environ.get('TESSERAE_DEBUG', 'false').lower() == 'true'
        )


@dataclass  
class AppConfig:
    """Main application configuration"""
    search_defaults: SearchDefaults = field(default_factory=SearchDefaults)
    feature_weights: FeatureWeightDefaults = field(default_factory=FeatureWeightDefaults)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    
    texts_dir: str = ''
    admin_password: str = ''
    
    @classmethod
    def load(cls) -> 'AppConfig':
        """Load configuration from environment and defaults"""
        config = cls(
            features=FeatureFlags.from_env(),
            admin_password=os.environ.get('ADMIN_PASSWORD', ''),
            texts_dir=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')
        )
        
        if os.environ.get('DEBUG', '').lower() == 'true':
            config.features.debug_mode = True
            
        return config
    
    def get_search_settings(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get search settings with optional overrides"""
        settings = {
            'min_matches': self.search_defaults.min_matches,
            'max_distance': self.search_defaults.max_distance,
            'max_results': self.search_defaults.max_results,
            'stoplist_size': self.search_defaults.stoplist_size,
            'language': self.search_defaults.default_language,
            'match_type': self.search_defaults.default_match_type,
            'source_unit_type': self.search_defaults.default_unit_type,
            'target_unit_type': self.search_defaults.default_unit_type,
            'stoplist_basis': self.search_defaults.default_stoplist_basis,
        }
        
        if overrides:
            settings.update(overrides)
            
        return settings
    
    def is_match_type_enabled(self, match_type: str) -> bool:
        """Check if a match type is enabled"""
        if match_type == 'semantic':
            return self.features.semantic_matching_enabled
        elif match_type == 'sound':
            return self.features.sound_matching_enabled
        elif match_type == 'edit_distance':
            return self.features.edit_distance_matching_enabled
        return True


app_config = AppConfig.load()
