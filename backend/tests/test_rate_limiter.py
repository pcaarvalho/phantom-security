"""
Unit tests for Rate Limiter implementation
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

from app.core.resilience.rate_limiter import (
    AdaptiveRateLimiter, RateLimitConfig, BackoffStrategy,
    RateLimitExceededException, BackoffCalculator,
    rate_limiter_manager, rate_limited
)


class TestBackoffCalculator:
    """Test BackoffCalculator utility class"""
    
    def test_fixed_delay(self):
        """Test fixed delay backoff strategy"""
        delay = BackoffCalculator.calculate_backoff(
            BackoffStrategy.FIXED_DELAY, 5, 2.0, 60.0
        )
        assert delay == 2.0
    
    def test_linear_backoff(self):
        """Test linear backoff strategy"""
        delay = BackoffCalculator.calculate_backoff(
            BackoffStrategy.LINEAR_BACKOFF, 3, 2.0, 60.0
        )
        assert delay == 6.0  # 2.0 * 3
    
    def test_exponential_backoff(self):
        """Test exponential backoff strategy"""
        delay = BackoffCalculator.calculate_backoff(
            BackoffStrategy.EXPONENTIAL_BACKOFF, 3, 2.0, 60.0, multiplier=2.0
        )
        assert delay == 8.0  # 2.0 * (2.0 ** (3-1))
    
    def test_exponential_backoff_with_jitter(self):
        """Test exponential backoff with jitter"""
        delay = BackoffCalculator.calculate_backoff(
            BackoffStrategy.EXPONENTIAL_BACKOFF_JITTER, 3, 2.0, 60.0, 
            multiplier=2.0, jitter_factor=0.1
        )
        # Should be around 8.0 +/- jitter
        assert 7.2 <= delay <= 8.8  # 8.0 +/- 10%
    
    def test_fibonacci_backoff(self):
        """Test Fibonacci backoff strategy"""
        delay = BackoffCalculator.calculate_backoff(
            BackoffStrategy.FIBONACCI, 5, 1.0, 60.0
        )
        assert delay == 5.0  # 5th Fibonacci number
    
    def test_max_delay_limit(self):
        """Test maximum delay limit is respected"""
        delay = BackoffCalculator.calculate_backoff(
            BackoffStrategy.EXPONENTIAL_BACKOFF, 10, 2.0, 60.0, multiplier=2.0
        )
        assert delay == 60.0  # Should be capped at max_delay


class TestAdaptiveRateLimiter:
    """Test AdaptiveRateLimiter functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.config = RateLimitConfig(
            max_requests=10,
            time_window_seconds=1,
            burst_capacity=5,
            burst_refill_rate=2.0,
            failure_threshold=3
        )
        self.limiter = AdaptiveRateLimiter("test_limiter", self.config)
    
    @pytest.mark.asyncio
    async def test_successful_acquire(self):
        """Test successful token acquisition"""
        success = await self.limiter.acquire()
        assert success is True
        assert self.limiter.metrics.allowed_requests == 1
    
    @pytest.mark.asyncio
    async def test_burst_limit(self):
        """Test burst capacity limiting"""
        # Fill up burst capacity
        for i in range(self.config.burst_capacity):
            success = await self.limiter.acquire()
            assert success is True
        
        # Next request should be rate limited
        with pytest.raises(RateLimitExceededException):
            await self.limiter.acquire()
    
    @pytest.mark.asyncio
    async def test_sliding_window_limit(self):
        """Test sliding window rate limiting"""
        # Allow burst to refill
        await asyncio.sleep(self.config.burst_capacity / self.config.burst_refill_rate + 0.1)
        
        # Fill up the sliding window
        for i in range(self.config.max_requests):
            success = await self.limiter.acquire()
            assert success is True
        
        # Next request should hit sliding window limit
        assert await self.limiter.acquire() is False
        assert self.limiter.metrics.rejected_requests > 0
    
    @pytest.mark.asyncio
    async def test_adaptive_rate_adjustment(self):
        """Test adaptive rate adjustment based on success/failure patterns"""
        # Initial adaptive multiplier should be 1.0
        assert self.limiter.adaptive_multiplier == 1.0
        
        # Simulate some failures to trigger rate reduction
        for _ in range(5):  # More than failure_streak threshold
            self.limiter._record_failure(time.time())
        
        # Rate should be reduced
        assert self.limiter.adaptive_multiplier < 1.0
        
        # Simulate successes to increase rate
        for _ in range(15):  # More than success_streak threshold  
            self.limiter._record_success()
        
        # Rate should increase back towards 1.0
        assert self.limiter.adaptive_multiplier > 0.1
    
    @pytest.mark.asyncio
    async def test_backoff_triggering(self):
        """Test backoff period triggering after consecutive failures"""
        # Cause enough consecutive failures to trigger backoff
        current_time = time.time()
        for _ in range(self.config.failure_threshold):
            self.limiter._record_failure(current_time)
        
        # Should now be in backoff period
        assert self.limiter.backoff_until > current_time
        
        # Requests during backoff should raise exception
        with pytest.raises(RateLimitExceededException) as exc_info:
            await self.limiter.acquire()
        
        assert exc_info.value.retry_after > 0
    
    @pytest.mark.asyncio
    async def test_call_with_rate_limit_success(self):
        """Test calling function with rate limit wrapper - success case"""
        async def test_func():
            return "rate_limited_success"
        
        result = await self.limiter.call_with_rate_limit(test_func)
        assert result == "rate_limited_success"
        assert self.limiter.metrics.allowed_requests == 1
    
    @pytest.mark.asyncio
    async def test_call_with_rate_limit_failure(self):
        """Test calling function with rate limit wrapper - failure case"""
        async def failing_func():
            raise Exception("Test failure")
        
        with pytest.raises(Exception):
            await self.limiter.call_with_rate_limit(failing_func)
        
        # Should record failure for adaptive behavior
        assert self.limiter.consecutive_failures > 0
    
    @pytest.mark.asyncio
    async def test_sync_function_support(self):
        """Test rate limiter with synchronous functions"""
        def sync_func():
            return "sync_success"
        
        result = await self.limiter.call_with_rate_limit(sync_func)
        assert result == "sync_success"
    
    def test_metrics_collection(self):
        """Test metrics collection and reporting"""
        metrics = self.limiter.get_metrics()
        
        assert isinstance(metrics, dict)
        assert "name" in metrics
        assert "config" in metrics
        assert "metrics" in metrics
        assert metrics["name"] == "test_limiter"
        
        # Check specific metrics
        assert "total_requests" in metrics["metrics"]
        assert "allowed_requests" in metrics["metrics"]
        assert "rejected_requests" in metrics["metrics"]
        assert "adaptive_multiplier" in metrics["metrics"]
        assert "token_bucket" in metrics["metrics"]
    
    @pytest.mark.asyncio
    async def test_reset_functionality(self):
        """Test rate limiter reset"""
        # Generate some activity
        await self.limiter.acquire()
        await self.limiter.acquire()
        
        assert self.limiter.metrics.total_requests > 0
        
        # Reset
        await self.limiter.reset()
        
        assert self.limiter.metrics.total_requests == 0
        assert self.limiter.consecutive_failures == 0
        assert self.limiter.backoff_until == 0.0
        assert self.limiter.adaptive_multiplier == 1.0


