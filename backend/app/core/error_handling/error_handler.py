"""
Standardized Error Handler with Retry Logic and Context Management
"""

import asyncio
import time
import random
from typing import Callable, Any, Optional, Dict, List, Union, Type
from functools import wraps
from dataclasses import dataclass
from enum import Enum
import traceback
import logging

from .exceptions import (
    PhantomBaseException, ErrorContext, ErrorCategory, ErrorSeverity,
    TimeoutException, NetworkException, ExternalServiceException,
    RateLimitException, CircuitBreakerException,
    is_retryable_error, get_retry_delay, wrap_external_exception
)
from ..logging.structured_logger import get_logger, EventType


logger = get_logger(__name__)


class RetryStrategy(Enum):
    """Retry strategies"""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF_JITTER = "exponential_backoff_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF_JITTER
    multiplier: float = 2.0
    jitter_factor: float = 0.1
    retryable_exceptions: Optional[List[Type[Exception]]] = None
    non_retryable_exceptions: Optional[List[Type[Exception]]] = None


@dataclass
class ErrorHandlingMetrics:
    """Metrics for error handling"""
    total_errors: int = 0
    retries_attempted: int = 0
    successful_retries: int = 0
    failed_retries: int = 0
    errors_by_category: Dict[str, int] = None
    errors_by_severity: Dict[str, int] = None
    average_retry_delay: float = 0.0
    
    def __post_init__(self):
        if self.errors_by_category is None:
            self.errors_by_category = {}
        if self.errors_by_severity is None:
            self.errors_by_severity = {}


