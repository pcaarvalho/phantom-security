"""
Unit tests for Circuit Breaker implementation
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock

from app.core.resilience.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState,
    CircuitOpenException, RateLimitExceededException,
    circuit_breaker_manager, circuit_breaker
)


class TestCircuitBreaker:
    """Test CircuitBreaker functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,
            success_threshold=2,
            timeout=0.5,
            max_calls_per_minute=60
        )
        self.breaker = CircuitBreaker("test_service", self.config)
    
    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful function call through circuit breaker"""
        async def success_func():
            return "success"
        
        result = await self.breaker.call(success_func)
        
        assert result == "success"
        assert self.breaker.state == CircuitState.CLOSED
        assert self.breaker.metrics.successful_requests == 1
        assert self.breaker.metrics.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_circuit_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures"""
        async def failing_func():
            raise Exception("Test failure")
        
        # Exceed failure threshold
        for i in range(self.config.failure_threshold):
            with pytest.raises(Exception):
                await self.breaker.call(failing_func)
        
        assert self.breaker.state == CircuitState.OPEN
        assert self.breaker.metrics.failed_requests == self.config.failure_threshold
        
        # Next call should fail immediately with CircuitOpenException
        with pytest.raises(CircuitOpenException):
            await self.breaker.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        """Test circuit breaker transitions to half-open for recovery"""
        async def failing_func():
            raise Exception("Test failure")
        
        # Open the circuit
        for i in range(self.config.failure_threshold):
            with pytest.raises(Exception):
                await self.breaker.call(failing_func)
        
        assert self.breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(self.config.recovery_timeout + 0.1)
        
        # Next call should transition to half-open
        with pytest.raises(Exception):
            await self.breaker.call(failing_func)
        
        assert self.breaker.state == CircuitState.OPEN  # Back to open after failure
    
    @pytest.mark.asyncio
    async def test_successful_recovery(self):
        """Test successful recovery from open to closed state"""
        call_count = 0
        
        async def sometimes_failing_func():
            nonlocal call_count
            call_count += 1
            if call_count <= self.config.failure_threshold:
                raise Exception("Initial failures")
            return "success"
        
        # Open the circuit
        for i in range(self.config.failure_threshold):
            with pytest.raises(Exception):
                await self.breaker.call(sometimes_failing_func)
        
        assert self.breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(self.config.recovery_timeout + 0.1)
        
        # Successful calls during half-open should close circuit
        for i in range(self.config.success_threshold):
            result = await self.breaker.call(sometimes_failing_func)
            assert result == "success"
        
        assert self.breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test circuit breaker timeout handling"""
        async def slow_func():
            await asyncio.sleep(self.config.timeout + 0.2)
            return "too_slow"
        
        with pytest.raises(TimeoutError):
            await self.breaker.call(slow_func)
        
        assert self.breaker.metrics.timeouts == 1
        assert self.breaker.metrics.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # Configure for very low rate limit to test easily
        self.breaker.config.max_calls_per_minute = 2
        
        async def fast_func():
            return "fast"
        
        # First two calls should succeed
        await self.breaker.call(fast_func)
        await self.breaker.call(fast_func)
        
        # Third call should be rate limited
        with pytest.raises(RateLimitExceededException):
            await self.breaker.call(fast_func)
    
    @pytest.mark.asyncio
    async def test_sync_function_support(self):
        """Test circuit breaker with synchronous functions"""
        def sync_func():
            return "sync_success"
        
        result = await self.breaker.call(sync_func)
        assert result == "sync_success"
    
    def test_metrics_collection(self):
        """Test metrics collection and reporting"""
        metrics = self.breaker.get_metrics()
        
        assert isinstance(metrics, dict)
        assert "name" in metrics
        assert "state" in metrics
        assert "config" in metrics
        assert "metrics" in metrics
        assert metrics["name"] == "test_service"
        assert metrics["state"] == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_reset(self):
        """Test circuit breaker reset functionality"""
        # Cause some failures to change state
        async def failing_func():
            raise Exception("Test failure")
        
        with pytest.raises(Exception):
            await self.breaker.call(failing_func)
        
        assert self.breaker.metrics.failed_requests > 0
        
        # Reset circuit
        await self.breaker.reset()
        
        assert self.breaker.state == CircuitState.CLOSED
        assert self.breaker.metrics.failed_requests == 0
        assert self.breaker.metrics.total_requests == 0


class TestCircuitBreakerManager:
    """Test CircuitBreakerManager functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        # Clear any existing breakers
        circuit_breaker_manager.breakers.clear()
    
    def test_get_circuit_breaker(self):
        """Test getting circuit breaker from manager"""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = circuit_breaker_manager.get_circuit_breaker("test_service", config)
        
        assert breaker.name == "test_service"
        assert breaker.config.failure_threshold == 5
        
        # Getting same service should return same instance
        same_breaker = circuit_breaker_manager.get_circuit_breaker("test_service")
        assert breaker is same_breaker
    
    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker(self):
        """Test calling function through manager"""
        async def test_func():
            return "managed_success"
        
        result = await circuit_breaker_manager.call_with_circuit_breaker(
            "managed_service", test_func
        )
        
        assert result == "managed_success"
        assert "managed_service" in circuit_breaker_manager.breakers
    
    def test_get_all_metrics(self):
        """Test getting metrics from all breakers"""
        # Create a few breakers
        circuit_breaker_manager.get_circuit_breaker("service1")
        circuit_breaker_manager.get_circuit_breaker("service2")
        
        metrics = circuit_breaker_manager.get_all_metrics()
        
        assert isinstance(metrics, dict)
        assert "service1" in metrics
        assert "service2" in metrics
    
    @pytest.mark.asyncio
    async def test_reset_all(self):
        """Test resetting all circuit breakers"""
        # Create and use some breakers
        breaker1 = circuit_breaker_manager.get_circuit_breaker("service1")
        breaker2 = circuit_breaker_manager.get_circuit_breaker("service2")
        
        # Cause some activity
        async def test_func():
            return "test"
        
        await breaker1.call(test_func)
        await breaker2.call(test_func)
        
        assert breaker1.metrics.total_requests > 0
        assert breaker2.metrics.total_requests > 0
        
        # Reset all
        await circuit_breaker_manager.reset_all()
        
        assert breaker1.metrics.total_requests == 0
        assert breaker2.metrics.total_requests == 0


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        circuit_breaker_manager.breakers.clear()
    
    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        """Test decorator with async function"""
        
        @circuit_breaker("decorated_service")
        async def decorated_func():
            return "decorated_success"
        
        result = await decorated_func()
        assert result == "decorated_success"
        assert "decorated_service" in circuit_breaker_manager.breakers
    
    @pytest.mark.asyncio
    async def test_sync_function_decorator(self):
        """Test decorator with sync function"""
        
        @circuit_breaker("sync_decorated_service")
        def sync_decorated_func():
            return "sync_decorated_success"
        
        result = await sync_decorated_func()
        assert result == "sync_decorated_success"
        assert "sync_decorated_service" in circuit_breaker_manager.breakers
    
    @pytest.mark.asyncio
    async def test_decorator_with_config(self):
        """Test decorator with custom configuration"""
        config = CircuitBreakerConfig(failure_threshold=10)
        
        @circuit_breaker("configured_service", config)
        async def configured_func():
            return "configured_success"
        
        result = await configured_func()
        assert result == "configured_success"
        
        breaker = circuit_breaker_manager.breakers["configured_service"]
        assert breaker.config.failure_threshold == 10
    
    @pytest.mark.asyncio
    async def test_decorator_failure_handling(self):
        """Test decorator handles failures correctly"""
        
        @circuit_breaker("failing_service", CircuitBreakerConfig(failure_threshold=2))
        async def failing_func():
            raise Exception("Decorator test failure")
        
        # Cause failures
        for _ in range(2):
            with pytest.raises(Exception):
                await failing_func()
        
        # Circuit should be open now
        breaker = circuit_breaker_manager.breakers["failing_service"]
        assert breaker.state == CircuitState.OPEN
        
        # Next call should fail with CircuitOpenException
        with pytest.raises(CircuitOpenException):
            await failing_func()


if __name__ == "__main__":
    pytest.main([__file__])