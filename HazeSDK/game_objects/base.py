"""
Base Game Object
================

Base class for all game objects with optimized memory access.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.memory_manager import MemoryManager


class GameObject:
    """
    Base class for game objects.
    
    Features:
    - Lazy loading of properties
    - Caching of frequently accessed data
    - Efficient memory reads
    """
    
    def __init__(self, address: int, memory_manager: 'MemoryManager'):
        """
        Initialize game object.
        
        Args:
            address: Memory address of the object
            memory_manager: MemoryManager instance
        """
        self.address = address
        self.mm = memory_manager
        self._cache = {}
    
    def is_valid(self) -> bool:
        """Check if object address is valid"""
        return self.address != 0
    
    def invalidate_cache(self):
        """Clear cached properties"""
        self._cache.clear()
    
    def _read_int(self, offset: int, cache_key: Optional[str] = None) -> int:
        """Read integer with optional caching"""
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        
        value = self.mm.read_int(self.address + offset)
        
        if cache_key:
            self._cache[cache_key] = value
        
        return value
    
    def _read_float(self, offset: int, cache_key: Optional[str] = None) -> float:
        """Read float with optional caching"""
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        
        value = self.mm.read_float(self.address + offset)
        
        if cache_key:
            self._cache[cache_key] = value
        
        return value
    
    def _read_ptr(self, offset: int, cache_key: Optional[str] = None) -> int:
        """Read pointer with optional caching"""
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]
        
        value = self.mm.read_longlong(self.address + offset)
        
        if cache_key:
            self._cache[cache_key] = value
        
        return value
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} at 0x{self.address:X}>"

