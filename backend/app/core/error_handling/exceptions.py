"""
Standardized Exception Classes for PHANTOM Security AI
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass
import traceback
from datetime import datetime


class ErrorCategory(Enum):
    """Categories of errors for classification and handling"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_SERVICE = "external_service"
    NETWORK = "network"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    RATE_LIMITING = "rate_limiting"
    CIRCUIT_BREAKER = "circuit_breaker"
    TIMEOUT = "timeout"
    SECURITY = "security"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for errors"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for errors"""
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    scan_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PhantomBaseException(Exception):
    """Base exception for all PHANTOM Security AI errors"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_code: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        retry_after: Optional[int] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.error_code = error_code or self._generate_error_code()
        self.context = context or ErrorContext()
        self.cause = cause
        self.retry_after = retry_after
        self.user_message = user_message or self._get_user_friendly_message()
        self.timestamp = datetime.utcnow()
        self.traceback_str = traceback.format_exc()
    
    def _generate_error_code(self) -> str:
        """Generate error code based on exception class"""
        class_name = self.__class__.__name__
        return f"{self.category.value.upper()}_{class_name.upper().replace('EXCEPTION', '')}"
    
    def _get_user_friendly_message(self) -> str:
        """Get user-friendly error message"""
        # Default user-friendly messages by category
        user_messages = {
            ErrorCategory.AUTHENTICATION: "Authentication failed. Please check your credentials.",
            ErrorCategory.AUTHORIZATION: "You don't have permission to perform this action.",
            ErrorCategory.VALIDATION: "The provided data is invalid. Please check your input.",
            ErrorCategory.EXTERNAL_SERVICE: "An external service is currently unavailable. Please try again later.",
            ErrorCategory.RATE_LIMITING: "Too many requests. Please wait before trying again.",
            ErrorCategory.TIMEOUT: "The operation timed out. Please try again.",
            ErrorCategory.SYSTEM: "A system error occurred. Please contact support if the issue persists."
        }
        return user_messages.get(self.category, "An unexpected error occurred. Please try again.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "context": {
                "correlation_id": self.context.correlation_id,
                "request_id": self.context.request_id,
                "operation": self.context.operation,
                "component": self.context.component
            },
            "retry_after": self.retry_after,
            "caused_by": str(self.cause) if self.cause else None
        }


# Authentication & Authorization Exceptions
class AuthenticationException(PhantomBaseException):
    """Authentication related errors"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class AuthorizationException(PhantomBaseException):
    """Authorization related errors"""
    
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class InvalidTokenException(AuthenticationException):
    """Invalid or expired token"""
    
    def __init__(self, message: str = "Token is invalid or expired", **kwargs):
        super().__init__(message, **kwargs)