class TestRateLimiterManager:
    """Test RateLimiterManager functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        rate_limiter_manager.limiters.clear()
    
    def test_get_rate_limiter(self):
        """Test getting rate limiter from manager"""
        config = RateLimitConfig(max_requests=50)
        limiter = rate_limiter_manager.get_rate_limiter("test_service", config)
        
        assert limiter.name == "test_service"
        assert limiter.config.max_requests == 50
        
        # Getting same service should return same instance
        same_limiter = rate_limiter_manager.get_rate_limiter("test_service")
        assert limiter is same_limiter
    
    @pytest.mark.asyncio
    async def test_call_with_rate_limit(self):
        """Test calling function through manager"""
        async def test_func():
            return "managed_success"
        
        result = await rate_limiter_manager.call_with_rate_limit(
            "managed_service", test_func
        )
        
        assert result == "managed_success"
        assert "managed_service" in rate_limiter_manager.limiters
    
    def test_get_all_metrics(self):
        """Test getting metrics from all rate limiters"""
        # Create a few limiters
        rate_limiter_manager.get_rate_limiter("service1")
        rate_limiter_manager.get_rate_limiter("service2")
        
        metrics = rate_limiter_manager.get_all_metrics()
        
        assert isinstance(metrics, dict)
        assert "service1" in metrics
        assert "service2" in metrics
    
    @pytest.mark.asyncio
    async def test_reset_all(self):
        """Test resetting all rate limiters"""
        # Create and use some limiters
        limiter1 = rate_limiter_manager.get_rate_limiter("service1")
        limiter2 = rate_limiter_manager.get_rate_limiter("service2")
        
        # Cause some activity
        await limiter1.acquire()
        await limiter2.acquire()
        
        assert limiter1.metrics.total_requests > 0
        assert limiter2.metrics.total_requests > 0
        
        # Reset all
        await rate_limiter_manager.reset_all()
        
        assert limiter1.metrics.total_requests == 0
        assert limiter2.metrics.total_requests == 0


class TestRateLimitedDecorator:
    """Test rate_limited decorator functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        rate_limiter_manager.limiters.clear()
    
    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        """Test decorator with async function"""
        
        @rate_limited("decorated_service")
        async def decorated_func():
            return "decorated_success"
        
        result = await decorated_func()
        assert result == "decorated_success"
        assert "decorated_service" in rate_limiter_manager.limiters
    
    @pytest.mark.asyncio
    async def test_sync_function_decorator(self):
        """Test decorator with sync function"""
        
        @rate_limited("sync_decorated_service")
        def sync_decorated_func():
            return "sync_decorated_success"
        
        result = await sync_decorated_func()
        assert result == "sync_decorated_success"
        assert "sync_decorated_service" in rate_limiter_manager.limiters
    
    @pytest.mark.asyncio
    async def test_decorator_with_config(self):
        """Test decorator with custom configuration"""
        config = RateLimitConfig(max_requests=100)
        
        @rate_limited("configured_service", config)
        async def configured_func():
            return "configured_success"
        
        result = await configured_func()
        assert result == "configured_success"
        
        limiter = rate_limiter_manager.limiters["configured_service"]
        assert limiter.config.max_requests == 100
    
    @pytest.mark.asyncio
    async def test_decorator_rate_limiting(self):
        """Test decorator actually applies rate limiting"""
        # Use very restrictive config
        config = RateLimitConfig(
            max_requests=1,
            time_window_seconds=1,
            burst_capacity=1,
            burst_refill_rate=0.5
        )
        
        @rate_limited("limiting_service", config)
        async def limited_func():
            return "limited_success"
        
        # First call should succeed
        result = await limited_func()
        assert result == "limited_success"
        
        # Second call should be rate limited
        with pytest.raises(RateLimitExceededException):
            await limited_func()


