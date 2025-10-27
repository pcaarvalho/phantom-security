"""
Rate Limiting and Throttling System with Intelligent Backoff Strategies
"""

import asyncio
import time
import math
import random
from typing import Dict, Optional, Callable, Any, Union, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Backoff strategy types"""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"
    FIBONACCI = "fibonacci"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    # Basic rate limiting
    max_requests: int = 100
    time_window_seconds: int = 60
    
    # Burst handling
    burst_capacity: int = 10
    burst_refill_rate: float = 1.0  # tokens per second
    
    # Backoff configuration
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 300.0  # 5 minutes max
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    
    # Circuit breaker integration
    failure_threshold: int = 5
    reset_after_seconds: int = 300


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""
    capacity: int
    tokens: float = field(init=False)
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)
    
    def __post_init__(self):
        self.tokens = float(self.capacity)
    
    def try_consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket"""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on time passed"""
        now = time.time()
        elapsed = now - self.last_refill
        self.last_refill = now
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)


@dataclass
class RateLimitMetrics:
    """Rate limiting metrics"""
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    backoff_triggered: int = 0
    current_backoff_seconds: float = 0.0
    consecutive_failures: int = 0
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    
    # Time window metrics
    requests_in_current_window: int = 0
    current_window_start: float = field(default_factory=time.time)
    
    def reset_window_if_needed(self, window_seconds: int):
        """Reset window counters if window expired"""
        now = time.time()
        if now - self.current_window_start >= window_seconds:
            self.requests_in_current_window = 0
            self.current_window_start = now


class RateLimitExceededException(Exception):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class BackoffCalculator:
    """Calculates backoff delays using various strategies"""
    
    @staticmethod
    def calculate_backoff(
        strategy: BackoffStrategy,
        attempt: int,
        initial_delay: float,
        max_delay: float,
        multiplier: float = 2.0,
        jitter_factor: float = 0.1
    ) -> float:
        """Calculate backoff delay based on strategy"""
        
        if strategy == BackoffStrategy.FIXED:
            delay = initial_delay
            
        elif strategy == BackoffStrategy.LINEAR:
            delay = initial_delay * attempt
            
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = initial_delay * (multiplier ** (attempt - 1))
            
        elif strategy == BackoffStrategy.EXPONENTIAL_JITTER:
            delay = initial_delay * (multiplier ** (attempt - 1))
            # Add jitter to prevent thundering herd
            jitter = delay * jitter_factor * (random.random() - 0.5)
            delay += jitter
            
        elif strategy == BackoffStrategy.FIBONACCI:
            delay = initial_delay * BackoffCalculator._fibonacci(attempt)
            
        else:
            delay = initial_delay
        
        # Ensure delay is within bounds
        delay = max(0, min(max_delay, delay))
        return delay
    
    @staticmethod
    def _fibonacci(n: int) -> int:
        """Calculate nth Fibonacci number"""
        if n <= 1:
            return 1
        
        a, b = 1, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b


class AdaptiveRateLimiter:
    """
    Advanced rate limiter with intelligent backoff and adaptive behavior
    
    Features:
    - Token bucket algorithm for smooth rate limiting
    - Multiple backoff strategies
    - Adaptive rate adjustment based on service health
    - Comprehensive metrics collection
    - Integration with circuit breaker pattern
    """
    
    def __init__(self, name: str, config: Optional[RateLimitConfig] = None):
        self.name = name
        self.config = config or RateLimitConfig()
        self.metrics = RateLimitMetrics()
        
        # Token bucket for burst handling
        self.token_bucket = TokenBucket(
            capacity=self.config.burst_capacity,
            refill_rate=self.config.burst_refill_rate
        )
        
        # Sliding window for rate limiting
        self.request_times: List[float] = []
        
        # Backoff state
        self.consecutive_failures = 0
        self.last_failure_time: Optional[float] = None
        self.backoff_until: float = 0.0
        
        # Adaptive rate adjustment
        self.adaptive_multiplier = 1.0  # Start with normal rate
        self.success_streak = 0
        self.failure_streak = 0
        
        self.lock = asyncio.Lock()
        
        logger.info(f"Rate limiter '{name}' initialized with config: {self.config}")
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens for request
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False if rate limited
            
        Raises:
            RateLimitExceededException: If rate limit exceeded with backoff info
        """
        async with self.lock:
            current_time = time.time()
            
            # Check if we're in backoff period
            if current_time < self.backoff_until:
                retry_after = self.backoff_until - current_time
                self.metrics.rejected_requests += 1
                raise RateLimitExceededException(
                    f"Rate limiter '{self.name}' in backoff period", 
                    retry_after=retry_after
                )
            
            # Update metrics window
            self.metrics.reset_window_if_needed(self.config.time_window_seconds)
            self.metrics.total_requests += 1
            
            # Check sliding window rate limit
            if not self._check_sliding_window(current_time, tokens):
                return False
            
            # Check token bucket (for burst control)
            if not self.token_bucket.try_consume(tokens):
                self.metrics.rejected_requests += 1
                retry_after = self._calculate_retry_after()
                raise RateLimitExceededException(
                    f"Rate limiter '{self.name}' token bucket exhausted",
                    retry_after=retry_after
                )
            
            # Request allowed
            self.metrics.allowed_requests += 1
            self.metrics.requests_in_current_window += tokens
            self._record_success()
            
            return True
    
    def _check_sliding_window(self, current_time: float, tokens: int) -> bool:
        """Check if request fits within sliding window rate limit"""
        window_start = current_time - self.config.time_window_seconds
        
        # Remove old requests
        self.request_times = [t for t in self.request_times if t > window_start]
        
        # Apply adaptive rate adjustment
        adjusted_max_requests = int(self.config.max_requests * self.adaptive_multiplier)
        
        # Check if adding this request would exceed limit
        if len(self.request_times) + tokens > adjusted_max_requests:
            self.metrics.rejected_requests += 1
            self._record_failure(current_time)
            return False
        
        # Add current request times
        for _ in range(tokens):
            self.request_times.append(current_time)
        
        return True
    
    def _record_success(self):
        """Record successful request"""
        self.consecutive_failures = 0
        self.failure_streak = 0
        self.success_streak += 1
        self.metrics.last_success_time = datetime.utcnow()
        
        # Gradually increase rate if service is healthy
        if self.success_streak > 10 and self.adaptive_multiplier < 1.0:
            self.adaptive_multiplier = min(1.0, self.adaptive_multiplier + 0.1)
            logger.debug(f"Rate limiter '{self.name}' increasing rate multiplier to {self.adaptive_multiplier:.2f}")
    
    def _record_failure(self, current_time: float):
        """Record failed request and potentially trigger backoff"""
        self.consecutive_failures += 1
        self.success_streak = 0
        self.failure_streak += 1
        self.last_failure_time = current_time
        self.metrics.last_failure_time = datetime.utcnow()
        
        # Reduce adaptive rate on failures
        if self.failure_streak > 3:
            self.adaptive_multiplier = max(0.1, self.adaptive_multiplier - 0.2)
            logger.debug(f"Rate limiter '{self.name}' reducing rate multiplier to {self.adaptive_multiplier:.2f}")
        
        # Trigger backoff if too many consecutive failures
        if self.consecutive_failures >= self.config.failure_threshold:
            self._trigger_backoff(current_time)
    
    def _trigger_backoff(self, current_time: float):
        """Trigger backoff period"""
        backoff_delay = BackoffCalculator.calculate_backoff(
            strategy=self.config.backoff_strategy,
            attempt=min(self.consecutive_failures, 10),  # Cap attempts for calculation
            initial_delay=self.config.initial_backoff_seconds,
            max_delay=self.config.max_backoff_seconds,
            multiplier=self.config.backoff_multiplier,
            jitter_factor=self.config.jitter_factor
        )
        
        self.backoff_until = current_time + backoff_delay
        self.metrics.backoff_triggered += 1
        self.metrics.current_backoff_seconds = backoff_delay
        
        logger.warning(
            f"Rate limiter '{self.name}' triggered backoff for {backoff_delay:.2f}s "
            f"after {self.consecutive_failures} consecutive failures"
        )
    
    def _calculate_retry_after(self) -> float:
        """Calculate retry-after time for client"""
        # Base retry on token bucket refill time
        tokens_needed = 1
        tokens_available = self.token_bucket.tokens
        
        if tokens_needed > tokens_available:
            tokens_to_wait = tokens_needed - tokens_available
            retry_after = tokens_to_wait / self.config.burst_refill_rate
        else:
            retry_after = 1.0 / self.config.burst_refill_rate
        
        # Add some jitter
        jitter = retry_after * 0.1 * random.random()
        return retry_after + jitter
    
    async def call_with_rate_limit(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with rate limiting protection"""
        await self.acquire()
        
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return await asyncio.get_event_loop().run_in_executor(
                    None, func, *args, **kwargs
                )
        except Exception as e:
            # Record failure for adaptive behavior
            async with self.lock:
                self._record_failure(time.time())
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current rate limiter metrics"""
        current_time = time.time()
        
        return {
            "name": self.name,
            "config": {
                "max_requests": self.config.max_requests,
                "time_window_seconds": self.config.time_window_seconds,
                "burst_capacity": self.config.burst_capacity,
                "backoff_strategy": self.config.backoff_strategy.value
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "allowed_requests": self.metrics.allowed_requests,
                "rejected_requests": self.metrics.rejected_requests,
                "rejection_rate_percent": (
                    (self.metrics.rejected_requests / self.metrics.total_requests * 100)
                    if self.metrics.total_requests > 0 else 0
                ),
                "requests_in_current_window": self.metrics.requests_in_current_window,
                "backoff_triggered": self.metrics.backoff_triggered,
                "current_backoff_seconds": max(0, self.backoff_until - current_time),
                "adaptive_multiplier": self.adaptive_multiplier,
                "consecutive_failures": self.consecutive_failures,
                "success_streak": self.success_streak,
                "failure_streak": self.failure_streak,
                "token_bucket": {
                    "tokens": self.token_bucket.tokens,
                    "capacity": self.token_bucket.capacity,
                    "refill_rate": self.token_bucket.refill_rate
                }
            }
        }
    
    async def reset(self):
        """Reset rate limiter to initial state"""
        async with self.lock:
            self.metrics = RateLimitMetrics()
            self.request_times.clear()
            self.consecutive_failures = 0
            self.backoff_until = 0.0
            self.adaptive_multiplier = 1.0
            self.success_streak = 0
            self.failure_streak = 0
            self.token_bucket.tokens = float(self.token_bucket.capacity)
            logger.info(f"Rate limiter '{self.name}' reset to initial state")


class RateLimiterManager:
    """Manages multiple rate limiters for different services"""
    
    def __init__(self):
        self.limiters: Dict[str, AdaptiveRateLimiter] = {}
        self.lock = asyncio.Lock()
    
    def get_rate_limiter(
        self, 
        name: str, 
        config: Optional[RateLimitConfig] = None
    ) -> AdaptiveRateLimiter:
        """Get or create rate limiter for service"""
        if name not in self.limiters:
            self.limiters[name] = AdaptiveRateLimiter(name, config)
            logger.info(f"Created new rate limiter for service '{name}'")
        return self.limiters[name]
    
    async def call_with_rate_limit(
        self, 
        service_name: str, 
        func: Callable, 
        *args,
        config: Optional[RateLimitConfig] = None,
        **kwargs
    ) -> Any:
        """Execute function with rate limiting protection"""
        limiter = self.get_rate_limiter(service_name, config)
        return await limiter.call_with_rate_limit(func, *args, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all rate limiters"""
        return {name: limiter.get_metrics() for name, limiter in self.limiters.items()}
    
    async def reset_all(self):
        """Reset all rate limiters"""
        async with self.lock:
            for limiter in self.limiters.values():
                await limiter.reset()
            logger.info("All rate limiters reset")


# Global rate limiter manager
rate_limiter_manager = RateLimiterManager()


def rate_limited(
    service_name: str,
    config: Optional[RateLimitConfig] = None
):
    """
    Decorator for applying rate limiting to functions
    
    Usage:
        @rate_limited("openai_api", RateLimitConfig(max_requests=50))
        async def call_openai():
            # API call implementation
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await rate_limiter_manager.call_with_rate_limit(
                service_name, func, *args, config=config, **kwargs
            )
        return wrapper
    return decorator