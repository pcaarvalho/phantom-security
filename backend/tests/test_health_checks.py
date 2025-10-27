"""
Unit tests for Health Check system
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from app.core.resilience.health_checks import (
    HealthCheckManager, BaseHealthCheck, DatabaseHealthCheck,
    RedisHealthCheck, OpenAIHealthCheck, SystemResourcesHealthCheck,
    NetworkConnectivityHealthCheck, HealthStatus, HealthCheckResult,
    HealthCheckConfig, health_manager
)


class MockHealthCheck(BaseHealthCheck):
    """Mock health check for testing"""
    
    def __init__(self, name: str, should_pass: bool = True, delay: float = 0.0):
        super().__init__(name)
        self.should_pass = should_pass
        self.delay = delay
    
    async def check_health(self) -> HealthCheckResult:
        """Mock health check implementation"""
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        
        if self.should_pass:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=self.delay * 1000,
                timestamp=asyncio.get_event_loop().time(),
                details={"test": "passed"}
            )
        else:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=self.delay * 1000,
                timestamp=asyncio.get_event_loop().time(),
                error="Mock failure",
                details={"test": "failed"}
            )


class TestHealthCheckResult:
    """Test HealthCheckResult functionality"""
    
    def test_to_dict(self):
        """Test converting health check result to dictionary"""
        from datetime import datetime
        
        result = HealthCheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            response_time_ms=123.45,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            details={"key": "value"},
            metrics={"count": 42}
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["name"] == "test_check"
        assert result_dict["status"] == "healthy"
        assert result_dict["response_time_ms"] == 123.45
        assert result_dict["details"] == {"key": "value"}
        assert result_dict["metrics"] == {"count": 42}
        assert result_dict["error"] is None


class TestBaseHealthCheck:
    """Test BaseHealthCheck functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.config = HealthCheckConfig(
            timeout_seconds=1.0,
            retry_attempts=2,
            retry_delay_seconds=0.1
        )
    
    @pytest.mark.asyncio
    async def test_successful_check(self):
        """Test successful health check execution"""
        check = MockHealthCheck("test_success", should_pass=True)
        check.config = self.config
        
        result = await check.execute_check()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.name == "test_success"
        assert check.consecutive_failures == 0
        assert check.consecutive_successes == 1
        assert check.total_checks == 1
        assert check.total_failures == 0
    
    @pytest.mark.asyncio
    async def test_failing_check(self):
        """Test failing health check execution"""
        check = MockHealthCheck("test_failure", should_pass=False)
        check.config = self.config
        
        result = await check.execute_check()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Mock failure"
        assert check.consecutive_failures == 1
        assert check.consecutive_successes == 0
        assert check.total_checks == 1
        assert check.total_failures == 1
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test health check timeout handling"""
        # Create check that takes longer than timeout
        check = MockHealthCheck("test_timeout", should_pass=True, delay=2.0)
        check.config = self.config
        
        result = await check.execute_check()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.error
        assert check.total_failures == 1
    
    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test health check retry logic"""
        call_count = 0
        
        class RetryMockCheck(BaseHealthCheck):
            async def check_health(self):
                nonlocal call_count
                call_count += 1
                if call_count < 2:  # Fail first attempt, succeed second
                    raise Exception("Retry test failure")
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=0,
                    timestamp=asyncio.get_event_loop().time()
                )
        
        check = RetryMockCheck("retry_test")
        check.config = self.config
        
        result = await check.execute_check()
        
        assert result.status == HealthStatus.HEALTHY
        assert call_count == 2  # Should have retried once
        assert check.total_checks == 1  # But only count as one overall check
    
    @pytest.mark.asyncio
    async def test_disabled_check(self):
        """Test disabled health check"""
        check = MockHealthCheck("disabled_test", should_pass=True)
        check.config.enabled = False
        
        result = await check.execute_check()
        
        assert result.status == HealthStatus.UNKNOWN
        assert "disabled" in result.details["message"]
    
    @pytest.mark.asyncio
    async def test_slow_response_thresholds(self):
        """Test slow response time threshold handling"""
        check = MockHealthCheck("slow_test", should_pass=True, delay=0.1)
        check.config = HealthCheckConfig(
            warning_response_time_ms=50,
            critical_response_time_ms=200
        )
        
        result = await check.execute_check()
        
        # 100ms delay should trigger warning threshold
        assert result.status == HealthStatus.DEGRADED
        assert result.details.get("slow_response") is True
    
    def test_statistics(self):
        """Test health check statistics collection"""
        check = MockHealthCheck("stats_test")
        check.total_checks = 10
        check.total_failures = 2
        check.consecutive_failures = 0
        check.consecutive_successes = 5
        
        stats = check.get_statistics()
        
        assert stats["total_checks"] == 10
        assert stats["total_failures"] == 2
        assert stats["success_rate_percent"] == 80.0
        assert stats["consecutive_successes"] == 5


