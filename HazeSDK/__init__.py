"""
HazeSDK - Optimized Rocket League SDK
=====================================

A high-performance, modular SDK for Rocket League bot development.

Features:
- Intelligent memory caching
- Optimized game object access
- Simple bot interface
- Event system
- Performance monitoring

Author: HazeSDK Team
Version: 1.0.0
"""

from .core.sdk import HazeSDK
from .core.memory_manager import MemoryManager
from .game_objects.game_state import GameState
from .game_objects.car import Car
from .game_objects.ball import Ball
from .events.event_manager import EventManager, EventType
from .utils.constants import *

__version__ = "1.0.0"
__all__ = [
    "HazeSDK",
    "MemoryManager", 
    "GameState",
    "Car",
    "Ball",
    "EventManager",
    "EventType"
]

