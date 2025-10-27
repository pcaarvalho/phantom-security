"""
Comprehensive Health Check System with Detailed Service Monitoring
"""

import asyncio
import time
import psutil
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
from abc import ABC, abstractmethod
import aioredis
import httpx
import subprocess
import openai
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckType(Enum):
    """Types of health checks"""
    DATABASE = "database"
    REDIS = "redis"
    EXTERNAL_API = "external_api"
    FILE_SYSTEM = "file_system"
    SYSTEM_RESOURCES = "system_resources"
    NETWORK = "network"
    CUSTOM = "custom"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    name: str
    status: HealthStatus
    response_time_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metrics: Dict[str, Union[int, float, str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "status": self.status.value,
            "response_time_ms": round(self.response_time_ms, 2),
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "error": self.error,
            "metrics": self.metrics
        }


@dataclass
class HealthCheckConfig:
    """Configuration for health checks"""
    timeout_seconds: float = 10.0
    interval_seconds: float = 30.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    critical: bool = False  # If True, failure affects overall system health
    enabled: bool = True
    
    # Thresholds
    warning_response_time_ms: float = 1000.0
    critical_response_time_ms: float = 5000.0
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)


class BaseHealthCheck(ABC):
    """Base class for all health checks"""
    
    def __init__(self, name: str, config: Optional[HealthCheckConfig] = None):
        self.name = name
        self.config = config or HealthCheckConfig()
        self.last_result: Optional[HealthCheckResult] = None
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.total_checks = 0
        self.total_failures = 0
    
    @abstractmethod
    async def check_health(self) -> HealthCheckResult:
        """Perform the health check"""
        pass
    
    async def execute_check(self) -> HealthCheckResult:
        """Execute health check with retries and timing"""
        if not self.config.enabled:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                timestamp=datetime.utcnow(),
                details={"message": "Health check disabled"}
            )
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.config.retry_attempts):
            try:
                result = await asyncio.wait_for(
                    self.check_health(),
                    timeout=self.config.timeout_seconds
                )
                
                # Calculate response time
                response_time_ms = (time.time() - start_time) * 1000
                result.response_time_ms = response_time_ms
                
                # Update status based on response time thresholds
                if response_time_ms > self.config.critical_response_time_ms:
                    result.status = HealthStatus.UNHEALTHY
                    result.details["slow_response"] = True
                elif response_time_ms > self.config.warning_response_time_ms:
                    if result.status == HealthStatus.HEALTHY:
                        result.status = HealthStatus.DEGRADED
                    result.details["slow_response"] = True
                
                # Update metrics
                self.total_checks += 1
                self.last_result = result
                
                if result.status == HealthStatus.HEALTHY:
                    self.consecutive_failures = 0
                    self.consecutive_successes += 1
                else:
                    self.total_failures += 1
                    self.consecutive_successes = 0
                    if result.status == HealthStatus.UNHEALTHY:
                        self.consecutive_failures += 1
                
                return result
                
            except asyncio.TimeoutError:
                last_error = f"Health check timed out after {self.config.timeout_seconds}s"
                logger.warning(f"Health check '{self.name}' timed out (attempt {attempt + 1})")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Health check '{self.name}' failed (attempt {attempt + 1}): {e}")
            
            if attempt < self.config.retry_attempts - 1:
                await asyncio.sleep(self.config.retry_delay_seconds)
        
        # All attempts failed
        response_time_ms = (time.time() - start_time) * 1000
        self.total_checks += 1
        self.total_failures += 1
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        
        result = HealthCheckResult(
            name=self.name,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=response_time_ms,
            timestamp=datetime.utcnow(),
            error=last_error,
            details={"attempts": self.config.retry_attempts}
        )
        
        self.last_result = result
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get health check statistics"""
        success_rate = (
            ((self.total_checks - self.total_failures) / self.total_checks * 100)
            if self.total_checks > 0 else 0
        )
        
        return {
            "total_checks": self.total_checks,
            "total_failures": self.total_failures,
            "success_rate_percent": round(success_rate, 2),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_check": (
                self.last_result.timestamp.isoformat() 
                if self.last_result else None
            ),
            "average_response_time_ms": (
                self.last_result.response_time_ms 
                if self.last_result else 0
            )
        }


class DatabaseHealthCheck(BaseHealthCheck):
    """Health check for PostgreSQL database"""
    
    def __init__(self, name: str = "database", config: Optional[HealthCheckConfig] = None):
        super().__init__(name, config)
    
    async def check_health(self) -> HealthCheckResult:
        """Check database connectivity and performance"""
        from app.database import engine
        
        start_time = time.time()
        details = {}
        metrics = {}
        
        try:
            # Test connection
            with engine.connect() as conn:
                # Simple query to test connectivity
                result = conn.execute("SELECT 1 as test, NOW() as current_time")
                row = result.fetchone()
                
                query_time_ms = (time.time() - start_time) * 1000
                
                details.update({
                    "connection": "successful",
                    "test_query": "passed",
                    "current_time": str(row[1]) if row else None
                })
                
                metrics.update({
                    "query_time_ms": round(query_time_ms, 2),
                    "active_connections": self._get_connection_count(conn)
                })
                
                # Check connection pool status if available
                if hasattr(engine.pool, 'size'):
                    metrics.update({
                        "pool_size": engine.pool.size(),
                        "pool_checked_out": engine.pool.checkedout(),
                        "pool_overflow": getattr(engine.pool, 'overflow', 0)
                    })
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow(),
                error=str(e),
                details={"connection": "failed"}
            )
        
        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.HEALTHY,
            response_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.utcnow(),
            details=details,
            metrics=metrics
        )
    
    def _get_connection_count(self, conn) -> int:
        """Get active connection count"""
        try:
            result = conn.execute("""
                SELECT count(*) 
                FROM pg_stat_activity 
                WHERE state = 'active'
            """)
            return result.scalar() or 0
        except:
            return 0


class RedisHealthCheck(BaseHealthCheck):
    """Health check for Redis cache"""
    
    def __init__(self, name: str = "redis", config: Optional[HealthCheckConfig] = None):
        super().__init__(name, config)
        self.redis_url = None
    
    async def check_health(self) -> HealthCheckResult:
        """Check Redis connectivity and performance"""
        from app.config import settings
        
        start_time = time.time()
        details = {}
        metrics = {}
        
        try:
            # Create Redis connection
            redis = aioredis.from_url(settings.redis_url)
            
            # Test basic operations
            test_key = f"health_check_{int(time.time())}"
            test_value = "phantom_health_check"
            
            # SET operation
            await redis.set(test_key, test_value, ex=60)
            set_time = time.time()
            
            # GET operation
            retrieved_value = await redis.get(test_key)
            get_time = time.time()
            
            # DELETE operation
            await redis.delete(test_key)
            del_time = time.time()
            
            # Get Redis info
            info = await redis.info()
            
            await redis.close()
            
            if retrieved_value.decode() == test_value:
                details.update({
                    "connection": "successful",
                    "set_get_delete": "passed",
                    "redis_version": info.get("redis_version", "unknown")
                })
                
                metrics.update({
                    "set_time_ms": round((set_time - start_time) * 1000, 2),
                    "get_time_ms": round((get_time - set_time) * 1000, 2),
                    "del_time_ms": round((del_time - get_time) * 1000, 2),
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0)
                })
            else:
                raise Exception("SET/GET operation failed - values don't match")
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow(),
                error=str(e),
                details={"connection": "failed"}
            )
        
        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.HEALTHY,
            response_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.utcnow(),
            details=details,
            metrics=metrics
        )


class OpenAIHealthCheck(BaseHealthCheck):
    """Health check for OpenAI API"""
    
    def __init__(self, name: str = "openai_api", config: Optional[HealthCheckConfig] = None):
        super().__init__(name, config)
    
    async def check_health(self) -> HealthCheckResult:
        """Check OpenAI API connectivity and performance"""
        from app.config import settings
        
        start_time = time.time()
        details = {}
        metrics = {}
        
        if not settings.openai_api_key:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                response_time_ms=0,
                timestamp=datetime.utcnow(),
                details={"api_key": "not_configured"},
                error="OpenAI API key not configured"
            )
        
        try:
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            # Simple API call to test connectivity
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello, respond with OK"}],
                max_tokens=10,
                timeout=self.config.timeout_seconds
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.choices and response.choices[0].message.content:
                details.update({
                    "api_connection": "successful",
                    "model_response": "received",
                    "model_used": response.model
                })
                
                metrics.update({
                    "tokens_used": (
                        response.usage.total_tokens 
                        if response.usage else 0
                    )
                })
            else:
                raise Exception("No response received from OpenAI API")
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow(),
                error=str(e),
                details={"api_connection": "failed"}
            )
        
        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.HEALTHY,
            response_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.utcnow(),
            details=details,
            metrics=metrics
        )


class SystemResourcesHealthCheck(BaseHealthCheck):
    """Health check for system resources (CPU, Memory, Disk)"""
    
    def __init__(self, name: str = "system_resources", config: Optional[HealthCheckConfig] = None):
        super().__init__(name, config)
        # Thresholds
        self.cpu_warning_percent = 80.0
        self.cpu_critical_percent = 95.0
        self.memory_warning_percent = 85.0
        self.memory_critical_percent = 95.0
        self.disk_warning_percent = 85.0
        self.disk_critical_percent = 95.0
    
    async def check_health(self) -> HealthCheckResult:
        """Check system resources"""
        start_time = time.time()
        details = {}
        metrics = {}
        status = HealthStatus.HEALTHY
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            details["cpu_usage_percent"] = round(cpu_percent, 2)
            metrics["cpu_usage_percent"] = cpu_percent
            
            if cpu_percent >= self.cpu_critical_percent:
                status = HealthStatus.UNHEALTHY
                details["cpu_status"] = "critical"
            elif cpu_percent >= self.cpu_warning_percent:
                status = HealthStatus.DEGRADED
                details["cpu_status"] = "warning"
            else:
                details["cpu_status"] = "good"
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            details["memory_usage_percent"] = round(memory_percent, 2)
            details["memory_available_gb"] = round(memory.available / (1024**3), 2)
            metrics.update({
                "memory_usage_percent": memory_percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2)
            })
            
            if memory_percent >= self.memory_critical_percent:
                status = HealthStatus.UNHEALTHY
                details["memory_status"] = "critical"
            elif memory_percent >= self.memory_warning_percent:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                details["memory_status"] = "warning"
            else:
                details["memory_status"] = "good"
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            details["disk_usage_percent"] = round(disk_percent, 2)
            details["disk_free_gb"] = round(disk.free / (1024**3), 2)
            metrics.update({
                "disk_usage_percent": disk_percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2)
            })
            
            if disk_percent >= self.disk_critical_percent:
                status = HealthStatus.UNHEALTHY
                details["disk_status"] = "critical"
            elif disk_percent >= self.disk_warning_percent:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                details["disk_status"] = "warning"
            else:
                details["disk_status"] = "good"
            
            # Load average (Linux/Mac only)
            try:
                load_avg = psutil.getloadavg()
                details["load_average"] = {
                    "1min": round(load_avg[0], 2),
                    "5min": round(load_avg[1], 2),
                    "15min": round(load_avg[2], 2)
                }
                metrics["load_average_1min"] = load_avg[0]
            except:
                pass  # Not available on all systems
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow(),
                error=str(e),
                details={"system_check": "failed"}
            )
        
        return HealthCheckResult(
            name=self.name,
            status=status,
            response_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.utcnow(),
            details=details,
            metrics=metrics
        )


class NetworkConnectivityHealthCheck(BaseHealthCheck):
    """Health check for network connectivity"""
    
    def __init__(self, 
                 name: str = "network_connectivity", 
                 config: Optional[HealthCheckConfig] = None,
                 test_urls: Optional[List[str]] = None):
        super().__init__(name, config)
        self.test_urls = test_urls or [
            "https://www.google.com",
            "https://api.openai.com",
            "https://scanme.nmap.org"
        ]
    
    async def check_health(self) -> HealthCheckResult:
        """Check network connectivity to external services"""
        start_time = time.time()
        details = {}
        metrics = {}
        status = HealthStatus.HEALTHY
        
        connectivity_results = []
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                for url in self.test_urls:
                    url_start = time.time()
                    try:
                        response = await client.head(url)
                        url_time = (time.time() - url_start) * 1000
                        
                        connectivity_results.append({
                            "url": url,
                            "status": "success",
                            "status_code": response.status_code,
                            "response_time_ms": round(url_time, 2)
                        })
                        
                    except Exception as e:
                        url_time = (time.time() - url_start) * 1000
                        connectivity_results.append({
                            "url": url,
                            "status": "failed",
                            "error": str(e),
                            "response_time_ms": round(url_time, 2)
                        })
                        status = HealthStatus.DEGRADED
            
            details["connectivity_tests"] = connectivity_results
            
            successful_tests = len([r for r in connectivity_results if r["status"] == "success"])
            total_tests = len(connectivity_results)
            success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
            
            metrics.update({
                "successful_connections": successful_tests,
                "total_connection_tests": total_tests,
                "success_rate_percent": round(success_rate, 2),
                "average_response_time_ms": round(
                    sum(r["response_time_ms"] for r in connectivity_results) / total_tests,
                    2
                ) if total_tests > 0 else 0
            })
            
            if success_rate == 0:
                status = HealthStatus.UNHEALTHY
            elif success_rate < 70:
                status = HealthStatus.DEGRADED
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow(),
                error=str(e),
                details={"network_check": "failed"}
            )
        
        return HealthCheckResult(
            name=self.name,
            status=status,
            response_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.utcnow(),
            details=details,
            metrics=metrics
        )


class HealthCheckManager:
    """Manages and orchestrates all health checks"""
    
    def __init__(self):
        self.health_checks: Dict[str, BaseHealthCheck] = {}
        self.last_overall_result: Optional[Dict[str, Any]] = None
        self.check_history: List[Dict[str, Any]] = []
        self.max_history_size = 100
        self.lock = asyncio.Lock()
        
        # Register default health checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default health checks"""
        # Database check (critical)
        db_config = HealthCheckConfig(
            timeout_seconds=10.0,
            critical=True,
            warning_response_time_ms=500,
            critical_response_time_ms=2000
        )
        self.health_checks["database"] = DatabaseHealthCheck("database", db_config)
        
        # Redis check (non-critical, system can work without cache)
        redis_config = HealthCheckConfig(
            timeout_seconds=5.0,
            critical=False,
            warning_response_time_ms=200,
            critical_response_time_ms=1000
        )
        self.health_checks["redis"] = RedisHealthCheck("redis", redis_config)
        
        # OpenAI check (non-critical, fallback analysis available)
        openai_config = HealthCheckConfig(
            timeout_seconds=15.0,
            critical=False,
            warning_response_time_ms=2000,
            critical_response_time_ms=10000
        )
        self.health_checks["openai_api"] = OpenAIHealthCheck("openai_api", openai_config)
        
        # System resources check (critical)
        system_config = HealthCheckConfig(
            timeout_seconds=5.0,
            critical=True,
            warning_response_time_ms=1000,
            critical_response_time_ms=3000
        )
        self.health_checks["system_resources"] = SystemResourcesHealthCheck("system_resources", system_config)
        
        # Network connectivity check (non-critical)
        network_config = HealthCheckConfig(
            timeout_seconds=10.0,
            critical=False,
            warning_response_time_ms=3000,
            critical_response_time_ms=8000
        )
        self.health_checks["network"] = NetworkConnectivityHealthCheck("network", network_config)
    
    def register_health_check(self, health_check: BaseHealthCheck):
        """Register a custom health check"""
        self.health_checks[health_check.name] = health_check
        logger.info(f"Registered health check: {health_check.name}")
    
    async def check_all(self) -> Dict[str, Any]:
        """Execute all health checks and return overall status"""
        async with self.lock:
            start_time = time.time()
            results = {}
            overall_status = HealthStatus.HEALTHY
            
            # Execute all health checks concurrently
            tasks = []
            for name, check in self.health_checks.items():
                tasks.append(self._execute_single_check(name, check))
            
            check_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            critical_failures = 0
            total_failures = 0
            total_checks = len(self.health_checks)
            
            for i, result in enumerate(check_results):
                check_name = list(self.health_checks.keys())[i]
                check = self.health_checks[check_name]
                
                if isinstance(result, Exception):
                    # Health check raised an exception
                    result = HealthCheckResult(
                        name=check_name,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0,
                        timestamp=datetime.utcnow(),
                        error=str(result)
                    )
                
                results[check_name] = result.to_dict()
                
                # Update overall status
                if result.status == HealthStatus.UNHEALTHY:
                    total_failures += 1
                    if check.config.critical:
                        critical_failures += 1
                        overall_status = HealthStatus.UNHEALTHY
                elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
            
            # Calculate overall metrics
            total_time = time.time() - start_time
            success_rate = ((total_checks - total_failures) / total_checks * 100) if total_checks > 0 else 0
            
            overall_result = {
                "status": overall_status.value,
                "timestamp": datetime.utcnow().isoformat(),
                "total_checks": total_checks,
                "successful_checks": total_checks - total_failures,
                "failed_checks": total_failures,
                "critical_failures": critical_failures,
                "success_rate_percent": round(success_rate, 2),
                "total_response_time_ms": round(total_time * 1000, 2),
                "checks": results,
                "system_info": await self._get_system_info()
            }
            
            # Store result
            self.last_overall_result = overall_result
            self._add_to_history(overall_result)
            
            return overall_result
    
    async def _execute_single_check(self, name: str, check: BaseHealthCheck) -> HealthCheckResult:
        """Execute a single health check"""
        try:
            return await check.execute_check()
        except Exception as e:
            logger.error(f"Health check '{name}' failed with exception: {e}")
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def check_single(self, check_name: str) -> Optional[Dict[str, Any]]:
        """Execute a single health check by name"""
        if check_name not in self.health_checks:
            return None
        
        check = self.health_checks[check_name]
        result = await check.execute_check()
        return result.to_dict()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get health check statistics"""
        stats = {}
        
        for name, check in self.health_checks.items():
            stats[name] = check.get_statistics()
        
        # Overall statistics
        if self.check_history:
            recent_checks = self.check_history[-10:]  # Last 10 checks
            avg_success_rate = sum(c["success_rate_percent"] for c in recent_checks) / len(recent_checks)
            avg_response_time = sum(c["total_response_time_ms"] for c in recent_checks) / len(recent_checks)
            
            stats["overall"] = {
                "total_health_checks": len(recent_checks),
                "average_success_rate_percent": round(avg_success_rate, 2),
                "average_response_time_ms": round(avg_response_time, 2),
                "last_check_time": (
                    recent_checks[-1]["timestamp"] if recent_checks else None
                )
            }
        
        return stats
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Get basic system information"""
        try:
            return {
                "python_version": f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
                "platform": psutil.sys.platform,
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "cpu_count": psutil.cpu_count(),
                "total_memory_gb": round(psutil.virtual_memory().total / (1024**3), 2)
            }
        except:
            return {}
    
    def _add_to_history(self, result: Dict[str, Any]):
        """Add result to history with size limit"""
        self.check_history.append(result)
        
        # Keep only recent results
        if len(self.check_history) > self.max_history_size:
            self.check_history = self.check_history[-self.max_history_size:]
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent health check history"""
        return self.check_history[-limit:] if self.check_history else []


# Global health check manager
health_manager = HealthCheckManager()