class TestHealthCheckManager:
    """Test HealthCheckManager functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.manager = HealthCheckManager()
        # Clear default checks for isolated testing
        self.manager.health_checks.clear()
    
    def test_register_health_check(self):
        """Test registering custom health check"""
        check = MockHealthCheck("custom_check")
        self.manager.register_health_check(check)
        
        assert "custom_check" in self.manager.health_checks
        assert self.manager.health_checks["custom_check"] is check
    
    @pytest.mark.asyncio
    async def test_check_all_success(self):
        """Test checking all health checks - success scenario"""
        # Register some mock checks
        self.manager.register_health_check(MockHealthCheck("check1", should_pass=True))
        self.manager.register_health_check(MockHealthCheck("check2", should_pass=True))
        
        result = await self.manager.check_all()
        
        assert result["status"] == "healthy"
        assert result["total_checks"] == 2
        assert result["successful_checks"] == 2
        assert result["failed_checks"] == 0
        assert "check1" in result["checks"]
        assert "check2" in result["checks"]
    
    @pytest.mark.asyncio
    async def test_check_all_with_failures(self):
        """Test checking all health checks - with failures"""
        # Register mixed success/failure checks
        self.manager.register_health_check(MockHealthCheck("success_check", should_pass=True))
        
        failing_check = MockHealthCheck("failing_check", should_pass=False)
        failing_check.config.critical = False  # Non-critical failure
        self.manager.register_health_check(failing_check)
        
        result = await self.manager.check_all()
        
        assert result["status"] == "degraded"  # Should be degraded, not unhealthy
        assert result["total_checks"] == 2
        assert result["successful_checks"] == 1
        assert result["failed_checks"] == 1
        assert result["critical_failures"] == 0
    
    @pytest.mark.asyncio
    async def test_check_all_critical_failure(self):
        """Test checking all health checks - with critical failure"""
        # Register success and critical failure
        self.manager.register_health_check(MockHealthCheck("success_check", should_pass=True))
        
        critical_check = MockHealthCheck("critical_check", should_pass=False)
        critical_check.config.critical = True
        self.manager.register_health_check(critical_check)
        
        result = await self.manager.check_all()
        
        assert result["status"] == "unhealthy"  # Should be unhealthy due to critical failure
        assert result["critical_failures"] == 1
    
    @pytest.mark.asyncio
    async def test_check_single(self):
        """Test checking single health check"""
        check = MockHealthCheck("single_check", should_pass=True)
        self.manager.register_health_check(check)
        
        result = await self.manager.check_single("single_check")
        
        assert result is not None
        assert result["name"] == "single_check"
        assert result["status"] == "healthy"
        
        # Non-existent check should return None
        result = await self.manager.check_single("non_existent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Test health checks execute concurrently"""
        # Add checks with delays to test concurrency
        self.manager.register_health_check(MockHealthCheck("slow1", should_pass=True, delay=0.1))
        self.manager.register_health_check(MockHealthCheck("slow2", should_pass=True, delay=0.1))
        self.manager.register_health_check(MockHealthCheck("slow3", should_pass=True, delay=0.1))
        
        start_time = asyncio.get_event_loop().time()
        result = await self.manager.check_all()
        end_time = asyncio.get_event_loop().time()
        
        # Should take roughly 0.1 seconds (concurrent) not 0.3 seconds (sequential)
        total_time = end_time - start_time
        assert total_time < 0.2  # Allow some overhead
        assert result["status"] == "healthy"
    
    def test_statistics(self):
        """Test health check manager statistics"""
        # Add some checks with history
        check1 = MockHealthCheck("stats1")
        check1.total_checks = 10
        check1.total_failures = 1
        
        check2 = MockHealthCheck("stats2")
        check2.total_checks = 20
        check2.total_failures = 0
        
        self.manager.register_health_check(check1)
        self.manager.register_health_check(check2)
        
        # Add some history
        self.manager.check_history = [
            {"success_rate_percent": 90, "total_response_time_ms": 100, "timestamp": "2024-01-01T12:00:00"},
            {"success_rate_percent": 95, "total_response_time_ms": 120, "timestamp": "2024-01-01T12:01:00"}
        ]
        
        stats = self.manager.get_statistics()
        
        assert "stats1" in stats
        assert "stats2" in stats
        assert "overall" in stats
        assert stats["overall"]["total_health_checks"] == 2
        assert stats["overall"]["average_success_rate_percent"] == 92.5
    
    def test_history_management(self):
        """Test health check history management"""
        # Test history size limit
        self.manager.max_history_size = 3
        
        for i in range(5):
            self.manager._add_to_history({"test": i})
        
        assert len(self.manager.check_history) == 3
        assert self.manager.check_history[0]["test"] == 2  # Should keep last 3
        
        # Test get_history with limit
        history = self.manager.get_history(limit=2)
        assert len(history) == 2


