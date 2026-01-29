"""
Tesserae V6 - Text Processing Service
Encapsulates text processing, caching, and unit retrieval
Provides abstraction layer for future cache backend changes
"""
import os
from typing import Dict, List, Any, Optional, Protocol
from abc import ABC, abstractmethod

from backend.logging_config import get_logger
from backend.lemma_cache import get_cached_units, save_cached_units, get_file_hash

logger = get_logger('text_service')


class CacheBackend(ABC):
    """Abstract cache backend interface for future extensibility"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set cached value"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values"""
        pass


class InMemoryCache(CacheBackend):
    """Simple in-memory cache implementation"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Any] = {}
        self._max_size = max_size
    
    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)
    
    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = value
    
    def exists(self, key: str) -> bool:
        return key in self._cache
    
    def clear(self) -> None:
        self._cache.clear()
    
    @property
    def size(self) -> int:
        return len(self._cache)


class TextProcessingService:
    """
    Service for processing and caching text units.
    Abstracts text processing logic from Flask routes.
    """
    
    def __init__(
        self,
        texts_dir: str,
        text_processor: Any,
        cache: Optional[CacheBackend] = None
    ):
        self.texts_dir = texts_dir
        self.text_processor = text_processor
        self.cache = cache or InMemoryCache()
    
    def get_processed_units(
        self,
        text_id: str,
        language: str,
        unit_type: str
    ) -> List[Dict[str, Any]]:
        """
        Get processed units, using file-based lemma cache when available.
        
        Args:
            text_id: Text file identifier
            language: Language code (la, grc, en)
            unit_type: 'line' or 'phrase'
            
        Returns:
            List of processed text units
        """
        filepath = os.path.join(self.texts_dir, language, text_id)
        cache_key = f"{filepath}:{language}:{unit_type}"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        file_cached = get_cached_units(text_id, language)
        if file_cached:
            units_key = 'units_phrase' if unit_type == 'phrase' else 'units_line'
            units = file_cached.get(units_key)
            if units is not None:
                self.cache.set(cache_key, units)
                return units
        
        units = self.text_processor.process_file(filepath, language, unit_type)
        self.cache.set(cache_key, units)
        
        try:
            file_hash = get_file_hash(filepath)
            existing = get_cached_units(text_id, language)
            if unit_type == 'line':
                phrase_units = existing.get('units_phrase') if existing else None
                save_cached_units(text_id, language, units, phrase_units, file_hash)
            else:
                line_units = existing.get('units_line') if existing else None
                save_cached_units(text_id, language, line_units, units, file_hash)
        except Exception as e:
            logger.warning(f"Failed to save cached units for {text_id}: {e}")
        
        return units
    
    def clear_cache(self) -> int:
        """Clear the in-memory cache"""
        size = getattr(self.cache, 'size', 0)
        self.cache.clear()
        logger.info(f"Cleared {size} cached entries")
        return size
    
    def get_text_path(self, text_id: str, language: str) -> str:
        """Get full path for a text file"""
        return os.path.join(self.texts_dir, language, text_id)
    
    def text_exists(self, text_id: str, language: str) -> bool:
        """Check if a text file exists"""
        return os.path.exists(self.get_text_path(text_id, language))
