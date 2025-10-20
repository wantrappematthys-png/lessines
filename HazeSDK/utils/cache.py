"""
Intelligent Cache System
========================

Optimized caching for memory reads with automatic invalidation.
"""

import time
from typing import Any, Optional, Dict
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Cache entry with timestamp"""
    value: Any
    timestamp: float


class Cache:
    """
    High-performance cache with automatic expiration.
    
    Features:
    - Time-based expiration
    - Separate namespaces for different data types
    - Memory efficient
    """
    
    def __init__(self, default_ttl: float = 0.1):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default time-to-live in seconds
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str, ttl: Optional[float] = None) -> Optional[Any]:
        """
        Get value from cache if still valid.
        
        Args:
            key: Cache key
            ttl: Custom TTL, uses default if None
            
        Returns:
            Cached value or None if expired/missing
        """
        if key not in self._cache:
            self._misses += 1
            return None
        
        entry = self._cache[key]
        age = time.time() - entry.timestamp
        
        ttl = ttl if ttl is not None else self.default_ttl
        
        if age > ttl:
            # Expired
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        return entry.value
    
    def set(self, key: str, value: Any):
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = CacheEntry(
            value=value,
            timestamp=time.time()
        )
    
    def invalidate(self, key: str):
        """Remove a specific key from cache"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """Clear entire cache"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache)
        }


class ObjectCache:
    """
    Specialized cache for game objects with address-based keys.
    """
    
    def __init__(self, ttl: float = 0.1):
        self._cache = Cache(ttl)
    
    def get_object(self, address: int, object_type: str) -> Optional[Any]:
        """Get cached object by address and type"""
        key = f"{object_type}_{address:X}"
        return self._cache.get(key)
    
    def set_object(self, address: int, object_type: str, obj: Any):
        """Cache object by address and type"""
        key = f"{object_type}_{address:X}"
        self._cache.set(key, obj)
    
    def invalidate_object(self, address: int, object_type: str):
        """Invalidate specific object"""
        key = f"{object_type}_{address:X}"
        self._cache.invalidate(key)
    
    def clear(self):
        """Clear all cached objects"""
        self._cache.clear()

