
"""
Adaptive Backpressure System
Dynamically adjusts system concurrency/throughput based on resource usage.
"""

import time
import logging
import psutil
from typing import Optional, Tuple
from services.network.pid import PIDController

logger = logging.getLogger(__name__)

class AdaptiveBackpressure:
    _instance = None

    def __init__(self, target_cpu_percent: float = 75.0, min_concurrency: int = 1, max_concurrency: int = 50):
        self.target_cpu = target_cpu_percent
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        
        # PID Controller
        # Kp: Proportional gain (reaction speed)
        # Ki: Integral gain (steady state error elimination)
        # Kd: Derivative gain (dampening)
        self.pid = PIDController(Kp=0.2, Ki=0.05, Kd=0.1, setpoint=target_cpu_percent)
        self.pid.set_output_limits(-10, 10) # Max adjustment per step
        
        self._current_concurrency = float(max_concurrency / 2) # Start middle
        self._last_update = time.time()
        self._update_interval = 2.0 # Update every 2 seconds
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def update(self) -> float:
        """
        Update controller and return suggested concurrency.
        Should be called periodically.
        """
        now = time.time()
        if now - self._last_update < self._update_interval:
            return self._current_concurrency

        try:
            # Metric: CPU Usage (System wide)
            # interval=None means non-blocking (from last call)
            cpu = psutil.cpu_percent(interval=None)
            
            # Metric: Memory Usage (Protect against OOM)
            mem = psutil.virtual_memory().percent
            
            # Feedback Loop
            # If Memory is critical (>90%), force reduce significantly
            if mem > 90.0:
                adjustment = -5.0
                logger.warning(f"High Memory ({mem}%), reducing concurrency!")
            else:
                # PID based on CPU
                # Error = Setpoint - ProcessVariable
                # If CPU (80) > Target (70) -> Error -10. Output negative.
                # We want CPU to match Target.
                adjustment = self.pid.update(cpu)
            
            self._current_concurrency += adjustment
            
            # Clamp logic
            self._current_concurrency = max(
                float(self.min_concurrency), 
                min(float(self.max_concurrency), self._current_concurrency)
            )
            
            self._last_update = now
            return self._current_concurrency
            
        except Exception as e:
            logger.error(f"Backpressure update failed: {e}")
            return self._current_concurrency

    @property
    def concurrency_limit(self) -> int:
        return int(self.update())

    def should_throttle(self) -> bool:
        """Returns True if system is overloaded beyond recovery range."""
        return psutil.cpu_percent(interval=None) > 95.0 or psutil.virtual_memory().percent > 95.0

