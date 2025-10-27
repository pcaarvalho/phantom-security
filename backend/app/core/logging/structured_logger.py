"""
Structured Logging System with Correlation IDs and Centralized Management
"""

import json
import uuid
import time
import logging
import asyncio
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from contextvars import ContextVar
from functools import wraps
import threading
import traceback
import inspect
from pathlib import Path

# Context variables for correlation tracking
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
scan_id: ContextVar[Optional[str]] = ContextVar('scan_id', default=None)
request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class LogLevel(Enum):
    """Enhanced log levels"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SECURITY = "SECURITY"  # Special level for security events
    AUDIT = "AUDIT"        # Special level for audit events


class EventType(Enum):
    """Types of events for categorization"""
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    DATABASE_QUERY = "database_query"
    CACHE_OPERATION = "cache_operation"
    EXTERNAL_SERVICE = "external_service"
    SECURITY_SCAN = "security_scan"
    VULNERABILITY_FOUND = "vulnerability_found"
    ERROR_OCCURRED = "error_occurred"
    PERFORMANCE_METRIC = "performance_metric"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    AUDIT_EVENT = "audit_event"


@dataclass
class LogContext:
    """Context information for structured logging"""
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    scan_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LogEvent:
    """Structured log event"""
    timestamp: datetime
    level: LogLevel
    message: str
    event_type: EventType
    context: LogContext
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Union[int, float]]] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "event_type": self.event_type.value,
            "context": self.context.to_dict(),
            "metadata": self.metadata,
            "tags": self.tags
        }
        
        if self.error_details:
            result["error"] = self.error_details
        
        if self.performance_metrics:
            result["performance"] = self.performance_metrics
        
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        # Extract context from context variables
        context = LogContext(
            correlation_id=correlation_id.get(),
            request_id=request_id.get(),
            user_id=user_id.get(),
            scan_id=scan_id.get()
        )
        
        # Create log event
        event = LogEvent(
            timestamp=datetime.fromtimestamp(record.created),
            level=LogLevel(record.levelname),
            message=record.getMessage(),
            event_type=getattr(record, 'event_type', EventType.SYSTEM_EVENT),
            context=context,
            metadata=getattr(record, 'metadata', {}),
            error_details=self._extract_error_details(record),
            performance_metrics=getattr(record, 'performance_metrics', None),
            tags=getattr(record, 'tags', [])
        )
        
        return event.to_json()
    
    def _extract_error_details(self, record: logging.LogRecord) -> Optional[Dict[str, Any]]:
        """Extract error details from log record"""
        if record.exc_info:
            return {
                "exception_type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "exception_message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
                "module": record.module,
                "function": record.funcName,
                "line_number": record.lineno
            }
        return None


class MetricsCollector:
    """Collects and aggregates logging metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "total_logs": 0,
            "logs_by_level": {},
            "logs_by_event_type": {},
            "errors_count": 0,
            "warnings_count": 0,
            "average_response_time": 0.0,
            "last_reset": datetime.utcnow()
        }
        self.lock = threading.Lock()
        self.response_times: List[float] = []
        
    def record_log(self, level: LogLevel, event_type: EventType, response_time: Optional[float] = None):
        """Record a log event for metrics"""
        with self.lock:
            self.metrics["total_logs"] += 1
            
            # Count by level
            level_key = level.value
            self.metrics["logs_by_level"][level_key] = self.metrics["logs_by_level"].get(level_key, 0) + 1
            
            # Count by event type
            event_key = event_type.value
            self.metrics["logs_by_event_type"][event_key] = self.metrics["logs_by_event_type"].get(event_key, 0) + 1
            
            # Special counters
            if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                self.metrics["errors_count"] += 1
            elif level == LogLevel.WARNING:
                self.metrics["warnings_count"] += 1
            
            # Response time tracking
            if response_time is not None:
                self.response_times.append(response_time)
                # Keep only recent response times (last 1000)
                self.response_times = self.response_times[-1000:]
                self.metrics["average_response_time"] = sum(self.response_times) / len(self.response_times)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self.lock:
            return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset metrics counters"""
        with self.lock:
            self.metrics = {
                "total_logs": 0,
                "logs_by_level": {},
                "logs_by_event_type": {},
                "errors_count": 0,
                "warnings_count": 0,
                "average_response_time": 0.0,
                "last_reset": datetime.utcnow()
            }
            self.response_times.clear()


class StructuredLogger:
    """Enhanced structured logger with correlation IDs and metrics"""
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        self.metrics_collector = MetricsCollector()
        
        # Setup structured formatter
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def _log(self, 
             level: LogLevel,
             message: str,
             event_type: EventType = EventType.SYSTEM_EVENT,
             metadata: Optional[Dict[str, Any]] = None,
             error: Optional[Exception] = None,
             performance_metrics: Optional[Dict[str, Union[int, float]]] = None,
             tags: Optional[List[str]] = None,
             **kwargs):
        """Internal logging method"""
        
        # Record metrics
        response_time = performance_metrics.get('response_time_ms') if performance_metrics else None
        self.metrics_collector.record_log(level, event_type, response_time)
        
        # Create log record
        extra = {
            'event_type': event_type,
            'metadata': metadata or {},
            'performance_metrics': performance_metrics,
            'tags': tags or []
        }
        extra.update(kwargs)
        
        # Log with appropriate level
        log_level = getattr(logging, level.value)
        
        if error:
            self.logger.log(log_level, message, exc_info=True, extra=extra)
        else:
            self.logger.log(log_level, message, extra=extra)
    
    def trace(self, message: str, **kwargs):
        """Log trace message"""
        self._log(LogLevel.TRACE, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message"""
        self._log(LogLevel.ERROR, message, error=error, **kwargs)
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message"""
        self._log(LogLevel.CRITICAL, message, error=error, **kwargs)
    
    def security(self, message: str, **kwargs):
        """Log security event"""
        self._log(LogLevel.SECURITY, message, event_type=EventType.SECURITY_SCAN, **kwargs)
    
    def audit(self, message: str, **kwargs):
        """Log audit event"""
        self._log(LogLevel.AUDIT, message, event_type=EventType.AUDIT_EVENT, **kwargs)
    
    def api_request(self, method: str, path: str, **kwargs):
        """Log API request"""
        message = f"{method} {path}"
        metadata = kwargs.pop('metadata', {})
        metadata.update({"method": method, "path": path})
        self._log(LogLevel.INFO, message, EventType.API_REQUEST, metadata=metadata, **kwargs)
    
    def api_response(self, method: str, path: str, status_code: int, response_time_ms: float, **kwargs):
        """Log API response"""
        message = f"{method} {path} -> {status_code}"
        metadata = kwargs.pop('metadata', {})
        metadata.update({
            "method": method, 
            "path": path, 
            "status_code": status_code
        })
        performance_metrics = {"response_time_ms": response_time_ms}
        
        # Determine log level based on status code
        if status_code >= 500:
            level = LogLevel.ERROR
        elif status_code >= 400:
            level = LogLevel.WARNING
        else:
            level = LogLevel.INFO
            
        self._log(level, message, EventType.API_RESPONSE, 
                 metadata=metadata, performance_metrics=performance_metrics, **kwargs)
    
    def database_query(self, query_type: str, table: str, duration_ms: float, **kwargs):
        """Log database query"""
        message = f"Database {query_type} on {table}"
        metadata = kwargs.pop('metadata', {})
        metadata.update({"query_type": query_type, "table": table})
        performance_metrics = {"query_time_ms": duration_ms}
        
        level = LogLevel.WARNING if duration_ms > 1000 else LogLevel.DEBUG
        self._log(level, message, EventType.DATABASE_QUERY,
                 metadata=metadata, performance_metrics=performance_metrics, **kwargs)
    
    def vulnerability_found(self, vulnerability: Dict[str, Any], **kwargs):
        """Log vulnerability discovery"""
        severity = vulnerability.get('severity', 'unknown')
        target = vulnerability.get('target', 'unknown')
        message = f"Vulnerability found: {severity} on {target}"
        
        metadata = kwargs.pop('metadata', {})
        metadata.update(vulnerability)
        
        level = LogLevel.CRITICAL if severity.lower() == 'critical' else LogLevel.WARNING
        tags = kwargs.pop('tags', [])
        tags.extend(['vulnerability', severity.lower()])
        
        self._log(level, message, EventType.VULNERABILITY_FOUND,
                 metadata=metadata, tags=tags, **kwargs)
    
    def external_service_call(self, service: str, operation: str, 
                            duration_ms: float, success: bool = True, **kwargs):
        """Log external service call"""
        status = "successful" if success else "failed"
        message = f"External service call to {service}.{operation} {status}"
        
        metadata = kwargs.pop('metadata', {})
        metadata.update({
            "service": service,
            "operation": operation,
            "success": success
        })
        
        performance_metrics = {"call_duration_ms": duration_ms}
        
        level = LogLevel.ERROR if not success else LogLevel.INFO
        self._log(level, message, EventType.EXTERNAL_SERVICE,
                 metadata=metadata, performance_metrics=performance_metrics, **kwargs)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get logging metrics"""
        return self.metrics_collector.get_metrics()


