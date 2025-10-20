"""
Memory Manager
==============

Optimized memory access with intelligent caching and batch reads.
"""

import pymem
import pymem.process
import struct
from typing import Optional, List, Tuple, Any

# Absolute imports
import sys
import os
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from utils.cache import Cache
from utils.performance import PerformanceMonitor


class MemoryManager:
    """
    High-performance memory manager for Rocket League.
    
    Features:
    - Intelligent caching of memory reads
    - Batch read operations
    - Error handling with retries
    - Performance monitoring
    """
    
    def __init__(self, process_name: str = "RocketLeague.exe", pid: Optional[int] = None):
        """
        Initialize memory manager.
        
        Args:
            process_name: Name of the process to attach to
            pid: Optional process ID
        """
        self.process_name = process_name
        self.pid = pid
        self.pm: Optional[pymem.Pymem] = None
        self.base_address = 0
        
        # Cache for memory reads
        self._cache = Cache(default_ttl=0.05)  # 50ms cache
        
        # Performance monitoring
        self._perf_monitor = PerformanceMonitor()
        
        # Connect to process
        self._connect()
    
    def _connect(self):
        """Connect to the Rocket League process"""
        try:
            if self.pid:
                self.pm = pymem.Pymem(self.pid)
            else:
                self.pm = pymem.Pymem(self.process_name)
            
            module = pymem.process.module_from_name(
                self.pm.process_handle, 
                self.process_name
            )
            self.base_address = module.lpBaseOfDll
            
        except Exception as e:
            raise RuntimeError(f"Failed to connect to {self.process_name}: {e}")
    
    # =================================================================
    # BASIC MEMORY READS
    # =================================================================
    
    def read_int(self, address: int, use_cache: bool = False) -> int:
        """Read a 32-bit integer"""
        if use_cache:
            cached = self._cache.get(f"int_{address:X}")
            if cached is not None:
                return cached
        
        with self._perf_monitor.time_operation("read_int"):
            try:
                value = self.pm.read_int(address)
                if use_cache:
                    self._cache.set(f"int_{address:X}", value)
                return value
            except Exception:
                return 0
    
    def read_uint(self, address: int, use_cache: bool = False) -> int:
        """Read an unsigned 32-bit integer"""
        if use_cache:
            cached = self._cache.get(f"uint_{address:X}")
            if cached is not None:
                return cached
        
        with self._perf_monitor.time_operation("read_uint"):
            try:
                value = self.pm.read_uint(address)
                if use_cache:
                    self._cache.set(f"uint_{address:X}", value)
                return value
            except Exception:
                return 0
    
    def read_longlong(self, address: int, use_cache: bool = False) -> int:
        """Read a 64-bit integer (pointer)"""
        if use_cache:
            cached = self._cache.get(f"ptr_{address:X}")
            if cached is not None:
                return cached
        
        with self._perf_monitor.time_operation("read_ptr"):
            try:
                value = self.pm.read_ulonglong(address)
                if use_cache:
                    self._cache.set(f"ptr_{address:X}", value)
                return value
            except Exception:
                return 0
    
    def read_float(self, address: int, use_cache: bool = False) -> float:
        """Read a 32-bit float"""
        if use_cache:
            cached = self._cache.get(f"float_{address:X}")
            if cached is not None:
                return cached
        
        with self._perf_monitor.time_operation("read_float"):
            try:
                value = self.pm.read_float(address)
                if use_cache:
                    self._cache.set(f"float_{address:X}", value)
                return value
            except Exception:
                return 0.0
    
    def read_uchar(self, address: int, use_cache: bool = False) -> int:
        """Read an unsigned char (byte)"""
        if use_cache:
            cached = self._cache.get(f"byte_{address:X}")
            if cached is not None:
                return cached
        
        with self._perf_monitor.time_operation("read_byte"):
            try:
                value = self.pm.read_uchar(address)
                if use_cache:
                    self._cache.set(f"byte_{address:X}", value)
                return value
            except Exception:
                return 0
    
    def read_bytes(self, address: int, size: int) -> bytes:
        """Read raw bytes"""
        with self._perf_monitor.time_operation("read_bytes"):
            try:
                return self.pm.read_bytes(address, size)
            except Exception:
                return b'\x00' * size
    
    def read_string(self, address: int, max_length: int = 256) -> str:
        """Read a wide string (UTF-16LE)"""
        with self._perf_monitor.time_operation("read_string"):
            try:
                array_data_address = self.read_longlong(address)
                if array_data_address == 0:
                    return ""
                
                array_count = self.read_int(address + 0x8)
                if array_count <= 1 or array_count > max_length:
                    return ""
                
                bytes_to_read = min((array_count - 1) * 2, max_length * 2)
                char_bytes = self.read_bytes(array_data_address, bytes_to_read)
                
                return char_bytes.decode('utf-16le', errors='ignore')
            except Exception:
                return ""
    
    # =================================================================
    # OPTIMIZED BATCH READS
    # =================================================================
    
    def read_vector3(self, address: int, use_cache: bool = False) -> Tuple[float, float, float]:
        """
        Read a 3D vector (12 bytes) in one operation.
        More efficient than 3 separate float reads.
        """
        cache_key = f"vec3_{address:X}"
        
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        with self._perf_monitor.time_operation("read_vector3"):
            try:
                # Read all 12 bytes at once
                data = self.read_bytes(address, 12)
                x, y, z = struct.unpack('<fff', data)
                
                result = (x, y, z)
                if use_cache:
                    self._cache.set(cache_key, result)
                
                return result
            except Exception:
                return (0.0, 0.0, 0.0)
    
    def read_rotator(self, address: int, use_cache: bool = False) -> Tuple[float, float, float]:
        """
        Read a rotator (pitch, yaw, roll) in one operation.
        Values are converted from int to radians.
        """
        cache_key = f"rot_{address:X}"
        
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        with self._perf_monitor.time_operation("read_rotator"):
            try:
                # Read all 12 bytes at once
                data = self.read_bytes(address, 12)
                pitch, yaw, roll = struct.unpack('<iii', data)
                
                # Convert to radians
                to_rad = 0.00009587379924285
                result = (pitch * to_rad, yaw * to_rad, roll * to_rad)
                
                if use_cache:
                    self._cache.set(cache_key, result)
                
                return result
            except Exception:
                return (0.0, 0.0, 0.0)
    
    def read_vehicle_inputs(self, address: int) -> dict:
        """
        Read all vehicle inputs in one batch operation (32 bytes).
        Much faster than individual reads.
        """
        with self._perf_monitor.time_operation("read_inputs"):
            try:
                data = self.read_bytes(address, 32)
                
                # Unpack all floats
                throttle, steer, pitch, yaw, roll, dodge_fwd, dodge_right = struct.unpack('<7f', data[:28])
                
                # Unpack flags
                flags = struct.unpack('<I', data[28:32])[0]
                
                return {
                    'throttle': throttle,
                    'steer': steer,
                    'pitch': pitch,
                    'yaw': yaw,
                    'roll': roll,
                    'dodge_forward': dodge_fwd,
                    'dodge_right': dodge_right,
                    'handbrake': flags & 1,
                    'jump': (flags >> 1) & 1,
                    'boost': (flags >> 2) & 1,
                }
            except Exception:
                return {
                    'throttle': 0.0, 'steer': 0.0, 'pitch': 0.0,
                    'yaw': 0.0, 'roll': 0.0, 'dodge_forward': 0.0,
                    'dodge_right': 0.0, 'handbrake': 0, 'jump': 0, 'boost': 0,
                }
    
    # =================================================================
    # MEMORY WRITING
    # =================================================================
    
    def write_bytes(self, address: int, data: bytes) -> bool:
        """Write raw bytes to memory"""
        with self._perf_monitor.time_operation("write_bytes"):
            try:
                self.pm.write_bytes(address, data, len(data))
                return True
            except Exception:
                return False
    
    def write_vehicle_inputs(self, address: int, inputs: dict) -> bool:
        """
        Write vehicle inputs in one batch operation.
        
        Args:
            address: Input structure address
            inputs: Dictionary with throttle, steer, pitch, yaw, roll, jump, boost, handbrake
        """
        with self._perf_monitor.time_operation("write_inputs"):
            try:
                # Pack floats
                data = struct.pack('<f', inputs.get('throttle', 0.0))
                data += struct.pack('<f', inputs.get('steer', 0.0))
                data += struct.pack('<f', inputs.get('pitch', 0.0))
                data += struct.pack('<f', inputs.get('yaw', 0.0))
                data += struct.pack('<f', inputs.get('roll', 0.0))
                data += struct.pack('<f', -inputs.get('pitch', 0.0))  # dodge_forward
                data += struct.pack('<f', inputs.get('yaw', 0.0))     # dodge_right
                
                # Pack flags
                flags = 0
                flags |= (1 if inputs.get('handbrake', False) else 0) << 0
                flags |= (1 if inputs.get('jump', False) else 0) << 1
                flags |= (1 if inputs.get('boost', False) else 0) << 2
                flags |= (1 if inputs.get('boost', False) else 0) << 3
                
                data += struct.pack('<I', flags)
                
                return self.write_bytes(address, data)
            except Exception:
                return False
    
    # =================================================================
    # PATTERN SCANNING
    # =================================================================
    
    def pattern_scan(self, pattern: bytes, return_multiple: bool = False) -> Optional[int]:
        """
        Scan memory for a pattern.
        
        Args:
            pattern: Byte pattern to search for (use 0x00 for wildcards)
            return_multiple: If True, return all matches
        """
        with self._perf_monitor.time_operation("pattern_scan"):
            try:
                return self.pm.pattern_scan_all(pattern, return_multiple=return_multiple)
            except Exception:
                return None
    
    # =================================================================
    # CACHE MANAGEMENT
    # =================================================================
    
    def clear_cache(self):
        """Clear all cached memory reads"""
        self._cache.clear()
    
    def get_cache_stats(self) -> dict:
        """Get cache performance statistics"""
        return self._cache.get_stats()
    
    # =================================================================
    # PERFORMANCE MONITORING
    # =================================================================
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        return {
            name: {
                'avg_ms': stats.avg_time * 1000,
                'recent_ms': stats.recent_avg * 1000,
                'count': stats.count,
                'total_ms': stats.total_time * 1000
            }
            for name, stats in self._perf_monitor.get_all_stats().items()
        }
    
    def print_performance_summary(self):
        """Print performance summary"""
        self._perf_monitor.print_summary()
    
    def reset_performance_stats(self):
        """Reset performance monitoring"""
        self._perf_monitor.reset()

