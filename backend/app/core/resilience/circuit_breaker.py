"""
Circuit Breaker Pattern Implementation for External Service Resilience
"""

import asyncio
import time
from typing import Callable, Any, Optional, Dict, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Number of failures to open circuit
    recovery_timeout: float = 60.0  # Seconds to wait before trying recovery
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: float = 30.0  # Request timeout in seconds
    
    # Rate limiting
    max_calls_per_minute: int = 60
    
    # Monitoring
    metrics_window: int = 300  # 5 minutes metrics window


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    circuit_open_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    current_state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    # Rate limiting metrics
    calls_in_current_minute: int = 0
    current_minute: int = field(default_factory=lambda: int(time.time() // 60))
    
    def reset_rate_limit(self):
        """Reset rate limit counters if minute changed"""
        current_minute = int(time.time() // 60)
        if current_minute != self.current_minute:
            self.calls_in_current_minute = 0
            self.current_minute = current_minute


class CircuitBreakerException(Exception):
    """Circuit breaker specific exceptions"""
    pass


class CircuitOpenException(CircuitBreakerException):
    """Raised when circuit is open"""
    pass


class RateLimitExceededException(CircuitBreakerException):
    """Raised when rate limit is exceeded"""
    pass


class CircuitBreaker:
    """
    Circuit Breaker implementation for external service calls
    
    Features:
    - Circuit breaker pattern with three states
    - Rate limiting per service
    - Comprehensive metrics collection
    - Async support with proper context management
    - Configurable timeouts and thresholds
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.metrics = CircuitBreakerMetrics()
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None
        self.lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialized with config: {self.config}")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to execute (can be sync or async)
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenException: When circuit is open
            RateLimitExceededException: When rate limit exceeded
            TimeoutError: When call times out
        """
        async with self.lock:
            # Check rate limiting
            await self._check_rate_limit()
            
            # Check circuit state
            await self._check_circuit_state()
            
            # Record request attempt
            self.metrics.total_requests += 1
            self.metrics.calls_in_current_minute += 1
        
        # Execute the function call
        start_time = time.time()
        try:
            # Handle both sync and async functions
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout
                )
            else:
                # Run sync function in thread pool with timeout
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, func, *args, **kwargs),
                    timeout=self.config.timeout
                )
            
            # Record success
            await self._record_success()
            return result
            
        except asyncio.TimeoutError:
            await self._record_timeout()
            raise TimeoutError(f"Circuit breaker '{self.name}' call timed out after {self.config.timeout}s")
        except Exception as e:
            await self._record_failure(e)
            raise
        finally:
            duration = time.time() - start_time
            logger.debug(f"Circuit breaker '{self.name}' call completed in {duration:.2f}s")
    
    async def _check_rate_limit(self):
        """Check if rate limit is exceeded"""
        self.metrics.reset_rate_limit()
        
        if self.metrics.calls_in_current_minute >= self.config.max_calls_per_minute:
            logger.warning(
                f"Rate limit exceeded for '{self.name}': "
                f"{self.metrics.calls_in_current_minute}/{self.config.max_calls_per_minute} calls per minute"
            )
            raise RateLimitExceededException(
                f"Rate limit exceeded for '{self.name}': max {self.config.max_calls_per_minute} calls per minute"
            )
    
    async def _check_circuit_state(self):
        """Check and potentially update circuit state"""
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            if (self.last_failure_time and 
                current_time - self.last_failure_time >= self.config.recovery_timeout):
                # Try to recover
                self.state = CircuitState.HALF_OPEN
                self.metrics.consecutive_successes = 0
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
            else:
                raise CircuitOpenException(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Will retry in {self.config.recovery_timeout - (current_time - (self.last_failure_time or 0)):.1f}s"
                )
    
    async def _record_success(self):
        """Record successful call"""
        async with self.lock:
            self.metrics.successful_requests += 1
            self.metrics.consecutive_failures = 0
            self.metrics.consecutive_successes += 1
            self.metrics.last_success_time = datetime.utcnow()
            
            # Transition from HALF_OPEN to CLOSED if enough successes
            if (self.state == CircuitState.HALF_OPEN and 
                self.metrics.consecutive_successes >= self.config.success_threshold):
                self.state = CircuitState.CLOSED
                logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED after {self.metrics.consecutive_successes} successes")
    
    async def _record_failure(self, exception: Exception):
        """Record failed call"""
        async with self.lock:
            self.metrics.failed_requests += 1
            self.metrics.consecutive_successes = 0
            self.metrics.consecutive_failures += 1
            self.metrics.last_failure_time = datetime.utcnow()
            self.last_failure_time = time.time()
            
            logger.warning(f"Circuit breaker '{self.name}' recorded failure: {exception}")
            
            # Open circuit if failure threshold reached
            if (self.state == CircuitState.CLOSED and 
                self.metrics.consecutive_failures >= self.config.failure_threshold):
                self.state = CircuitState.OPEN
                self.metrics.circuit_open_count += 1
                logger.error(
                    f"Circuit breaker '{self.name}' OPENED after {self.metrics.consecutive_failures} consecutive failures"
                )
            
            # Go back to OPEN from HALF_OPEN on any failure
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.metrics.circuit_open_count += 1
                logger.error(f"Circuit breaker '{self.name}' returned to OPEN state after failure during recovery")
    
    async def _record_timeout(self):
        """Record timeout as failure"""
        async with self.lock:
            self.metrics.timeouts += 1
        await self._record_failure(TimeoutError("Request timeout"))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit breaker metrics"""
        success_rate = (
            (self.metrics.successful_requests / self.metrics.total_requests * 100)
            if self.metrics.total_requests > 0 else 0
        )
        
        return {
            "name": self.name,
            "state": self.state.value,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "max_calls_per_minute": self.config.max_calls_per_minute
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "timeouts": self.metrics.timeouts,
                "success_rate_percent": round(success_rate, 2),
                "consecutive_failures": self.metrics.consecutive_failures,
                "consecutive_successes": self.metrics.consecutive_successes,
                "circuit_open_count": self.metrics.circuit_open_count,
                "calls_in_current_minute": self.metrics.calls_in_current_minute,
                "last_failure_time": (
                    self.metrics.last_failure_time.isoformat() 
                    if self.metrics.last_failure_time else None
                ),
                "last_success_time": (
                    self.metrics.last_success_time.isoformat() 
                    if self.metrics.last_success_time else None
                )
            }
        }
    
    async def reset(self):
        """Reset circuit breaker to initial state"""
        async with self.lock:
            self.state = CircuitState.CLOSED
            self.metrics = CircuitBreakerMetrics()
            self.last_failure_time = None
            logger.info(f"Circuit breaker '{self.name}' reset to initial state")
    
    async def force_open(self):
        """Force circuit breaker to open state (for testing/emergency)"""
        async with self.lock:
            self.state = CircuitState.OPEN
            self.last_failure_time = time.time()
            self.metrics.circuit_open_count += 1
            logger.warning(f"Circuit breaker '{self.name}' manually forced to OPEN state")
    
    async def force_close(self):
        """Force circuit breaker to close state (for testing/recovery)"""
        async with self.lock:
            self.state = CircuitState.CLOSED
            self.metrics.consecutive_failures = 0
            logger.warning(f"Circuit breaker '{self.name}' manually forced to CLOSED state")


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different services"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self.lock = asyncio.Lock()
    
    def get_circuit_breaker(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)
            logger.info(f"Created new circuit breaker for service '{name}'")
        return self.breakers[name]
    
    async def call_with_circuit_breaker(
        self, 
        service_name: str, 
        func: Callable, 
        *args, 
        config: Optional[CircuitBreakerConfig] = None,
        **kwargs
    ) -> Any:
        """Execute function with circuit breaker protection"""
        breaker = self.get_circuit_breaker(service_name, config)
        return await breaker.call(func, *args, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers"""
        return {name: breaker.get_metrics() for name, breaker in self.breakers.items()}
    
    async def reset_all(self):
        """Reset all circuit breakers"""
        async with self.lock:
            for breaker in self.breakers.values():
                await breaker.reset()
            logger.info("All circuit breakers reset")


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


def circuit_breaker(
    service_name: str, 
    config: Optional[CircuitBreakerConfig] = None
):
    """
    Decorator for applying circuit breaker to functions
    
    Usage:
        @circuit_breaker("openai_service")
        async def call_openai_api():
            # API call implementation
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await circuit_breaker_manager.call_with_circuit_breaker(
                service_name, func, *args, config=config, **kwargs
            )
        return wrapper
    return decorator