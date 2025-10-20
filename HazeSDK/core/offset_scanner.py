"""
Offset Scanner
==============

Auto-detect memory offsets for GNames and GObjects.
"""

import struct
from typing import Optional, Tuple
import sys
import os
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from utils.constants import MEMORY_PATTERNS, EXPECTED_OFFSET_DIFF


class OffsetScanner:
    """
    Automatic offset detection for Rocket League memory structures.
    
    Uses multiple patterns for different game versions.
    """
    
    def __init__(self, memory_manager):
        """
        Initialize scanner.
        
        Args:
            memory_manager: MemoryManager instance
        """
        self.mm = memory_manager
        self.pm = memory_manager.pm
        self.base_address = memory_manager.base_address
    
    def find_offsets(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Find GNames and GObjects offsets.
        
        Returns:
            Tuple of (gnames_offset, gobjects_offset) or (None, None) if not found
        """
        print("[HazeSDK] Scanning for memory offsets...")
        
        try:
            # Get module info
            import pymem.process
            module = pymem.process.module_from_name(self.pm.process_handle, "RocketLeague.exe")
            module_base = module.lpBaseOfDll
            module_size = module.SizeOfImage
            
            gnames_address = None
            gobjects_address = None
            
            # Try current patterns first
            print("[HazeSDK] Attempting current patterns...")
            
            # Find GObjects
            gobjects_pattern_addr = self._scan_pattern(
                MEMORY_PATTERNS['GObjects_Current'],
                "GObjects (Current)"
            )
            if gobjects_pattern_addr:
                gobjects_address = self._extract_gobjects_current(gobjects_pattern_addr)
                if gobjects_address:
                    print(f"[HazeSDK] ✓ GObjects found at 0x{gobjects_address:X}")
            
            # Find GNames - Method 1
            gnames_pattern_addr = self._scan_pattern(
                MEMORY_PATTERNS['GNames_Current1'],
                "GNames (Current Method 1)"
            )
            if gnames_pattern_addr:
                gnames_address = self._extract_gnames_method1(gnames_pattern_addr)
                if gnames_address:
                    print(f"[HazeSDK] ✓ GNames found at 0x{gnames_address:X}")
            
            # Try method 2 if method 1 failed
            if not gnames_address:
                gnames_pattern_addr = self._scan_pattern(
                    MEMORY_PATTERNS['GNames_Current2'],
                    "GNames (Current Method 2)"
                )
                if gnames_pattern_addr:
                    gnames_address = self._extract_gnames_method2(gnames_pattern_addr)
                    if gnames_address:
                        print(f"[HazeSDK] ✓ GNames found at 0x{gnames_address:X}")
            
            # Fallback to legacy patterns if needed
            if not gnames_address or not gobjects_address:
                print("[HazeSDK] Trying legacy patterns...")
                gnames_address, gobjects_address = self._try_legacy_patterns(
                    gnames_address, gobjects_address
                )
            
            # Validate offsets
            if gnames_address and gobjects_address:
                offset_diff = abs(gobjects_address - gnames_address)
                if offset_diff != EXPECTED_OFFSET_DIFF:
                    print(f"[HazeSDK] ⚠ Unexpected offset difference: 0x{offset_diff:X}")
                    print(f"[HazeSDK]   Adjusting GNames to maintain 0x{EXPECTED_OFFSET_DIFF:X} difference")
                    gnames_address = gobjects_address - EXPECTED_OFFSET_DIFF
                
                # Convert to offsets
                gnames_offset = gnames_address - self.base_address
                gobjects_offset = gobjects_address - self.base_address
                
                print(f"[HazeSDK] ✓ Offsets found:")
                print(f"[HazeSDK]   GNames:   0x{gnames_offset:X}")
                print(f"[HazeSDK]   GObjects: 0x{gobjects_offset:X}")
                
                return gnames_offset, gobjects_offset
            
            print("[HazeSDK] ✗ Failed to find offsets")
            return None, None
            
        except Exception as e:
            print(f"[HazeSDK] ✗ Error during offset scan: {e}")
            return None, None
    
    def _scan_pattern(self, pattern: bytes, name: str) -> Optional[int]:
        """Scan for a pattern in memory"""
        try:
            import pymem.process
            module = pymem.process.module_from_name(self.pm.process_handle, "RocketLeague.exe")
            base = module.lpBaseOfDll
            size = module.SizeOfImage
            
            memory_dump = self.mm.read_bytes(base, size)
            
            for i in range(len(memory_dump) - len(pattern)):
                if self._pattern_matches(memory_dump, i, pattern):
                    return base + i
            
            return None
        except Exception:
            return None
    
    def _pattern_matches(self, memory: bytes, offset: int, pattern: bytes) -> bool:
        """Check if pattern matches at offset (0x00 = wildcard)"""
        for i, byte in enumerate(pattern):
            if byte != 0x00 and memory[offset + i] != byte:
                return False
        return True
    
    def _extract_gobjects_current(self, pattern_addr: int) -> Optional[int]:
        """Extract GObjects address from current pattern"""
        try:
            # Pattern: 48 8B C8 48 8B 05 ?? ?? ?? ?? 48 8B 0C C8
            # Offset is at pattern_addr + 6
            offset_addr = pattern_addr + 6
            rel_offset = struct.unpack('i', self.mm.read_bytes(offset_addr, 4))[0]
            return offset_addr + rel_offset + 4
        except Exception:
            return None
    
    def _extract_gnames_method1(self, pattern_addr: int) -> Optional[int]:
        """Extract GNames address - Method 1"""
        try:
            # Pattern: 48 8B 0D ?? ?? ?? ?? 48 8B 0C C1
            # Offset is at pattern_addr + 3
            offset_addr = pattern_addr + 3
            rel_offset = struct.unpack('i', self.mm.read_bytes(offset_addr, 4))[0]
            return offset_addr + rel_offset + 4
        except Exception:
            return None
    
    def _extract_gnames_method2(self, pattern_addr: int) -> Optional[int]:
        """Extract GNames address - Method 2"""
        try:
            # Pattern has longer prefix, offset at pattern_addr + 10
            offset_addr = pattern_addr + 10
            rel_offset = struct.unpack('i', self.mm.read_bytes(offset_addr, 4))[0]
            return offset_addr + rel_offset + 4
        except Exception:
            return None
    
    def _try_legacy_patterns(
        self, 
        current_gnames: Optional[int],
        current_gobjects: Optional[int]
    ) -> Tuple[Optional[int], Optional[int]]:
        """Try legacy patterns as fallback"""
        gnames = current_gnames
        gobjects = current_gobjects
        
        if not gnames:
            pattern_addr = self._scan_pattern(
                MEMORY_PATTERNS['GNames_Legacy1'],
                "GNames (Legacy)"
            )
            if pattern_addr:
                gnames = self._extract_legacy_gnames(pattern_addr)
        
        if not gobjects:
            pattern_addr = self._scan_pattern(
                MEMORY_PATTERNS['GObjects_Legacy1'],
                "GObjects (Legacy)"
            )
            if pattern_addr:
                gobjects = self._extract_legacy_gobjects(pattern_addr)
        
        return gnames, gobjects
    
    def _extract_legacy_gnames(self, pattern_addr: int) -> Optional[int]:
        """Extract GNames using legacy method"""
        try:
            offset = pattern_addr + 3
            rel_offset = struct.unpack('i', self.mm.read_bytes(offset, 4))[0]
            addr = offset + rel_offset + 4
            addr += 0x27
            offset = addr + 3
            rel_offset = struct.unpack('i', self.mm.read_bytes(offset, 4))[0]
            return offset + rel_offset + 4
        except Exception:
            return None
    
    def _extract_legacy_gobjects(self, pattern_addr: int) -> Optional[int]:
        """Extract GObjects using legacy method"""
        try:
            offset = pattern_addr + 1
            rel_offset = struct.unpack('i', self.mm.read_bytes(offset, 4))[0]
            addr = offset + rel_offset + 4
            addr += 0x65
            offset = addr + 3
            rel_offset = struct.unpack('i', self.mm.read_bytes(offset, 4))[0]
            return offset + rel_offset + 4
        except Exception:
            return None

