"""
Car Object
==========

Optimized car representation with batch reads.
"""

from typing import Tuple, Optional, Dict
import sys
import os
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from game_objects.base import GameObject
from utils.constants import *


class Car(GameObject):
    """
    Represents a car in the game.
    
    Optimized for:
    - Batch reading of physics data
    - Efficient state checks
    - Minimal memory calls
    """
    
    def __init__(self, address: int, memory_manager):
        super().__init__(address, memory_manager)
        self._physics_cache = {}
        self._flags_cache = 0
    
    # =================================================================
    # PHYSICS - Batch Read Optimization
    # =================================================================
    
    def update_physics(self):
        """
        Update all physics data in one batch read.
        Call this once per tick for best performance.
        """
        # Read location (12 bytes)
        loc = self.mm.read_vector3(self.address + ACTOR_LOCATION, use_cache=True)
        self._physics_cache['location'] = loc
        
        # Read rotation (12 bytes)
        rot = self.mm.read_rotator(self.address + ACTOR_ROTATION, use_cache=True)
        self._physics_cache['rotation'] = rot
        
        # Read velocity (12 bytes)
        vel = self.mm.read_vector3(self.address + ACTOR_VELOCITY, use_cache=True)
        self._physics_cache['velocity'] = vel
        
        # Read angular velocity (12 bytes)
        ang_vel = self.mm.read_vector3(self.address + ACTOR_ANGULAR_VELOCITY, use_cache=True)
        self._physics_cache['angular_velocity'] = ang_vel
        
        # Read flags once
        self._flags_cache = self.mm.read_int(self.address + CAR_FLAGS)
    
    @property
    def location(self) -> Tuple[float, float, float]:
        """Get car location (x, y, z)"""
        if 'location' in self._physics_cache:
            return self._physics_cache['location']
        
        loc = self.mm.read_vector3(self.address + ACTOR_LOCATION)
        self._physics_cache['location'] = loc
        return loc
    
    @property
    def rotation(self) -> Tuple[float, float, float]:
        """Get car rotation (pitch, yaw, roll) in radians"""
        if 'rotation' in self._physics_cache:
            return self._physics_cache['rotation']
        
        rot = self.mm.read_rotator(self.address + ACTOR_ROTATION)
        self._physics_cache['rotation'] = rot
        return rot
    
    @property
    def velocity(self) -> Tuple[float, float, float]:
        """Get car velocity (vx, vy, vz)"""
        if 'velocity' in self._physics_cache:
            return self._physics_cache['velocity']
        
        vel = self.mm.read_vector3(self.address + ACTOR_VELOCITY)
        self._physics_cache['velocity'] = vel
        return vel
    
    @property
    def angular_velocity(self) -> Tuple[float, float, float]:
        """Get car angular velocity (wx, wy, wz)"""
        if 'angular_velocity' in self._physics_cache:
            return self._physics_cache['angular_velocity']
        
        ang_vel = self.mm.read_vector3(self.address + ACTOR_ANGULAR_VELOCITY)
        self._physics_cache['angular_velocity'] = ang_vel
        return ang_vel
    
    # =================================================================
    # STATE FLAGS - Efficient Bitfield Checks
    # =================================================================
    
    @property
    def is_on_ground(self) -> bool:
        """Check if car has wheel contact"""
        return (self._flags_cache >> 4) & 1 == 1
    
    @property
    def has_jumped(self) -> bool:
        """Check if car has jumped"""
        return (self._flags_cache >> 2) & 1 == 1
    
    @property
    def has_double_jumped(self) -> bool:
        """Check if car has double jumped"""
        return (self._flags_cache >> 3) & 1 == 1
    
    @property
    def is_supersonic(self) -> bool:
        """Check if car is supersonic"""
        return (self._flags_cache >> 5) & 1 == 1
    
    # =================================================================
    # BOOST
    # =================================================================
    
    @property
    def boost_amount(self) -> float:
        """Get boost amount (0.0 - 1.0)"""
        boost_component_addr = self.mm.read_longlong(self.address + CAR_BOOST_COMPONENT)
        if boost_component_addr == 0:
            return 0.0
        
        return self.mm.read_float(boost_component_addr + 0x0338)
    
    @property
    def boost_percent(self) -> int:
        """Get boost as integer percentage (0-100)"""
        return int(round(self.boost_amount * 100))
    
    # =================================================================
    # INPUTS - Batch Read
    # =================================================================
    
    def get_inputs(self) -> Dict[str, float]:
        """
        Get current inputs in one batch read.
        
        Returns:
            Dictionary with throttle, steer, pitch, yaw, roll, jump, boost, handbrake
        """
        return self.mm.read_vehicle_inputs(self.address + CAR_INPUTS)
    
    # =================================================================
    # RELATIONS
    # =================================================================
    
    @property
    def player_info_address(self) -> int:
        """Get PRI (Player Replication Info) address"""
        return self.mm.read_longlong(self.address + CAR_PRI)
    
    # =================================================================
    # UTILITY
    # =================================================================
    
    def get_speed(self) -> float:
        """Calculate speed magnitude from velocity"""
        vx, vy, vz = self.velocity
        return (vx**2 + vy**2 + vz**2) ** 0.5
    
    def get_speed_2d(self) -> float:
        """Calculate 2D speed (ignoring Z)"""
        vx, vy, _ = self.velocity
        return (vx**2 + vy**2) ** 0.5

