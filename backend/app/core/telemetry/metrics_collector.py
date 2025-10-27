"""
Metrics collection and telemetry for PHANTOM Security AI
"""

import time
import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json
import statistics
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected"""
    COUNTER = "counter"           # Incrementing counter
    GAUGE = "gauge"              # Point-in-time value
    HISTOGRAM = "histogram"      # Distribution of values
    TIMER = "timer"              # Duration measurements
    RATE = "rate"                # Rate over time


@dataclass
class MetricValue:
    """Individual metric measurement"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = "count"


class MetricsBuffer:
    """Thread-safe buffer for metric storage"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self._lock = threading.RLock()
    
    def add(self, metric: MetricValue):
        """Add metric to buffer"""
        with self._lock:
            self.buffer.append(metric)
    
    def get_metrics(self, since: datetime = None) -> List[MetricValue]:
        """Get metrics from buffer"""
        with self._lock:
            if since:
                return [m for m in self.buffer if m.timestamp >= since]
            return list(self.buffer)
    
    def clear(self):
        """Clear buffer"""
        with self._lock:
            self.buffer.clear()
    
    def size(self) -> int:
        """Get buffer size"""
        with self._lock:
            return len(self.buffer)


class MetricsCollector:
    """Centralized metrics collection system"""
    
    def __init__(self):
        self.buffer = MetricsBuffer()
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Performance tracking
        self.scan_timers: Dict[str, float] = {}
        self.phase_timers: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # System metrics
        self.system_metrics = {
            "active_scans": 0,
            "total_scans_started": 0,
            "total_scans_completed": 0,
            "total_scans_failed": 0,
            "total_vulnerabilities_found": 0,
            "avg_scan_duration": 0.0,
            "cache_hit_rate": 0.0,
            "ai_api_calls": 0,
            "ai_api_errors": 0
        }
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    def increment_counter(
        self, 
        name: str, 
        value: float = 1.0, 
        labels: Dict[str, str] = None
    ):
        """Increment a counter metric"""
        with self._lock:
            key = self._build_metric_key(name, labels)
            self.counters[key] += value
            
            metric = MetricValue(
                name=name,
                value=self.counters[key],
                metric_type=MetricType.COUNTER,
                timestamp=datetime.utcnow(),
                labels=labels or {}
            )
            self.buffer.add(metric)
    
    def set_gauge(
        self, 
        name: str, 
        value: float, 
        labels: Dict[str, str] = None,
        unit: str = "count"
    ):
        """Set a gauge metric"""
        with self._lock:
            key = self._build_metric_key(name, labels)
            self.gauges[key] = value
            
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                timestamp=datetime.utcnow(),
                labels=labels or {},
                unit=unit
            )
            self.buffer.add(metric)
    
    def record_histogram(
        self, 
        name: str, 
        value: float, 
        labels: Dict[str, str] = None
    ):
        """Record a value in a histogram"""
        with self._lock:
            key = self._build_metric_key(name, labels)
            self.histograms[key].append(value)
            
            # Keep only recent values to prevent memory bloat
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-500:]
            
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.HISTOGRAM,
                timestamp=datetime.utcnow(),
                labels=labels or {}
            )
            self.buffer.add(metric)
    
    def start_timer(self, name: str, labels: Dict[str, str] = None) -> str:
        """Start a timer and return timer ID"""
        timer_id = f"{name}:{id(threading.current_thread())}:{time.time()}"
        self.scan_timers[timer_id] = time.time()
        return timer_id
    
    def stop_timer(self, timer_id: str, name: str = None, labels: Dict[str, str] = None) -> float:
        """Stop a timer and record the duration"""
        if timer_id not in self.scan_timers:
            return 0.0
        
        start_time = self.scan_timers.pop(timer_id)
        duration = time.time() - start_time
        
        # Extract name from timer_id if not provided
        if not name:
            name = timer_id.split(":")[0]
        
        with self._lock:
            key = self._build_metric_key(name, labels)
            self.timers[key].append(duration)
            
            # Keep only recent values
            if len(self.timers[key]) > 1000:
                self.timers[key] = self.timers[key][-500:]
        
        metric = MetricValue(
            name=name,
            value=duration,
            metric_type=MetricType.TIMER,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            unit="seconds"
        )
        self.buffer.add(metric)
        
        return duration
    
    def record_rate(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Record a rate metric"""
        with self._lock:
            key = self._build_metric_key(name, labels)
            now = time.time()
            self.rates[key].append((now, value))
            
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.RATE,
                timestamp=datetime.utcnow(),
                labels=labels or {},
                unit="per_second"
            )
            self.buffer.add(metric)
    
    def _build_metric_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Build a unique key for metric storage"""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"
    
    # High-level tracking methods for PHANTOM
    
    def track_scan_started(self, scan_id: str, target: str, scan_type: str = "comprehensive"):
        """Track scan start"""
        self.increment_counter("scans_started_total")
        self.increment_counter("scans_started_by_type", labels={"type": scan_type})
        self.set_gauge("active_scans", self.system_metrics["active_scans"] + 1)
        self.system_metrics["active_scans"] += 1
        self.system_metrics["total_scans_started"] += 1
        
        # Start scan timer
        timer_id = self.start_timer("scan_duration", labels={"scan_id": scan_id})
        return timer_id
    
    def track_scan_completed(
        self, 
        scan_id: str, 
        timer_id: str, 
        vulnerabilities_found: int = 0,
        risk_score: float = 0.0
    ):
        """Track scan completion"""
        duration = self.stop_timer(timer_id, "scan_duration")
        
        self.increment_counter("scans_completed_total")
        self.set_gauge("active_scans", self.system_metrics["active_scans"] - 1)
        self.record_histogram("scan_duration_distribution", duration)
        self.increment_counter("vulnerabilities_found_total", vulnerabilities_found)
        self.record_histogram("risk_score_distribution", risk_score)
        
        self.system_metrics["active_scans"] -= 1
        self.system_metrics["total_scans_completed"] += 1
        self.system_metrics["total_vulnerabilities_found"] += vulnerabilities_found
        
        # Update average scan duration
        if self.system_metrics["total_scans_completed"] > 0:
            self.system_metrics["avg_scan_duration"] = (
                self.system_metrics["avg_scan_duration"] * 
                (self.system_metrics["total_scans_completed"] - 1) + duration
            ) / self.system_metrics["total_scans_completed"]
    
    def track_scan_failed(self, scan_id: str, timer_id: str, error: str):
        """Track scan failure"""
        self.stop_timer(timer_id, "scan_duration")
        
        self.increment_counter("scans_failed_total")
        self.increment_counter("scan_errors", labels={"error_type": self._classify_error(error)})
        self.set_gauge("active_scans", self.system_metrics["active_scans"] - 1)
        
        self.system_metrics["active_scans"] -= 1
        self.system_metrics["total_scans_failed"] += 1
    
    def track_phase_duration(self, phase_name: str, duration: float, scan_id: str = None):
        """Track duration of scan phases"""
        labels = {"phase": phase_name}
        if scan_id:
            labels["scan_id"] = scan_id
        
        self.record_histogram("phase_duration", duration, labels)
        self.record_histogram(f"phase_duration_{phase_name}", duration)
    
    def track_ai_api_call(self, model: str, tokens_used: int = None, cost: float = None):
        """Track AI API usage"""
        self.increment_counter("ai_api_calls_total")
        self.increment_counter("ai_api_calls_by_model", labels={"model": model})
        
        if tokens_used:
            self.record_histogram("ai_tokens_used", tokens_used, labels={"model": model})
        
        if cost:
            self.record_histogram("ai_api_cost", cost, labels={"model": model})
        
        self.system_metrics["ai_api_calls"] += 1
    
    def track_ai_api_error(self, model: str, error: str):
        """Track AI API errors"""
        self.increment_counter("ai_api_errors_total")
        self.increment_counter("ai_api_errors_by_model", labels={"model": model})
        self.increment_counter("ai_api_errors_by_type", labels={"error_type": self._classify_error(error)})
        
        self.system_metrics["ai_api_errors"] += 1
    
    def track_cache_hit(self, cache_level: str):
        """Track cache hits"""
        self.increment_counter("cache_hits_total")
        self.increment_counter("cache_hits_by_level", labels={"level": cache_level})
    
    def track_cache_miss(self, cache_level: str):
        """Track cache misses"""
        self.increment_counter("cache_misses_total")
        self.increment_counter("cache_misses_by_level", labels={"level": cache_level})
    
    def _classify_error(self, error: str) -> str:
        """Classify error types for metrics"""
        error_lower = error.lower()
        
        if any(keyword in error_lower for keyword in ["timeout", "timed out"]):
            return "timeout"
        elif any(keyword in error_lower for keyword in ["connection", "network", "dns"]):
            return "network"
        elif any(keyword in error_lower for keyword in ["permission", "forbidden", "unauthorized"]):
            return "permission"
        elif any(keyword in error_lower for keyword in ["rate limit", "quota", "throttle"]):
            return "rate_limit"
        elif any(keyword in error_lower for keyword in ["memory", "resource"]):
            return "resource"
        else:
            return "other"
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        with self._lock:
            # Calculate histogram statistics
            histogram_stats = {}
            for name, values in self.histograms.items():
                if values:
                    histogram_stats[name] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
            
            # Calculate timer statistics
            timer_stats = {}
            for name, values in self.timers.items():
                if values:
                    timer_stats[name] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
            
            # Calculate rates
            rate_stats = {}
            for name, rate_data in self.rates.items():
                if rate_data and len(rate_data) > 1:
                    recent_window = 60  # 60 seconds
                    now = time.time()
                    recent_rates = [(ts, val) for ts, val in rate_data if now - ts <= recent_window]
                    
                    if recent_rates:
                        total_value = sum(val for _, val in recent_rates)
                        time_span = max(ts for ts, _ in recent_rates) - min(ts for ts, _ in recent_rates)
                        rate_per_second = total_value / max(time_span, 1) if time_span > 0 else total_value
                        rate_stats[name] = rate_per_second
            
            # Calculate cache hit rate
            cache_hits = self.counters.get("cache_hits_total", 0)
            cache_misses = self.counters.get("cache_misses_total", 0)
            cache_total = cache_hits + cache_misses
            cache_hit_rate = (cache_hits / cache_total * 100) if cache_total > 0 else 0
            
            return {
                "system_metrics": self.system_metrics,
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histogram_stats": histogram_stats,
                "timer_stats": timer_stats,
                "rate_stats": rate_stats,
                "cache_hit_rate": round(cache_hit_rate, 2),
                "buffer_size": self.buffer.size(),
                "collection_time": datetime.utcnow().isoformat()
            }
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def export_metrics(self, format_type: str = "json") -> str:
        """Export metrics in specified format"""
        summary = self.get_metrics_summary()
        
        if format_type == "json":
            return json.dumps(summary, indent=2, default=str)
        elif format_type == "prometheus":
            return self._export_prometheus_format(summary)
        else:
            return str(summary)
    
    def _export_prometheus_format(self, summary: Dict[str, Any]) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        # Counters
        for name, value in summary["counters"].items():
            lines.append(f"phantom_{name.replace('-', '_')} {value}")
        
        # Gauges
        for name, value in summary["gauges"].items():
            lines.append(f"phantom_{name.replace('-', '_')} {value}")
        
        # Histogram summaries
        for name, stats in summary["histogram_stats"].items():
            base_name = f"phantom_{name.replace('-', '_')}"
            lines.append(f"{base_name}_count {stats['count']}")
            lines.append(f"{base_name}_min {stats['min']}")
            lines.append(f"{base_name}_max {stats['max']}")
            lines.append(f"{base_name}_mean {stats['mean']}")
            lines.append(f"{base_name}_p95 {stats['p95']}")
            lines.append(f"{base_name}_p99 {stats['p99']}")
        
        return "\n".join(lines)
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        with self._lock:
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()
            self.timers.clear()
            self.rates.clear()
            self.scan_timers.clear()
            self.phase_timers.clear()
            self.buffer.clear()
            
            self.system_metrics = {
                "active_scans": 0,
                "total_scans_started": 0,
                "total_scans_completed": 0,
                "total_scans_failed": 0,
                "total_vulnerabilities_found": 0,
                "avg_scan_duration": 0.0,
                "cache_hit_rate": 0.0,
                "ai_api_calls": 0,
                "ai_api_errors": 0
            }


# Context manager for timing operations
class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, collector: MetricsCollector, name: str, labels: Dict[str, str] = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.timer_id = None
    
    def __enter__(self):
        self.timer_id = self.collector.start_timer(self.name, self.labels)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.timer_id:
            self.collector.stop_timer(self.timer_id, self.name, self.labels)


# Global metrics collector instance
metrics_collector = MetricsCollector()