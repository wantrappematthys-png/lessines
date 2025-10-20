"""
Game State
==========

Complete game state with optimized access patterns.
"""

from typing import List, Optional
import sys
import os
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from game_objects.car import Car
from game_objects.ball import Ball
from game_objects.player import Player
from game_objects.boost_pad import BoostPad
from utils.constants import *


class GameState:
    """
    Complete game state.
    
    Optimized for:
    - Batch updates of all objects
    - Minimal redundant reads
    - Efficient bot access
    """
    
    def __init__(self, game_event_address: int, memory_manager):
        """
        Initialize game state.
        
        Args:
            game_event_address: Address of GameEvent object
            memory_manager: MemoryManager instance
        """
        self.address = game_event_address
        self.mm = memory_manager
        
        # Game objects
        self.ball: Optional[Ball] = None
        self.cars: List[Car] = []
        self.players: List[Player] = []
        self.boost_pads: List[BoostPad] = []
        
        # Game info cache
        self._time_remaining = 0.0
        self._is_overtime = False
        self._is_round_active = False
        self._is_kickoff = False
        
        # Initialize boost pads
        self._init_boost_pads()
    
    def _init_boost_pads(self):
        """Initialize boost pad tracking"""
        self.boost_pads = [
            BoostPad((x, y, z), is_big)
            for x, y, z, is_big in BOOST_PAD_LOCATIONS
        ]
    
    def update(self):
        """
        Update entire game state.
        
        Call this once per tick for optimal performance.
        """
        # Update game info
        self._update_game_info()
        
        # Update ball
        self._update_ball()
        
        # Update cars
        self._update_cars()
        
        # Update players
        self._update_players()
    
    def _update_game_info(self):
        """Update game state flags"""
        flags = self.mm.read_int(self.address + GAMEEVENT_FLAGS)
        
        self._is_round_active = (flags >> 2) & 1 == 1
        self._is_overtime = (flags >> 5) & 1 == 1
        
        self._time_remaining = self.mm.read_float(self.address + GAMEEVENT_TIME_REMAINING)
        
        # Detect kickoff: round active + ball at (0,0)
        if self._is_round_active and self.ball:
            x, y, _ = self.ball.location
            self._is_kickoff = abs(x) < 10 and abs(y) < 10
    
    def _update_ball(self):
        """Update ball state"""
        balls_array_addr = self.address + GAMEEVENT_BALLS
        balls_data_addr = self.mm.read_longlong(balls_array_addr)
        balls_count = self.mm.read_int(balls_array_addr + 0x8)
        
        if balls_count > 0 and balls_data_addr != 0:
            ball_addr = self.mm.read_longlong(balls_data_addr)
            
            if self.ball is None or self.ball.address != ball_addr:
                self.ball = Ball(ball_addr, self.mm)
            
            # Batch update physics
            self.ball.update_physics()
    
    def _update_cars(self):
        """Update all cars"""
        cars_array_addr = self.address + GAMEEVENT_CARS
        cars_data_addr = self.mm.read_longlong(cars_array_addr)
        cars_count = self.mm.read_int(cars_array_addr + 0x8)
        
        # Read all car addresses at once
        new_cars = []
        for i in range(cars_count):
            car_addr = self.mm.read_longlong(cars_data_addr + i * 0x8)
            if car_addr == 0:
                continue
            
            # Reuse existing car objects when possible
            car = None
            for existing_car in self.cars:
                if existing_car.address == car_addr:
                    car = existing_car
                    break
            
            if car is None:
                car = Car(car_addr, self.mm)
            
            # Batch update physics
            car.update_physics()
            new_cars.append(car)
        
        self.cars = new_cars
    
    def _update_players(self):
        """Update player info"""
        pris_array_addr = self.address + GAMEEVENT_PRIS
        pris_data_addr = self.mm.read_longlong(pris_array_addr)
        pris_count = self.mm.read_int(pris_array_addr + 0x8)
        
        new_players = []
        for i in range(pris_count):
            pri_addr = self.mm.read_longlong(pris_data_addr + i * 0x8)
            if pri_addr == 0:
                continue
            
            # Reuse existing player objects
            player = None
            for existing_player in self.players:
                if existing_player.address == pri_addr:
                    player = existing_player
                    break
            
            if player is None:
                player = Player(pri_addr, self.mm)
            
            new_players.append(player)
        
        self.players = new_players
    
    # =================================================================
    # CONVENIENCE ACCESSORS
    # =================================================================
    
    def get_car(self, index: int) -> Optional[Car]:
        """Get car by index"""
        if 0 <= index < len(self.cars):
            return self.cars[index]
        return None
    
    def get_player(self, index: int) -> Optional[Player]:
        """Get player by index"""
        if 0 <= index < len(self.players):
            return self.players[index]
        return None
    
    def get_cars_by_team(self, team: int) -> List[Car]:
        """Get all cars on a team"""
        result = []
        for i, player in enumerate(self.players):
            if player.team == team and i < len(self.cars):
                result.append(self.cars[i])
        return result
    
    # =================================================================
    # GAME INFO PROPERTIES
    # =================================================================
    
    @property
    def time_remaining(self) -> float:
        """Seconds remaining in match"""
        return self._time_remaining
    
    @property
    def is_overtime(self) -> bool:
        """Check if in overtime"""
        return self._is_overtime
    
    @property
    def is_round_active(self) -> bool:
        """Check if round is active"""
        return self._is_round_active
    
    @property
    def is_kickoff(self) -> bool:
        """Check if in kickoff state"""
        return self._is_kickoff
    
    # =================================================================
    # BOOST PAD MANAGEMENT
    # =================================================================
    
    def on_boost_picked_up(self, location: tuple):
        """Call when boost pickup event fires"""
        x, y, z = location
        
        # Find closest pad
        min_dist = float('inf')
        closest_pad = None
        
        for pad in self.boost_pads:
            px, py, pz = pad.location
            dist = ((x - px)**2 + (y - py)**2 + (z - pz)**2) ** 0.5
            
            if dist < min_dist:
                min_dist = dist
                closest_pad = pad
        
        if closest_pad and min_dist < 100:  # Within 100 units
            closest_pad.set_inactive()
    
    def on_boost_respawned(self, location: tuple):
        """Call when boost respawn event fires"""
        x, y, z = location
        
        # Find closest pad
        min_dist = float('inf')
        closest_pad = None
        
        for pad in self.boost_pads:
            px, py, pz = pad.location
            dist = ((x - px)**2 + (y - py)**2 + (z - pz)**2) ** 0.5
            
            if dist < min_dist:
                min_dist = dist
                closest_pad = pad
        
        if closest_pad and min_dist < 100:
            closest_pad.set_active()

