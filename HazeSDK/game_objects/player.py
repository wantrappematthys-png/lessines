"""
Player Object
=============

Player information (PRI - Player Replication Info).
"""

from typing import Optional
import sys
import os
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from game_objects.base import GameObject


class Player(GameObject):
    """
    Player information.
    
    Cached for efficient access.
    """
    
    def __init__(self, address: int, memory_manager):
        super().__init__(address, memory_manager)
        self._name: Optional[str] = None
        self._team: Optional[int] = None
    
    @property
    def name(self) -> str:
        """Player name"""
        if self._name is None:
            self._name = self.mm.read_string(self.address + 0x0288)
        return self._name
    
    @property
    def team(self) -> int:
        """Team index (0 = blue, 1 = orange)"""
        if self._team is None:
            team_info_addr = self.mm.read_longlong(self.address + 0x02B0)
            if team_info_addr != 0:
                self._team = self.mm.read_int(team_info_addr + 0x0280)
            else:
                self._team = 0
        return self._team
    
    @property
    def score(self) -> int:
        """Player score"""
        return self.mm.read_int(self.address + 0x0458)
    
    @property
    def goals(self) -> int:
        """Goals scored"""
        return self.mm.read_int(self.address + 0x045C)
    
    @property
    def assists(self) -> int:
        """Assists"""
        return self.mm.read_int(self.address + 0x0464)
    
    @property
    def saves(self) -> int:
        """Saves"""
        return self.mm.read_int(self.address + 0x0468)
    
    @property
    def shots(self) -> int:
        """Shots"""
        return self.mm.read_int(self.address + 0x046C)
    
    @property
    def boost(self) -> int:
        """Current boost amount (0-100)"""
        car_addr = self.mm.read_longlong(self.address + 0x0498)
        if car_addr == 0:
            return 0
        
        boost_component_addr = self.mm.read_longlong(car_addr + 0x0848)
        if boost_component_addr == 0:
            return 0
        
        boost_amount = self.mm.read_float(boost_component_addr + 0x0338)
        return int(round(boost_amount * 100))