class TestSpecificHealthChecks:
    """Test specific health check implementations"""
    
    @pytest.mark.asyncio
    @patch('app.core.resilience.health_checks.engine')
    async def test_database_health_check(self, mock_engine):
        """Test database health check"""
        # Mock successful database connection
        mock_connection = MagicMock()
        mock_result = MagicMock()
        mock_row = (1, "2024-01-01 12:00:00")
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        
        check = DatabaseHealthCheck()
        result = await check.check_health()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.details["connection"] == "successful"
        assert result.details["test_query"] == "passed"
        assert "query_time_ms" in result.metrics
    
    @pytest.mark.asyncio
    @patch('aioredis.from_url')
    async def test_redis_health_check(self, mock_redis_from_url):
        """Test Redis health check"""
        # Mock successful Redis operations
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"phantom_health_check")
        mock_redis.delete = AsyncMock()
        mock_redis.info = AsyncMock(return_value={
            "redis_version": "6.0.0",
            "connected_clients": 5,
            "used_memory": 1024000
        })
        mock_redis.close = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        check = RedisHealthCheck()
        result = await check.check_health()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.details["connection"] == "successful"
        assert result.details["set_get_delete"] == "passed"
        assert "redis_version" in result.details
    
    @pytest.mark.asyncio
    @patch('openai.AsyncOpenAI')
    async def test_openai_health_check(self, mock_openai):
        """Test OpenAI health check"""
        # Mock successful OpenAI API call
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        mock_response.model = "gpt-3.5-turbo"
        mock_response.usage.total_tokens = 10
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client
        
        with patch('app.core.resilience.health_checks.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            
            check = OpenAIHealthCheck()
            result = await check.check_health()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.details["api_connection"] == "successful"
        assert result.details["model_response"] == "received"
    
    @pytest.mark.asyncio
    @patch('psutil.cpu_percent', return_value=25.0)
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    async def test_system_resources_health_check(self, mock_disk, mock_memory, mock_cpu):
        """Test system resources health check"""
        # Mock system resource data
        mock_memory.return_value.percent = 60.0
        mock_memory.return_value.available = 4 * 1024**3  # 4GB
        mock_memory.return_value.total = 8 * 1024**3     # 8GB
        
        mock_disk.return_value.used = 50 * 1024**3     # 50GB
        mock_disk.return_value.total = 100 * 1024**3    # 100GB
        mock_disk.return_value.free = 50 * 1024**3      # 50GB
        
        check = SystemResourcesHealthCheck()
        result = await check.check_health()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.details["cpu_usage_percent"] == 25.0
        assert result.details["memory_usage_percent"] == 60.0
        assert result.details["disk_usage_percent"] == 50.0
        assert result.details["cpu_status"] == "good"
        assert result.details["memory_status"] == "good"
        assert result.details["disk_status"] == "good"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_network_connectivity_health_check(self, mock_client_class):
        """Test network connectivity health check"""
        # Mock successful HTTP responses
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        check = NetworkConnectivityHealthCheck(
            test_urls=["https://example.com", "https://test.com"]
        )
        result = await check.check_health()
        
        assert result.status == HealthStatus.HEALTHY
        assert len(result.details["connectivity_tests"]) == 2
        assert all(test["status"] == "success" for test in result.details["connectivity_tests"])
        assert result.metrics["success_rate_percent"] == 100.0


if __name__ == "__main__":
    pytest.main([__file__])