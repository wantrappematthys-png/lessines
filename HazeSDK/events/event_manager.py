"""
Event Manager
=============

High-performance event system for game events.
"""

from enum import Enum, auto
from typing import Callable, Dict, List, Any
from dataclasses import dataclass


class EventType(Enum):
    """Game event types"""
    TICK = auto()
    BOOST_PICKED_UP = auto()
    BOOST_RESPAWNED = auto()
    ROUND_STARTED = auto()
    ROUND_ENDED = auto()
    GOAL_SCORED = auto()
    GAME_STARTED = auto()
    GAME_ENDED = auto()
    KEY_PRESSED = auto()


@dataclass
class Event:
    """Base event class"""
    type: EventType
    data: Any = None


class EventManager:
    """
    Lightweight event system.
    
    Features:
    - Fast callback execution
    - Event filtering
    - Minimal overhead
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """
        Subscribe to an event.
        
        Args:
            event_type: Type of event to listen for
            callback: Function to call when event fires
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """
        Unsubscribe from an event.
        
        Args:
            event_type: Event type
            callback: Callback to remove
        """
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
    
    def fire(self, event: Event):
        """
        Fire an event to all subscribers.
        
        Args:
            event: Event to fire
        """
        if event.type not in self._subscribers:
            return
        
        for callback in self._subscribers[event.type]:
            try:
                callback(event)
            except Exception as e:
                # Don't let one callback crash the system
                print(f"[HazeSDK] Event callback error: {e}")
    
    def clear(self):
        """Clear all subscriptions"""
        self._subscribers.clear()

