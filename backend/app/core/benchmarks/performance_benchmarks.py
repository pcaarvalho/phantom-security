"""
Performance Benchmarks and Metrics Collection for PHANTOM Security AI

This module provides comprehensive performance benchmarking capabilities
to measure the impact of resilience and reliability improvements.
"""

import asyncio
import time
import statistics
import json
import psutil
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from contextlib import asynccontextmanager
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging

from ..logging.structured_logger import get_logger, EventType
from ..resilience.circuit_breaker import circuit_breaker_manager
from ..resilience.rate_limiter import rate_limiter_manager
from ..error_handling.error_handler import global_error_handler


logger = get_logger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution"""
    name: str
    description: str
    iterations: int = 100
    concurrency: int = 10
    warmup_iterations: int = 10
    timeout_seconds: float = 60.0
    collect_system_metrics: bool = True
    measure_memory: bool = True
    measure_cpu: bool = True


@dataclass
class SystemMetrics:
    """System resource metrics during benchmark"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "memory_used_mb": round(self.memory_used_mb, 2),
            "memory_available_mb": round(self.memory_available_mb, 2),
            "disk_io_read_mb": round(self.disk_io_read_mb, 2),
            "disk_io_write_mb": round(self.disk_io_write_mb, 2),
            "network_sent_mb": round(self.network_sent_mb, 2),
            "network_recv_mb": round(self.network_recv_mb, 2)
        }


@dataclass
class BenchmarkResult:
    """Results of a performance benchmark"""
    name: str
    config: BenchmarkConfig
    start_time: datetime
    end_time: datetime
    
    # Execution metrics
    total_iterations: int
    successful_iterations: int
    failed_iterations: int
    
    # Timing metrics (in milliseconds)
    response_times: List[float] = field(default_factory=list)
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    mean_response_time: float = 0.0
    median_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # Throughput metrics
    requests_per_second: float = 0.0
    total_throughput: float = 0.0
    
    # System metrics
    system_metrics_start: Optional[SystemMetrics] = None
    system_metrics_end: Optional[SystemMetrics] = None
    peak_system_metrics: Optional[SystemMetrics] = None
    
    # Error information
    error_types: Dict[str, int] = field(default_factory=dict)
    error_details: List[str] = field(default_factory=list)
    
    # Resilience metrics
    circuit_breaker_metrics: Dict[str, Any] = field(default_factory=dict)
    rate_limiter_metrics: Dict[str, Any] = field(default_factory=dict)
    error_handler_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_statistics(self):
        """Calculate statistical metrics from response times"""
        if not self.response_times:
            return
        
        self.min_response_time = min(self.response_times)
        self.max_response_time = max(self.response_times)
        self.mean_response_time = statistics.mean(self.response_times)
        self.median_response_time = statistics.median(self.response_times)
        
        if len(self.response_times) > 1:
            sorted_times = sorted(self.response_times)
            n = len(sorted_times)
            
            # Calculate percentiles
            p95_index = int(0.95 * n)
            p99_index = int(0.99 * n)
            
            self.p95_response_time = sorted_times[min(p95_index, n - 1)]
            self.p99_response_time = sorted_times[min(p99_index, n - 1)]
        
        # Calculate throughput
        duration_seconds = (self.end_time - self.start_time).total_seconds()
        if duration_seconds > 0:
            self.requests_per_second = self.successful_iterations / duration_seconds
            self.total_throughput = self.total_iterations / duration_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert benchmark result to dictionary"""
        return {
            "name": self.name,
            "config": {
                "iterations": self.config.iterations,
                "concurrency": self.config.concurrency,
                "timeout_seconds": self.config.timeout_seconds
            },
            "execution": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration_seconds": (self.end_time - self.start_time).total_seconds(),
                "total_iterations": self.total_iterations,
                "successful_iterations": self.successful_iterations,
                "failed_iterations": self.failed_iterations,
                "success_rate_percent": (
                    (self.successful_iterations / self.total_iterations * 100)
                    if self.total_iterations > 0 else 0
                )
            },
            "performance": {
                "min_response_time_ms": round(self.min_response_time, 2),
                "max_response_time_ms": round(self.max_response_time, 2),
                "mean_response_time_ms": round(self.mean_response_time, 2),
                "median_response_time_ms": round(self.median_response_time, 2),
                "p95_response_time_ms": round(self.p95_response_time, 2),
                "p99_response_time_ms": round(self.p99_response_time, 2),
                "requests_per_second": round(self.requests_per_second, 2),
                "total_throughput": round(self.total_throughput, 2)
            },
            "system_metrics": {
                "start": self.system_metrics_start.to_dict() if self.system_metrics_start else None,
                "end": self.system_metrics_end.to_dict() if self.system_metrics_end else None,
                "peak": self.peak_system_metrics.to_dict() if self.peak_system_metrics else None
            },
            "errors": {
                "error_types": self.error_types,
                "error_rate_percent": (
                    (self.failed_iterations / self.total_iterations * 100)
                    if self.total_iterations > 0 else 0
                )
            },
            "resilience": {
                "circuit_breakers": self.circuit_breaker_metrics,
                "rate_limiters": self.rate_limiter_metrics,
                "error_handlers": self.error_handler_metrics
            }
        }


class SystemMonitor:
    """System resource monitor for benchmarks"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics_history: List[SystemMetrics] = []
        self.monitor_thread: Optional[threading.Thread] = None
        self.initial_disk_io = None
        self.initial_network_io = None
    
    def start_monitoring(self, interval: float = 0.5):
        """Start system monitoring"""
        self.monitoring = True
        self.metrics_history.clear()
        
        # Get initial I/O counters
        try:
            self.initial_disk_io = psutil.disk_io_counters()
            self.initial_network_io = psutil.net_io_counters()
        except:
            pass
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> List[SystemMetrics]:
        """Stop monitoring and return collected metrics"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        
        return self.metrics_history.copy()
    
    def _monitor_loop(self, interval: float):
        """Monitoring loop"""
        while self.monitoring:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
            except Exception as e:
                logger.warning(f"Error collecting system metrics: {e}")
            
            time.sleep(interval)
    
    def _collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        
        # Disk I/O
        disk_io_read_mb = 0.0
        disk_io_write_mb = 0.0
        try:
            current_disk_io = psutil.disk_io_counters()
            if self.initial_disk_io and current_disk_io:
                disk_io_read_mb = (current_disk_io.read_bytes - self.initial_disk_io.read_bytes) / (1024 * 1024)
                disk_io_write_mb = (current_disk_io.write_bytes - self.initial_disk_io.write_bytes) / (1024 * 1024)
        except:
            pass
        
        # Network I/O
        network_sent_mb = 0.0
        network_recv_mb = 0.0
        try:
            current_network_io = psutil.net_io_counters()
            if self.initial_network_io and current_network_io:
                network_sent_mb = (current_network_io.bytes_sent - self.initial_network_io.bytes_sent) / (1024 * 1024)
                network_recv_mb = (current_network_io.bytes_recv - self.initial_network_io.bytes_recv) / (1024 * 1024)
        except:
            pass
        
        return SystemMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            memory_available_mb=memory.available / (1024 * 1024),
            disk_io_read_mb=disk_io_read_mb,
            disk_io_write_mb=disk_io_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb
        )


class PerformanceBenchmark:
    """
    Performance benchmark executor with comprehensive metrics collection
    
    Features:
    - Concurrent execution with configurable concurrency levels
    - System resource monitoring during execution
    - Statistical analysis of response times
    - Integration with resilience components
    - Before/after comparison capabilities
    """
    
    def __init__(self):
        self.system_monitor = SystemMonitor()
        self.results_history: List[BenchmarkResult] = []
    
    async def run_benchmark(
        self,
        benchmark_func: Callable,
        config: BenchmarkConfig,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """Run a performance benchmark"""
        logger.info(
            f"Starting benchmark: {config.name}",
            event_type=EventType.PERFORMANCE_METRIC,
            metadata={
                "benchmark": config.name,
                "iterations": config.iterations,
                "concurrency": config.concurrency
            }
        )
        
        # Initialize result
        result = BenchmarkResult(
            name=config.name,
            config=config,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),  # Will be updated
            total_iterations=0,
            successful_iterations=0,
            failed_iterations=0
        )
        
        try:
            # Start system monitoring
            if config.collect_system_metrics:
                self.system_monitor.start_monitoring()
                result.system_metrics_start = self.system_monitor._collect_metrics()
            
            # Capture initial resilience metrics
            result.circuit_breaker_metrics = circuit_breaker_manager.get_all_metrics()
            result.rate_limiter_metrics = rate_limiter_manager.get_all_metrics()
            result.error_handler_metrics = global_error_handler.get_all_metrics()
            
            # Warmup phase
            if config.warmup_iterations > 0:
                logger.info(f"Running {config.warmup_iterations} warmup iterations")
                await self._run_warmup(benchmark_func, config.warmup_iterations, *args, **kwargs)
            
            # Main benchmark execution
            result = await self._execute_benchmark(benchmark_func, config, result, *args, **kwargs)
            
            # Calculate statistics
            result.calculate_statistics()
            
            # Collect final metrics
            result.end_time = datetime.utcnow()
            
            if config.collect_system_metrics:
                system_history = self.system_monitor.stop_monitoring()
                result.system_metrics_end = self.system_monitor._collect_metrics()
                
                # Find peak system usage
                if system_history:
                    peak_cpu = max(system_history, key=lambda m: m.cpu_percent)
                    peak_memory = max(system_history, key=lambda m: m.memory_percent)
                    result.peak_system_metrics = SystemMetrics(
                        timestamp=datetime.utcnow(),
                        cpu_percent=peak_cpu.cpu_percent,
                        memory_percent=peak_memory.memory_percent,
                        memory_used_mb=peak_memory.memory_used_mb,
                        memory_available_mb=peak_memory.memory_available_mb
                    )
            
            # Store result
            self.results_history.append(result)
            
            logger.info(
                f"Benchmark completed: {config.name}",
                event_type=EventType.PERFORMANCE_METRIC,
                performance_metrics={
                    "mean_response_time_ms": result.mean_response_time,
                    "p95_response_time_ms": result.p95_response_time,
                    "requests_per_second": result.requests_per_second,
                    "success_rate_percent": (result.successful_iterations / result.total_iterations * 100) if result.total_iterations > 0 else 0
                },
                metadata={
                    "total_iterations": result.total_iterations,
                    "failed_iterations": result.failed_iterations
                }
            )
            
            return result
            
        except Exception as e:
            result.end_time = datetime.utcnow()
            result.error_details.append(str(e))
            
            logger.error(
                f"Benchmark failed: {config.name}",
                error=e,
                event_type=EventType.ERROR_OCCURRED,
                metadata={"benchmark": config.name}
            )
            
            if config.collect_system_metrics:
                self.system_monitor.stop_monitoring()
            
            raise
    
    async def _run_warmup(self, benchmark_func: Callable, iterations: int, *args, **kwargs):
        """Run warmup iterations"""
        tasks = []
        for _ in range(iterations):
            task = asyncio.create_task(self._execute_single(benchmark_func, *args, **kwargs))
            tasks.append(task)
        
        # Wait for all warmup tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_benchmark(
        self,
        benchmark_func: Callable,
        config: BenchmarkConfig,
        result: BenchmarkResult,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """Execute the main benchmark"""
        semaphore = asyncio.Semaphore(config.concurrency)
        tasks = []
        
        # Create tasks for all iterations
        for _ in range(config.iterations):
            task = asyncio.create_task(
                self._execute_single_with_semaphore(
                    semaphore, benchmark_func, *args, **kwargs
                )
            )
            tasks.append(task)
        
        # Execute all tasks with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(f"Benchmark {config.name} timed out after {config.timeout_seconds}s")
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            results = [r for r in tasks if r.done()]
        
        # Process results
        for task_result in results:
            result.total_iterations += 1
            
            if isinstance(task_result, Exception):
                result.failed_iterations += 1
                error_type = type(task_result).__name__
                result.error_types[error_type] = result.error_types.get(error_type, 0) + 1
                result.error_details.append(str(task_result))
            elif isinstance(task_result, (int, float)):
                result.successful_iterations += 1
                result.response_times.append(task_result)
            else:
                result.successful_iterations += 1
        
        return result
    
    async def _execute_single_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        benchmark_func: Callable,
        *args,
        **kwargs
    ) -> float:
        """Execute single benchmark iteration with concurrency control"""
        async with semaphore:
            return await self._execute_single(benchmark_func, *args, **kwargs)
    
    async def _execute_single(self, benchmark_func: Callable, *args, **kwargs) -> float:
        """Execute single benchmark iteration and return response time in ms"""
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(benchmark_func):
                await benchmark_func(*args, **kwargs)
            else:
                # Run sync function in thread pool
                await asyncio.get_event_loop().run_in_executor(
                    None, benchmark_func, *args, **kwargs
                )
            
            end_time = time.time()
            return (end_time - start_time) * 1000  # Convert to milliseconds
            
        except Exception as e:
            end_time = time.time()
            # Still return timing for failed requests
            response_time = (end_time - start_time) * 1000
            # Re-raise exception to be handled by caller
            raise e
    
    def compare_results(
        self,
        baseline_name: str,
        comparison_name: str
    ) -> Dict[str, Any]:
        """Compare two benchmark results"""
        baseline = None
        comparison = None
        
        for result in self.results_history:
            if result.name == baseline_name:
                baseline = result
            elif result.name == comparison_name:
                comparison = result
        
        if not baseline or not comparison:
            raise ValueError("Could not find both benchmark results for comparison")
        
        # Calculate improvements/regressions
        response_time_change = (
            (comparison.mean_response_time - baseline.mean_response_time) / baseline.mean_response_time * 100
            if baseline.mean_response_time > 0 else 0
        )
        
        throughput_change = (
            (comparison.requests_per_second - baseline.requests_per_second) / baseline.requests_per_second * 100
            if baseline.requests_per_second > 0 else 0
        )
        
        p95_change = (
            (comparison.p95_response_time - baseline.p95_response_time) / baseline.p95_response_time * 100
            if baseline.p95_response_time > 0 else 0
        )
        
        success_rate_baseline = (
            baseline.successful_iterations / baseline.total_iterations * 100
            if baseline.total_iterations > 0 else 0
        )
        
        success_rate_comparison = (
            comparison.successful_iterations / comparison.total_iterations * 100
            if comparison.total_iterations > 0 else 0
        )
        
        success_rate_change = success_rate_comparison - success_rate_baseline
        
        return {
            "baseline": {
                "name": baseline.name,
                "mean_response_time_ms": baseline.mean_response_time,
                "p95_response_time_ms": baseline.p95_response_time,
                "requests_per_second": baseline.requests_per_second,
                "success_rate_percent": success_rate_baseline
            },
            "comparison": {
                "name": comparison.name,
                "mean_response_time_ms": comparison.mean_response_time,
                "p95_response_time_ms": comparison.p95_response_time,
                "requests_per_second": comparison.requests_per_second,
                "success_rate_percent": success_rate_comparison
            },
            "improvements": {
                "response_time_change_percent": round(response_time_change, 2),
                "throughput_change_percent": round(throughput_change, 2),
                "p95_response_time_change_percent": round(p95_change, 2),
                "success_rate_change_percent": round(success_rate_change, 2)
            },
            "summary": {
                "response_time_improved": response_time_change < 0,
                "throughput_improved": throughput_change > 0,
                "p95_improved": p95_change < 0,
                "reliability_improved": success_rate_change > 0
            }
        }
    
    def export_results(self, filename: str):
        """Export benchmark results to JSON file"""
        results_data = {
            "export_time": datetime.utcnow().isoformat(),
            "total_benchmarks": len(self.results_history),
            "results": [result.to_dict() for result in self.results_history]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        logger.info(
            f"Benchmark results exported to {filename}",
            event_type=EventType.SYSTEM_EVENT,
            metadata={"filename": filename, "benchmark_count": len(self.results_history)}
        )
    
    def get_summary_report(self) -> Dict[str, Any]:
        """Get summary report of all benchmark results"""
        if not self.results_history:
            return {"message": "No benchmark results available"}
        
        # Calculate overall statistics
        all_response_times = []
        total_requests = 0
        total_successes = 0
        
        for result in self.results_history:
            all_response_times.extend(result.response_times)
            total_requests += result.total_iterations
            total_successes += result.successful_iterations
        
        overall_success_rate = (total_successes / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "summary": {
                "total_benchmarks": len(self.results_history),
                "total_requests": total_requests,
                "overall_success_rate_percent": round(overall_success_rate, 2),
                "overall_mean_response_time_ms": round(statistics.mean(all_response_times), 2) if all_response_times else 0,
                "overall_median_response_time_ms": round(statistics.median(all_response_times), 2) if all_response_times else 0
            },
            "benchmarks": [
                {
                    "name": result.name,
                    "mean_response_time_ms": round(result.mean_response_time, 2),
                    "requests_per_second": round(result.requests_per_second, 2),
                    "success_rate_percent": round((result.successful_iterations / result.total_iterations * 100), 2) if result.total_iterations > 0 else 0,
                    "timestamp": result.start_time.isoformat()
                }
                for result in self.results_history
            ]
        }


# Global benchmark instance
performance_benchmark = PerformanceBenchmark()


# Predefined benchmark functions for common PHANTOM operations
async def database_query_benchmark():
    """Benchmark database query performance"""
    from app.database import connection_manager
    
    with connection_manager.get_session() as session:
        result = session.execute("SELECT 1")
        result.fetchone()


async def cache_operation_benchmark():
    """Benchmark cache operations"""
    from app.core.cache.cache_manager import cache_manager
    from app.core.cache.cache_manager import CacheLevel
    
    if await cache_manager.initialize():
        # Test cache set/get cycle
        await cache_manager.set(
            CacheLevel.SCAN_RESULTS,
            "benchmark_target",
            {"test": "benchmark_data"}
        )
        
        await cache_manager.get(
            CacheLevel.SCAN_RESULTS,
            "benchmark_target"
        )


async def health_check_benchmark():
    """Benchmark health check performance"""
    from app.core.resilience.health_checks import health_manager
    
    await health_manager.check_all()


async def websocket_benchmark():
    """Benchmark WebSocket message handling"""
    from app.core.websocket.enhanced_manager import enhanced_ws_manager
    
    await enhanced_ws_manager.emit_with_queue(
        "benchmark_event",
        {"test": "benchmark_message"},
        priority=enhanced_ws_manager.MessagePriority.NORMAL
    )