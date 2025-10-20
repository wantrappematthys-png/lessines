"""
Ball Object
===========

Optimized ball representation.
"""

from typing import Tuple
import sys
import os
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from game_objects.base import GameObject
from utils.constants import *


class Ball(GameObject):
    """
    Represents the ball.
    
    Optimized with batch physics reads.
    """
    
    def __init__(self, address: int, memory_manager):
        super().__init__(address, memory_manager)
        self._physics_cache = {}
    
    def update_physics(self):
        """Update all physics data in batch"""
        loc = self.mm.read_vector3(self.address + ACTOR_LOCATION, use_cache=True)
        self._physics_cache['location'] = loc
        
        rot = self.mm.read_rotator(self.address + ACTOR_ROTATION, use_cache=True)
        self._physics_cache['rotation'] = rot
        
        vel = self.mm.read_vector3(self.address + ACTOR_VELOCITY, use_cache=True)
        self._physics_cache['velocity'] = vel
        
        ang_vel = self.mm.read_vector3(self.address + ACTOR_ANGULAR_VELOCITY, use_cache=True)
        self._physics_cache['angular_velocity'] = ang_vel
    
    @property
    def location(self) -> Tuple[float, float, float]:
        """Ball position"""
        if 'location' in self._physics_cache:
            return self._physics_cache['location']
        return self.mm.read_vector3(self.address + ACTOR_LOCATION)
    
    @property
    def rotation(self) -> Tuple[float, float, float]:
        """Ball rotation (pitch, yaw, roll)"""
        if 'rotation' in self._physics_cache:
            return self._physics_cache['rotation']
        return self.mm.read_rotator(self.address + ACTOR_ROTATION)
    
    @property
    def velocity(self) -> Tuple[float, float, float]:
        """Ball velocity"""
        if 'velocity' in self._physics_cache:
            return self._physics_cache['velocity']
        return self.mm.read_vector3(self.address + ACTOR_VELOCITY)
    
    @property
    def angular_velocity(self) -> Tuple[float, float, float]:
        """Ball angular velocity"""
        if 'angular_velocity' in self._physics_cache:
            return self._physics_cache['angular_velocity']
        return self.mm.read_vector3(self.address + ACTOR_ANGULAR_VELOCITY)
    
    def get_speed(self) -> float:
        """Calculate ball speed"""
        vx, vy, vz = self.velocity
        return (vx**2 + vy**2 + vz**2) ** 0.5

