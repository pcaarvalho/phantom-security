"""
Retry and fallback handler for scanner operations
"""

import asyncio
import logging
from typing import Dict, List, Any, Callable, Optional, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import random

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryStrategy(Enum):
    """Retry strategies for different operations"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"
    JITTERED_BACKOFF = "jittered_backoff"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    timeout: float = 300.0  # 5 minutes
    exceptions_to_retry: tuple = (ConnectionError, TimeoutError, Exception)
    exceptions_to_skip: tuple = (ValueError, TypeError)


class RetryHandler(Generic[T]):
    """Handle retries and fallbacks for scanner operations"""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.attempt_history: List[Dict] = []
        
    async def execute_with_retry(
        self,
        operation: Callable[..., Any],
        operation_name: str,
        fallback_operation: Optional[Callable[..., Any]] = None,
        *args,
        **kwargs
    ) -> T:
        """Execute operation with retry logic and optional fallback"""
        
        start_time = datetime.utcnow()
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                # Log attempt
                logger.info(f"[Retry] {operation_name} - Attempt {attempt}/{self.config.max_attempts}")
                
                # Calculate delay for current attempt
                if attempt > 1:
                    delay = self._calculate_delay(attempt - 1)
                    logger.info(f"[Retry] Waiting {delay:.2f}s before retry...")
                    await asyncio.sleep(delay)
                
                # Execute operation with timeout
                result = await asyncio.wait_for(
                    operation(*args, **kwargs),
                    timeout=self.config.timeout
                )
                
                # Record successful attempt
                self._record_attempt(operation_name, attempt, True, None)
                logger.info(f"[Retry] {operation_name} succeeded on attempt {attempt}")
                
                return result
                
            except self.config.exceptions_to_skip as e:
                logger.error(f"[Retry] {operation_name} failed with non-retryable error: {e}")
                self._record_attempt(operation_name, attempt, False, str(e))
                raise
                
            except self.config.exceptions_to_retry as e:
                last_exception = e
                self._record_attempt(operation_name, attempt, False, str(e))
                
                logger.warning(
                    f"[Retry] {operation_name} failed on attempt {attempt}: {str(e)[:100]}..."
                )
                
                # If this is the last attempt, try fallback
                if attempt == self.config.max_attempts and fallback_operation:
                    try:
                        logger.info(f"[Retry] Trying fallback for {operation_name}")
                        result = await fallback_operation(*args, **kwargs)
                        logger.info(f"[Retry] Fallback succeeded for {operation_name}")
                        self._record_attempt(f"{operation_name}_fallback", 1, True, None)
                        return result
                    except Exception as fallback_error:
                        logger.error(f"[Retry] Fallback failed for {operation_name}: {fallback_error}")
                        self._record_attempt(f"{operation_name}_fallback", 1, False, str(fallback_error))
                
                # Check if we should continue retrying
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > self.config.timeout:
                    logger.error(f"[Retry] {operation_name} timed out after {elapsed:.2f}s")
                    break
        
        # All attempts failed
        logger.error(f"[Retry] {operation_name} failed after {self.config.max_attempts} attempts")
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Operation {operation_name} failed after {self.config.max_attempts} attempts")
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on retry strategy"""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (2 ** attempt)
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        elif self.config.strategy == RetryStrategy.JITTERED_BACKOFF:
            base_delay = self.config.base_delay * (2 ** attempt)
            jitter = random.uniform(0, 0.1 * base_delay)
            delay = base_delay + jitter
        else:  # FIXED_DELAY
            delay = self.config.base_delay
        
        return min(delay, self.config.max_delay)
    
    def _record_attempt(self, operation: str, attempt: int, success: bool, error: Optional[str]):
        """Record attempt for metrics and debugging"""
        self.attempt_history.append({
            "operation": operation,
            "attempt": attempt,
            "success": success,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """Get retry statistics"""
        if not self.attempt_history:
            return {"total_attempts": 0, "success_rate": 0.0, "operations": {}}
        
        stats = {
            "total_attempts": len(self.attempt_history),
            "successful_attempts": sum(1 for a in self.attempt_history if a["success"]),
            "failed_attempts": sum(1 for a in self.attempt_history if not a["success"]),
            "operations": {}
        }
        
        # Group by operation
        for attempt in self.attempt_history:
            op = attempt["operation"]
            if op not in stats["operations"]:
                stats["operations"][op] = {
                    "total_attempts": 0,
                    "successful_attempts": 0,
                    "failed_attempts": 0,
                    "max_attempts_used": 0
                }
            
            stats["operations"][op]["total_attempts"] += 1
            stats["operations"][op]["max_attempts_used"] = max(
                stats["operations"][op]["max_attempts_used"],
                attempt["attempt"]
            )
            
            if attempt["success"]:
                stats["operations"][op]["successful_attempts"] += 1
            else:
                stats["operations"][op]["failed_attempts"] += 1
        
        # Calculate success rate
        stats["success_rate"] = (
            stats["successful_attempts"] / stats["total_attempts"] 
            if stats["total_attempts"] > 0 else 0.0
        )
        
        return stats


# Pre-configured retry handlers for different operations
class ScannerRetryConfigs:
    """Pre-configured retry configurations for different scanner operations"""
    
    NETWORK_SCAN = RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        timeout=300.0,  # 5 minutes
        exceptions_to_retry=(ConnectionError, TimeoutError, OSError)
    )
    
    WEB_SCAN = RetryConfig(
        max_attempts=2,
        base_delay=1.0,
        max_delay=15.0,
        strategy=RetryStrategy.FIXED_DELAY,
        timeout=120.0,  # 2 minutes
        exceptions_to_retry=(ConnectionError, TimeoutError)
    )
    
    VULNERABILITY_SCAN = RetryConfig(
        max_attempts=3,
        base_delay=5.0,
        max_delay=60.0,
        strategy=RetryStrategy.JITTERED_BACKOFF,
        timeout=600.0,  # 10 minutes
        exceptions_to_retry=(ConnectionError, TimeoutError, RuntimeError)
    )
    
    AI_ANALYSIS = RetryConfig(
        max_attempts=2,
        base_delay=3.0,
        max_delay=10.0,
        strategy=RetryStrategy.FIXED_DELAY,
        timeout=60.0,  # 1 minute
        exceptions_to_retry=(ConnectionError, TimeoutError)
    )
    
    RECON = RetryConfig(
        max_attempts=2,
        base_delay=1.0,
        max_delay=10.0,
        strategy=RetryStrategy.LINEAR_BACKOFF,
        timeout=180.0,  # 3 minutes
        exceptions_to_retry=(ConnectionError, TimeoutError, OSError)
    )