class LoggerManager:
    """Manages multiple structured loggers"""
    
    def __init__(self):
        self.loggers: Dict[str, StructuredLogger] = {}
        self.default_level = LogLevel.INFO
    
    def get_logger(self, name: str, level: Optional[LogLevel] = None) -> StructuredLogger:
        """Get or create a structured logger"""
        if name not in self.loggers:
            self.loggers[name] = StructuredLogger(name, level or self.default_level)
        return self.loggers[name]
    
    def set_default_level(self, level: LogLevel):
        """Set default logging level for new loggers"""
        self.default_level = level
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics from all loggers"""
        return {name: logger.get_metrics() for name, logger in self.loggers.items()}


# Global logger manager
logger_manager = LoggerManager()


def get_logger(name: str, level: Optional[LogLevel] = None) -> StructuredLogger:
    """Get a structured logger instance"""
    return logger_manager.get_logger(name, level)


def set_correlation_id(correlation_id_value: str):
    """Set correlation ID for current context"""
    correlation_id.set(correlation_id_value)


def set_scan_id(scan_id_value: str):
    """Set scan ID for current context"""
    scan_id.set(scan_id_value)


def set_user_id(user_id_value: str):
    """Set user ID for current context"""
    user_id.set(user_id_value)


def set_request_id(request_id_value: str):
    """Set request ID for current context"""
    request_id.set(request_id_value)


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())


def with_correlation_id(correlation_id_value: Optional[str] = None):
    """Decorator to set correlation ID for function execution"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cid = correlation_id_value or generate_correlation_id()
            correlation_id.set(cid)
            try:
                return await func(*args, **kwargs)
            finally:
                correlation_id.set(None)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cid = correlation_id_value or generate_correlation_id()
            correlation_id.set(cid)
            try:
                return func(*args, **kwargs)
            finally:
                correlation_id.set(None)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def with_scan_context(scan_id_value: str, user_id_value: Optional[str] = None):
    """Decorator to set scan context for function execution"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            scan_id.set(scan_id_value)
            if user_id_value:
                user_id.set(user_id_value)
            if not correlation_id.get():
                correlation_id.set(generate_correlation_id())
            
            try:
                return await func(*args, **kwargs)
            finally:
                scan_id.set(None)
                if user_id_value:
                    user_id.set(None)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            scan_id.set(scan_id_value)
            if user_id_value:
                user_id.set(user_id_value)
            if not correlation_id.get():
                correlation_id.set(generate_correlation_id())
            
            try:
                return func(*args, **kwargs)
            finally:
                scan_id.set(None)
                if user_id_value:
                    user_id.set(None)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def log_performance(operation_name: str, logger: Optional[StructuredLogger] = None):
    """Decorator to log function performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            log = logger or get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                log.info(
                    f"Operation '{operation_name}' completed",
                    event_type=EventType.PERFORMANCE_METRIC,
                    performance_metrics={"duration_ms": duration_ms},
                    metadata={"function": func.__name__, "module": func.__module__}
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                log.error(
                    f"Operation '{operation_name}' failed",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    performance_metrics={"duration_ms": duration_ms},
                    metadata={"function": func.__name__, "module": func.__module__}
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            log = logger or get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                log.info(
                    f"Operation '{operation_name}' completed",
                    event_type=EventType.PERFORMANCE_METRIC,
                    performance_metrics={"duration_ms": duration_ms},
                    metadata={"function": func.__name__, "module": func.__module__}
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                log.error(
                    f"Operation '{operation_name}' failed",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    performance_metrics={"duration_ms": duration_ms},
                    metadata={"function": func.__name__, "module": func.__module__}
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator