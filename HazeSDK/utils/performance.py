"""
Performance Monitoring
======================

Track SDK performance and identify bottlenecks.
"""

import time
from typing import Dict, List
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class TimingStats:
    """Statistics for a timed operation"""
    name: str
    total_time: float = 0.0
    count: int = 0
    min_time: float = float('inf')
    max_time: float = 0.0
    recent_times: List[float] = field(default_factory=list)
    
    @property
    def avg_time(self) -> float:
        """Average time per operation"""
        return self.total_time / self.count if self.count > 0 else 0.0
    
    @property
    def recent_avg(self) -> float:
        """Average of recent operations (last 100)"""
        if not self.recent_times:
            return 0.0
        return sum(self.recent_times) / len(self.recent_times)
    
    def add_time(self, elapsed: float):
        """Record a new timing"""
        self.total_time += elapsed
        self.count += 1
        self.min_time = min(self.min_time, elapsed)
        self.max_time = max(self.max_time, elapsed)
        
        # Keep last 100 for recent average
        self.recent_times.append(elapsed)
        if len(self.recent_times) > 100:
            self.recent_times.pop(0)


class PerformanceMonitor:
    """
    Monitor SDK performance.
    
    Features:
    - Context manager for easy timing
    - Detailed statistics
    - Operation tracking
    """
    
    def __init__(self):
        self._stats: Dict[str, TimingStats] = {}
        self._enabled = True
    
    @contextmanager
    def time_operation(self, name: str):
        """
        Context manager to time an operation.
        
        Usage:
            with monitor.time_operation("read_memory"):
                # ... code to time ...
        """
        if not self._enabled:
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.record(name, elapsed)
    
    def record(self, name: str, elapsed: float):
        """Record a timing manually"""
        if not self._enabled:
            return
        
        if name not in self._stats:
            self._stats[name] = TimingStats(name)
        
        self._stats[name].add_time(elapsed)
    
    def get_stats(self, name: str) -> TimingStats:
        """Get statistics for an operation"""
        return self._stats.get(name, TimingStats(name))
    
    def get_all_stats(self) -> Dict[str, TimingStats]:
        """Get all statistics"""
        return self._stats.copy()
    
    def reset(self):
        """Reset all statistics"""
        self._stats.clear()
    
    def enable(self):
        """Enable monitoring"""
        self._enabled = True
    
    def disable(self):
        """Disable monitoring (for production)"""
        self._enabled = False
    
    def print_summary(self):
        """Print a summary of all operations"""
        if not self._stats:
            print("No performance data collected")
            return
        
        print("\n" + "="*70)
        print("Performance Summary")
        print("="*70)
        print(f"{'Operation':<30} {'Calls':<10} {'Avg (ms)':<12} {'Recent (ms)'}")
        print("-"*70)
        
        for name, stats in sorted(self._stats.items(), key=lambda x: x[1].total_time, reverse=True):
            print(f"{name:<30} {stats.count:<10} {stats.avg_time*1000:<12.3f} {stats.recent_avg*1000:.3f}")
        
        print("="*70 + "\n")