# Validation Exceptions
class ValidationException(PhantomBaseException):
    """Data validation errors"""
    
    def __init__(self, message: str, field_errors: Optional[Dict[str, List[str]]] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.field_errors = field_errors or {}


class InvalidInputException(ValidationException):
    """Invalid input data"""
    
    def __init__(self, message: str = "Invalid input provided", **kwargs):
        super().__init__(message, **kwargs)


class MissingParameterException(ValidationException):
    """Required parameter missing"""
    
    def __init__(self, parameter: str, **kwargs):
        message = f"Required parameter '{parameter}' is missing"
        super().__init__(message, **kwargs)


# Business Logic Exceptions
class BusinessLogicException(PhantomBaseException):
    """Business logic violation errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class ScanNotFoundException(BusinessLogicException):
    """Scan not found"""
    
    def __init__(self, scan_id: str, **kwargs):
        message = f"Scan with ID '{scan_id}' not found"
        super().__init__(message, **kwargs)


class ScanAlreadyRunningException(BusinessLogicException):
    """Scan already running"""
    
    def __init__(self, scan_id: str, **kwargs):
        message = f"Scan '{scan_id}' is already running"
        super().__init__(message, **kwargs)


class InvalidScanConfigurationException(BusinessLogicException):
    """Invalid scan configuration"""
    
    def __init__(self, message: str = "Invalid scan configuration", **kwargs):
        super().__init__(message, **kwargs)


# External Service Exceptions
class ExternalServiceException(PhantomBaseException):
    """External service related errors"""
    
    def __init__(self, service_name: str, message: str, **kwargs):
        super().__init__(
            f"External service '{service_name}': {message}",
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.service_name = service_name


class OpenAIServiceException(ExternalServiceException):
    """OpenAI API related errors"""
    
    def __init__(self, message: str = "OpenAI API error", **kwargs):
        super().__init__("openai", message, **kwargs)


class NmapServiceException(ExternalServiceException):
    """Nmap service related errors"""
    
    def __init__(self, message: str = "Nmap execution error", **kwargs):
        super().__init__("nmap", message, **kwargs)


class NucleiServiceException(ExternalServiceException):
    """Nuclei service related errors"""
    
    def __init__(self, message: str = "Nuclei execution error", **kwargs):
        super().__init__("nuclei", message, **kwargs)


# Network & Connectivity Exceptions
class NetworkException(PhantomBaseException):
    """Network related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class ConnectionTimeoutException(NetworkException):
    """Connection timeout errors"""
    
    def __init__(self, target: str, timeout: float, **kwargs):
        message = f"Connection to '{target}' timed out after {timeout}s"
        super().__init__(message, **kwargs)


class DNSResolutionException(NetworkException):
    """DNS resolution errors"""
    
    def __init__(self, hostname: str, **kwargs):
        message = f"Failed to resolve hostname '{hostname}'"
        super().__init__(message, **kwargs)


# Database Exceptions
class DatabaseException(PhantomBaseException):
    """Database related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class DatabaseConnectionException(DatabaseException):
    """Database connection errors"""
    
    def __init__(self, message: str = "Database connection failed", **kwargs):
        super().__init__(message, **kwargs)


class DatabaseQueryException(DatabaseException):
    """Database query errors"""
    
    def __init__(self, query: str, error: str, **kwargs):
        message = f"Database query failed: {error}"
        super().__init__(message, **kwargs)
        self.query = query


# Rate Limiting Exceptions
class RateLimitException(PhantomBaseException):
    """Rate limiting related errors"""
    
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RATE_LIMITING,
            severity=ErrorSeverity.MEDIUM,
            retry_after=retry_after,
            **kwargs
        )


class APIRateLimitExceededException(RateLimitException):
    """API rate limit exceeded"""
    
    def __init__(self, service: str, limit: int, retry_after: int = 60, **kwargs):
        message = f"Rate limit exceeded for {service}: {limit} requests"
        super().__init__(message, retry_after=retry_after, **kwargs)


# Circuit Breaker Exceptions
class CircuitBreakerException(PhantomBaseException):
    """Circuit breaker related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CIRCUIT_BREAKER,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class CircuitOpenException(CircuitBreakerException):
    """Circuit breaker is open"""
    
    def __init__(self, service: str, retry_after: int = 60, **kwargs):
        message = f"Circuit breaker for '{service}' is open"
        super().__init__(message, retry_after=retry_after, **kwargs)


# Timeout Exceptions
class TimeoutException(PhantomBaseException):
    """Timeout related errors"""
    
    def __init__(self, operation: str, timeout: float, **kwargs):
        message = f"Operation '{operation}' timed out after {timeout}s"
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.timeout = timeout


class ScanTimeoutException(TimeoutException):
    """Scan operation timeout"""
    
    def __init__(self, scan_id: str, timeout: float, **kwargs):
        super().__init__(f"Scan {scan_id}", timeout, **kwargs)


# Security Exceptions
class SecurityException(PhantomBaseException):
    """Security related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SECURITY,
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class UnauthorizedTargetException(SecurityException):
    """Unauthorized scanning target"""
    
    def __init__(self, target: str, **kwargs):
        message = f"Unauthorized to scan target: {target}"
        super().__init__(message, **kwargs)


class SecurityPolicyViolationException(SecurityException):
    """Security policy violation"""
    
    def __init__(self, policy: str, **kwargs):
        message = f"Security policy violation: {policy}"
        super().__init__(message, **kwargs)


# System Exceptions
class SystemException(PhantomBaseException):
    """System level errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class ResourceExhaustedException(SystemException):
    """System resources exhausted"""
    
    def __init__(self, resource: str, **kwargs):
        message = f"System resource exhausted: {resource}"
        super().__init__(message, **kwargs)


class ConfigurationException(SystemException):
    """System configuration errors"""
    
    def __init__(self, message: str = "System configuration error", **kwargs):
        super().__init__(message, **kwargs)


# File System Exceptions
class FileSystemException(PhantomBaseException):
    """File system related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.FILE_SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class FileNotFoundException(FileSystemException):
    """File not found"""
    
    def __init__(self, file_path: str, **kwargs):
        message = f"File not found: {file_path}"
        super().__init__(message, **kwargs)


class FilePermissionException(FileSystemException):
    """File permission denied"""
    
    def __init__(self, file_path: str, operation: str, **kwargs):
        message = f"Permission denied for {operation} operation on: {file_path}"
        super().__init__(message, **kwargs)


class DiskSpaceException(FileSystemException):
    """Insufficient disk space"""
    
    def __init__(self, required_space: str, available_space: str, **kwargs):
        message = f"Insufficient disk space: required {required_space}, available {available_space}"
        super().__init__(message, **kwargs)


# Utility functions for exception handling
def create_error_context(
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    operation: Optional[str] = None,
    component: Optional[str] = None,
    **metadata
) -> ErrorContext:
    """Create error context with provided information"""
    return ErrorContext(
        correlation_id=correlation_id,
        request_id=request_id,
        user_id=user_id,
        scan_id=scan_id,
        operation=operation,
        component=component,
        metadata=metadata
    )


def wrap_external_exception(
    exc: Exception,
    service_name: str,
    operation: str,
    context: Optional[ErrorContext] = None
) -> PhantomBaseException:
    """Wrap external exceptions in PHANTOM exceptions"""
    
    # Map common exception types
    if isinstance(exc, TimeoutError):
        return TimeoutException(operation, 30.0, context=context, cause=exc)
    elif isinstance(exc, ConnectionError):
        return NetworkException(f"Connection error during {operation}", context=context, cause=exc)
    elif "authentication" in str(exc).lower() or "unauthorized" in str(exc).lower():
        return AuthenticationException(f"Authentication failed for {service_name}", context=context, cause=exc)
    elif "permission" in str(exc).lower() or "forbidden" in str(exc).lower():
        return AuthorizationException(f"Authorization failed for {service_name}", context=context, cause=exc)
    else:
        return ExternalServiceException(service_name, str(exc), context=context, cause=exc)


def is_retryable_error(exc: Exception) -> bool:
    """Check if an error is retryable"""
    retryable_categories = {
        ErrorCategory.NETWORK,
        ErrorCategory.EXTERNAL_SERVICE,
        ErrorCategory.TIMEOUT,
        ErrorCategory.RATE_LIMITING
    }
    
    if isinstance(exc, PhantomBaseException):
        return exc.category in retryable_categories
    
    # Common retryable exception types
    retryable_types = (
        ConnectionError,
        TimeoutError,
    )
    
    return isinstance(exc, retryable_types)


def get_retry_delay(exc: Exception, attempt: int = 1) -> Optional[int]:
    """Get recommended retry delay for an exception"""
    if isinstance(exc, PhantomBaseException) and exc.retry_after:
        return exc.retry_after
    
    if isinstance(exc, RateLimitException):
        return exc.retry_after or (60 * attempt)
    
    if isinstance(exc, CircuitBreakerException):
        return 30 * attempt
    
    if isinstance(exc, NetworkException):
        return min(300, 5 * (2 ** attempt))  # Exponential backoff, max 5 minutes
    
    return None