class ErrorHandler:
    """
    Comprehensive error handler with retry logic, context management, and metrics
    
    Features:
    - Multiple retry strategies with configurable parameters
    - Intelligent exception classification and handling
    - Context preservation across retries
    - Comprehensive error logging and metrics
    - Circuit breaker integration
    - Rate limiting awareness
    """
    
    def __init__(self, name: str):
        self.name = name
        self.metrics = ErrorHandlingMetrics()
        self.logger = get_logger(f"error_handler.{name}")
    
    async def handle_with_retry(
        self,
        func: Callable,
        *args,
        retry_config: Optional[RetryConfig] = None,
        context: Optional[ErrorContext] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with comprehensive error handling and retry logic
        
        Args:
            func: Function to execute
            *args: Function arguments
            retry_config: Retry configuration
            context: Error context
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            PhantomBaseException: Wrapped and classified exceptions
        """
        config = retry_config or RetryConfig()
        context = context or ErrorContext()
        
        last_exception = None
        retry_delays = []
        
        for attempt in range(1, config.max_attempts + 1):
            start_time = time.time()
            
            try:
                # Log attempt
                if attempt > 1:
                    self.logger.info(
                        f"Retry attempt {attempt}/{config.max_attempts} for operation",
                        event_type=EventType.SYSTEM_EVENT,
                        metadata={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": config.max_attempts,
                            "previous_error": str(last_exception) if last_exception else None
                        }
                    )
                
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, func, *args, **kwargs
                    )
                
                # Success - log and return
                execution_time = time.time() - start_time
                
                if attempt > 1:
                    self.metrics.successful_retries += 1
                    self.logger.info(
                        f"Operation succeeded after {attempt} attempts",
                        event_type=EventType.SYSTEM_EVENT,
                        performance_metrics={"execution_time_ms": execution_time * 1000},
                        metadata={
                            "function": func.__name__,
                            "total_attempts": attempt,
                            "retry_delays": retry_delays
                        }
                    )
                
                return result
                
            except Exception as exc:
                execution_time = time.time() - start_time
                last_exception = exc
                
                # Classify and wrap exception
                phantom_exc = self._classify_exception(exc, context, func.__name__)
                
                # Update metrics
                self.metrics.total_errors += 1
                self._update_error_metrics(phantom_exc)
                
                # Check if retryable
                if not self._is_retryable(phantom_exc, config):
                    self.logger.error(
                        f"Non-retryable error in operation: {phantom_exc.message}",
                        error=phantom_exc,
                        event_type=EventType.ERROR_OCCURRED,
                        metadata={
                            "function": func.__name__,
                            "attempt": attempt,
                            "error_category": phantom_exc.category.value,
                            "error_severity": phantom_exc.severity.value
                        }
                    )
                    raise phantom_exc
                
                # Check if we should retry
                if attempt >= config.max_attempts:
                    self.metrics.failed_retries += 1
                    self.logger.error(
                        f"Operation failed after {config.max_attempts} attempts: {phantom_exc.message}",
                        error=phantom_exc,
                        event_type=EventType.ERROR_OCCURRED,
                        metadata={
                            "function": func.__name__,
                            "total_attempts": attempt,
                            "retry_delays": retry_delays,
                            "final_error_category": phantom_exc.category.value
                        }
                    )
                    raise phantom_exc
                
                # Calculate retry delay
                retry_delay = self._calculate_retry_delay(
                    phantom_exc, attempt, config
                )
                retry_delays.append(retry_delay)
                
                self.metrics.retries_attempted += 1
                
                # Log retry decision
                self.logger.warning(
                    f"Operation failed (attempt {attempt}), retrying in {retry_delay}s: {phantom_exc.message}",
                    event_type=EventType.ERROR_OCCURRED,
                    performance_metrics={"execution_time_ms": execution_time * 1000},
                    metadata={
                        "function": func.__name__,
                        "attempt": attempt,
                        "max_attempts": config.max_attempts,
                        "retry_delay_seconds": retry_delay,
                        "error_category": phantom_exc.category.value,
                        "error_code": phantom_exc.error_code
                    }
                )
                
                # Wait before retry
                if retry_delay > 0:
                    await asyncio.sleep(retry_delay)
        
        # This should never be reached, but just in case
        raise last_exception or Exception("Unknown error in retry logic")
    
    def _classify_exception(
        self, 
        exc: Exception, 
        context: ErrorContext, 
        operation: str
    ) -> PhantomBaseException:
        """Classify and wrap exceptions"""
        
        # If already a PHANTOM exception, update context and return
        if isinstance(exc, PhantomBaseException):
            if not exc.context.correlation_id and context.correlation_id:
                exc.context = context
            if not exc.context.operation:
                exc.context.operation = operation
            return exc
        
        # Classify by exception type and message
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__
        
        # Timeout errors
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in exc_str:
            return TimeoutException(operation, 30.0, context=context, cause=exc)
        
        # Network errors
        if isinstance(exc, ConnectionError) or any(
            keyword in exc_str for keyword in ["connection", "network", "unreachable", "refused"]
        ):
            return NetworkException(f"Network error in {operation}: {str(exc)}", context=context, cause=exc)
        
        # Authentication/Authorization
        if any(keyword in exc_str for keyword in ["auth", "unauthorized", "forbidden", "credentials"]):
            from .exceptions import AuthenticationException, AuthorizationException
            if "forbidden" in exc_str or "authorization" in exc_str:
                return AuthorizationException(f"Authorization failed in {operation}", context=context, cause=exc)
            else:
                return AuthenticationException(f"Authentication failed in {operation}", context=context, cause=exc)
        
        # Rate limiting
        if any(keyword in exc_str for keyword in ["rate limit", "too many requests", "quota exceeded"]):
            retry_after = self._extract_retry_after(exc_str)
            return RateLimitException(f"Rate limit exceeded in {operation}", retry_after=retry_after, context=context, cause=exc)
        
        # Permission errors
        if isinstance(exc, PermissionError) or "permission" in exc_str:
            from .exceptions import FilePermissionException
            return FilePermissionException("unknown", operation, context=context, cause=exc)
        
        # File not found
        if isinstance(exc, FileNotFoundError) or "not found" in exc_str:
            from .exceptions import FileNotFoundException
            return FileNotFoundException("unknown", context=context, cause=exc)
        
        # Generic external service error
        service_name = self._extract_service_name(operation, exc_str)
        return ExternalServiceException(
            service_name, 
            f"Error in {operation}: {str(exc)}", 
            context=context, 
            cause=exc
        )
    
    def _is_retryable(self, exc: PhantomBaseException, config: RetryConfig) -> bool:
        """Check if exception is retryable based on configuration"""
        
        # Check explicit non-retryable exceptions
        if config.non_retryable_exceptions:
            if any(isinstance(exc.cause, exc_type) for exc_type in config.non_retryable_exceptions):
                return False
        
        # Check explicit retryable exceptions
        if config.retryable_exceptions:
            if any(isinstance(exc.cause, exc_type) for exc_type in config.retryable_exceptions):
                return True
        
        # Use built-in retryable logic
        return is_retryable_error(exc)
    
    def _calculate_retry_delay(
        self, 
        exc: PhantomBaseException, 
        attempt: int, 
        config: RetryConfig
    ) -> float:
        """Calculate retry delay based on strategy and exception"""
        
        # Check if exception specifies retry delay
        if hasattr(exc, 'retry_after') and exc.retry_after:
            return min(exc.retry_after, config.max_delay_seconds)
        
        # Use strategy-based calculation
        if config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.base_delay_seconds
            
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay_seconds * attempt
            
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay_seconds * (config.multiplier ** (attempt - 1))
            
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF_JITTER:
            base_delay = config.base_delay_seconds * (config.multiplier ** (attempt - 1))
            jitter = base_delay * config.jitter_factor * (random.random() - 0.5)
            delay = base_delay + jitter
            
        else:
            delay = config.base_delay_seconds
        
        # Ensure delay is within bounds
        delay = max(0, min(config.max_delay_seconds, delay))
        
        # Update metrics
        if delay > 0:
            total_delays = len([d for d in [delay] if d > 0])
            if total_delays > 0:
                self.metrics.average_retry_delay = (
                    self.metrics.average_retry_delay + delay
                ) / (total_delays + 1)
        
        return delay
    
    def _update_error_metrics(self, exc: PhantomBaseException):
        """Update error metrics"""
        category_key = exc.category.value
        severity_key = exc.severity.value
        
        self.metrics.errors_by_category[category_key] = (
            self.metrics.errors_by_category.get(category_key, 0) + 1
        )
        
        self.metrics.errors_by_severity[severity_key] = (
            self.metrics.errors_by_severity.get(severity_key, 0) + 1
        )
    
    def _extract_retry_after(self, error_message: str) -> int:
        """Extract retry-after value from error message"""
        import re
        
        # Look for patterns like "retry after 60 seconds"
        patterns = [
            r"retry after (\d+)",
            r"wait (\d+) seconds",
            r"try again in (\d+)",
            r"rate limit.*?(\d+).*?seconds"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message.lower())
            if match:
                return int(match.group(1))
        
        return 60  # Default retry after 1 minute
    
    def _extract_service_name(self, operation: str, error_message: str) -> str:
        """Extract service name from operation or error message"""
        
        # Common service keywords
        services = {
            "openai": ["openai", "gpt", "ai", "chat"],
            "nmap": ["nmap", "port", "scan"],
            "nuclei": ["nuclei", "vulnerability"],
            "database": ["database", "db", "sql", "postgres"],
            "redis": ["redis", "cache"],
            "http": ["http", "api", "request"]
        }
        
        operation_lower = operation.lower()
        error_lower = error_message.lower()
        
        for service, keywords in services.items():
            if any(keyword in operation_lower or keyword in error_lower for keyword in keywords):
                return service
        
        return "unknown"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get error handling metrics"""
        return {
            "handler_name": self.name,
            "total_errors": self.metrics.total_errors,
            "retries_attempted": self.metrics.retries_attempted,
            "successful_retries": self.metrics.successful_retries,
            "failed_retries": self.metrics.failed_retries,
            "retry_success_rate": (
                (self.metrics.successful_retries / self.metrics.retries_attempted * 100)
                if self.metrics.retries_attempted > 0 else 0
            ),
            "average_retry_delay_seconds": self.metrics.average_retry_delay,
            "errors_by_category": self.metrics.errors_by_category,
            "errors_by_severity": self.metrics.errors_by_severity
        }
    
    def reset_metrics(self):
        """Reset error handling metrics"""
        self.metrics = ErrorHandlingMetrics()


class GlobalErrorHandler:
    """Global error handler manager"""
    
    def __init__(self):
        self.handlers: Dict[str, ErrorHandler] = {}
        self.default_config = RetryConfig()
    
    def get_handler(self, name: str) -> ErrorHandler:
        """Get or create error handler"""
        if name not in self.handlers:
            self.handlers[name] = ErrorHandler(name)
        return self.handlers[name]
    
    def set_default_config(self, config: RetryConfig):
        """Set default retry configuration"""
        self.default_config = config
    
    async def handle_with_retry(
        self,
        func: Callable,
        *args,
        handler_name: str = "default",
        retry_config: Optional[RetryConfig] = None,
        context: Optional[ErrorContext] = None,
        **kwargs
    ) -> Any:
        """Handle function execution with error handling and retries"""
        handler = self.get_handler(handler_name)
        config = retry_config or self.default_config
        return await handler.handle_with_retry(func, *args, retry_config=config, context=context, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics from all error handlers"""
        return {name: handler.get_metrics() for name, handler in self.handlers.items()}


# Global error handler instance
global_error_handler = GlobalErrorHandler()


def with_error_handling(
    retry_config: Optional[RetryConfig] = None,
    handler_name: str = "default",
    context: Optional[ErrorContext] = None
):
    """
    Decorator for automatic error handling and retries
    
    Usage:
        @with_error_handling(RetryConfig(max_attempts=5))
        async def risky_operation():
            # Implementation
            pass
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await global_error_handler.handle_with_retry(
                func, *args, 
                handler_name=handler_name,
                retry_config=retry_config,
                context=context,
                **kwargs
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(global_error_handler.handle_with_retry(
                func, *args,
                handler_name=handler_name,
                retry_config=retry_config,
                context=context,
                **kwargs
            ))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def create_retry_config(
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF_JITTER,
    base_delay: float = 1.0,
    max_delay: float = 300.0
) -> RetryConfig:
    """Create retry configuration with common settings"""
    return RetryConfig(
        max_attempts=max_attempts,
        base_delay_seconds=base_delay,
        max_delay_seconds=max_delay,
        strategy=strategy
    )