class TestTokenBucket:
    """Test TokenBucket functionality"""
    
    def test_token_consumption(self):
        """Test basic token consumption"""
        from app.core.resilience.rate_limiter import TokenBucket
        
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        
        # Should start full
        assert bucket.tokens == 10.0
        
        # Consume some tokens
        assert bucket.try_consume(5) is True
        assert bucket.tokens == 5.0
        
        # Try to consume more than available
        assert bucket.try_consume(10) is False
        assert bucket.tokens == 5.0  # Should be unchanged
    
    def test_token_refill(self):
        """Test token bucket refill over time"""
        from app.core.resilience.rate_limiter import TokenBucket
        
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens per second
        
        # Consume all tokens
        assert bucket.try_consume(10) is True
        assert bucket.tokens == 0.0
        
        # Wait for refill (simulate time passing)
        time.sleep(0.5)  # 0.5 seconds
        bucket._refill()  # Manually trigger refill
        
        # Should have refilled approximately 5 tokens (10 * 0.5)
        assert bucket.tokens >= 4.5  # Allow for small timing variations
        assert bucket.tokens <= 5.5
    
    def test_capacity_limit(self):
        """Test token bucket respects capacity limit"""
        from app.core.resilience.rate_limiter import TokenBucket
        
        bucket = TokenBucket(capacity=5, refill_rate=10.0)
        
        # Start with capacity
        assert bucket.tokens == 5.0
        
        # Wait and refill - should not exceed capacity
        time.sleep(1.0)
        bucket._refill()
        
        assert bucket.tokens == 5.0  # Should not exceed capacity


if __name__ == "__main__":
    pytest.main([__file__])