"""
Boost Pad
=========

Boost pad state tracking.
"""

import time
from typing import Tuple


class BoostPad:
    """
    Represents a boost pad on the field.
    
    Tracked via events for efficiency.
    """
    
    def __init__(self, location: Tuple[float, float, float], is_big: bool):
        """
        Initialize boost pad.
        
        Args:
            location: (x, y, z) position
            is_big: True for big boost (100), False for small (12)
        """
        self.location = location
        self.is_big = is_big
        self.is_active = True
        self.last_pickup_time: float = 0.0
    
    @property
    def respawn_time(self) -> float:
        """Time until respawn"""
        if self.is_active:
            return 0.0
        
        elapsed = time.time() - self.last_pickup_time
        time_needed = 10.0 if self.is_big else 4.0
        
        return max(0.0, time_needed - elapsed)
    
    @property
    def will_respawn_soon(self) -> bool:
        """Check if pad will respawn in <1 second"""
        return 0 < self.respawn_time < 1.0
    
    def set_inactive(self):
        """Mark as picked up"""
        self.is_active = False
        self.last_pickup_time = time.time()
    
    def set_active(self):
        """Mark as available"""
        self.is_active = True
        self.last_pickup_time = 0.0

