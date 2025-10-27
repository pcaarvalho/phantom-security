"""
Advanced Database Connection Manager with Pooling and Monitoring
"""

import asyncio
import time
import threading
from typing import Dict, Any, Optional, List, ContextManager, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from contextlib import contextmanager, asynccontextmanager
from enum import Enum
import logging

from sqlalchemy import create_engine, event, text, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy.engine.events import PoolEvents
from sqlalchemy import __version__ as sqlalchemy_version

from ..logging.structured_logger import get_logger, EventType
from ..error_handling.exceptions import DatabaseException, DatabaseConnectionException


logger = get_logger(__name__)


class PoolType(Enum):
    """Database connection pool types"""
    QUEUE_POOL = "queue"
    NULL_POOL = "null"
    STATIC_POOL = "static"
    ASYNC_QUEUE_POOL = "async_queue"


@dataclass
class ConnectionPoolConfig:
    """Configuration for database connection pool"""
    # Pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    pool_pre_ping: bool = True
    
    # Connection settings
    connect_timeout: int = 10
    command_timeout: int = 30
    
    # Pool type
    pool_type: PoolType = PoolType.QUEUE_POOL
    
    # Monitoring
    enable_monitoring: bool = True
    stats_interval: int = 60  # seconds
    
    # Health checks
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class ConnectionMetrics:
    """Connection pool metrics"""
    pool_size: int = 0
    checked_out: int = 0
    overflow: int = 0
    invalid: int = 0
    
    # Connection lifecycle
    total_connections_created: int = 0
    total_connections_closed: int = 0
    total_checkouts: int = 0
    total_checkins: int = 0
    total_failures: int = 0
    
    # Performance metrics
    average_checkout_time_ms: float = 0.0
    average_query_time_ms: float = 0.0
    slow_query_count: int = 0
    
    # Time-based metrics
    uptime_seconds: float = 0.0
    last_activity: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    
    # Error tracking
    connection_errors: int = 0
    timeout_errors: int = 0
    query_errors: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pool_status": {
                "pool_size": self.pool_size,
                "checked_out": self.checked_out,
                "overflow": self.overflow,
                "invalid": self.invalid,
                "utilization_percent": (
                    (self.checked_out / (self.pool_size + self.overflow) * 100)
                    if (self.pool_size + self.overflow) > 0 else 0
                )
            },
            "connection_lifecycle": {
                "total_created": self.total_connections_created,
                "total_closed": self.total_connections_closed,
                "total_checkouts": self.total_checkouts,
                "total_checkins": self.total_checkins,
                "total_failures": self.total_failures
            },
            "performance": {
                "average_checkout_time_ms": round(self.average_checkout_time_ms, 2),
                "average_query_time_ms": round(self.average_query_time_ms, 2),
                "slow_query_count": self.slow_query_count
            },
            "status": {
                "uptime_seconds": round(self.uptime_seconds, 2),
                "last_activity": (
                    self.last_activity.isoformat() if self.last_activity else None
                ),
                "last_health_check": (
                    self.last_health_check.isoformat() if self.last_health_check else None
                )
            },
            "errors": {
                "connection_errors": self.connection_errors,
                "timeout_errors": self.timeout_errors,
                "query_errors": self.query_errors
            }
        }


class DatabaseConnectionManager:
    """
    Advanced database connection manager with comprehensive pooling and monitoring
    
    Features:
    - Connection pooling with configurable strategies
    - Real-time connection metrics and monitoring  
    - Health checks and automatic recovery
    - Query performance tracking
    - Connection lifecycle management
    - Circuit breaker integration
    - Structured logging
    """
    
    def __init__(self, database_url: str, config: Optional[ConnectionPoolConfig] = None):
        self.database_url = database_url
        self.config = config or ConnectionPoolConfig()
        self.metrics = ConnectionMetrics()
        self.start_time = time.time()
        
        # Threading locks
        self.lock = threading.RLock()
        self.metrics_lock = threading.Lock()
        
        # Connection objects
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        
        # Monitoring
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Query tracking
        self.query_times: List[float] = []
        self.checkout_times: List[float] = []
        
        # Initialize
        self._initialize_engine()
        self._setup_event_listeners()
        
        if self.config.enable_monitoring:
            self._start_monitoring()
    
    def _initialize_engine(self):
        """Initialize the SQLAlchemy engine with connection pooling"""
        try:
            # Determine pool class
            pool_classes = {
                PoolType.QUEUE_POOL: QueuePool,
                PoolType.NULL_POOL: NullPool,
                PoolType.STATIC_POOL: StaticPool,
            }
            
            pool_class = pool_classes.get(self.config.pool_type, QueuePool)
            
            # Engine arguments
            engine_args = {
                'url': self.database_url,
                'poolclass': pool_class,
                'echo': False,  # Set to True for SQL debugging
                'future': True,
            }
            
            # Pool-specific arguments
            if self.config.pool_type in [PoolType.QUEUE_POOL, PoolType.ASYNC_QUEUE_POOL]:
                engine_args.update({
                    'pool_size': self.config.pool_size,
                    'max_overflow': self.config.max_overflow,
                    'pool_timeout': self.config.pool_timeout,
                    'pool_recycle': self.config.pool_recycle,
                    'pool_pre_ping': self.config.pool_pre_ping,
                })
            
            # Connection arguments
            connect_args = {
                'connect_timeout': self.config.connect_timeout,
                'command_timeout': self.config.command_timeout,
            }
            engine_args['connect_args'] = connect_args
            
            # Create engine
            self.engine = create_engine(**engine_args)
            
            # Create session factory
            self.session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
            
            logger.info(
                "Database connection manager initialized",
                event_type=EventType.SYSTEM_EVENT,
                metadata={
                    "pool_type": self.config.pool_type.value,
                    "pool_size": self.config.pool_size,
                    "max_overflow": self.config.max_overflow,
                    "sqlalchemy_version": sqlalchemy_version
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize database engine",
                error=e,
                event_type=EventType.ERROR_OCCURRED
            )
            raise DatabaseConnectionException(f"Failed to initialize database: {str(e)}")
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for monitoring"""
        if not self.engine:
            return
        
        # Connection events
        @event.listens_for(self.engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            with self.metrics_lock:
                self.metrics.total_connections_created += 1
                self.metrics.last_activity = datetime.utcnow()
            
            logger.debug(
                "Database connection created",
                event_type=EventType.DATABASE_QUERY,
                metadata={"connection_id": id(dbapi_connection)}
            )
        
        @event.listens_for(self.engine, "close")
        def on_close(dbapi_connection, connection_record):
            with self.metrics_lock:
                self.metrics.total_connections_closed += 1
            
            logger.debug(
                "Database connection closed",
                event_type=EventType.DATABASE_QUERY,
                metadata={"connection_id": id(dbapi_connection)}
            )
        
        # Pool events
        @event.listens_for(self.engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            connection_record._checkout_time = time.time()
            with self.metrics_lock:
                self.metrics.total_checkouts += 1
                self.metrics.last_activity = datetime.utcnow()
        
        @event.listens_for(self.engine, "checkin")
        def on_checkin(dbapi_connection, connection_record):
            if hasattr(connection_record, '_checkout_time'):
                checkout_time = (time.time() - connection_record._checkout_time) * 1000
                self._update_checkout_time(checkout_time)
                delattr(connection_record, '_checkout_time')
            
            with self.metrics_lock:
                self.metrics.total_checkins += 1
        
        @event.listens_for(self.engine, "connect")
        def on_connect_error(dbapi_connection, connection_record, exception):
            with self.metrics_lock:
                self.metrics.connection_errors += 1
                self.metrics.total_failures += 1
            
            logger.error(
                "Database connection error",
                error=exception,
                event_type=EventType.ERROR_OCCURRED
            )
        
        # Before/After cursor execute for query timing
        @event.listens_for(self.engine, "before_cursor_execute")
        def on_before_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(self.engine, "after_cursor_execute")
        def on_after_execute(conn, cursor, statement, parameters, context, executemany):
            if hasattr(context, '_query_start_time'):
                query_time = (time.time() - context._query_start_time) * 1000
                self._update_query_time(query_time)
    
    def _update_checkout_time(self, checkout_time_ms: float):
        """Update checkout time metrics"""
        with self.metrics_lock:
            self.checkout_times.append(checkout_time_ms)
            # Keep only recent times (last 1000)
            self.checkout_times = self.checkout_times[-1000:]
            
            if self.checkout_times:
                self.metrics.average_checkout_time_ms = sum(self.checkout_times) / len(self.checkout_times)
    
    def _update_query_time(self, query_time_ms: float):
        """Update query time metrics"""
        with self.metrics_lock:
            self.query_times.append(query_time_ms)
            # Keep only recent times (last 1000)
            self.query_times = self.query_times[-1000:]
            
            if self.query_times:
                self.metrics.average_query_time_ms = sum(self.query_times) / len(self.query_times)
            
            # Count slow queries (> 1 second)
            if query_time_ms > 1000:
                self.metrics.slow_query_count += 1
    
    @contextmanager
    def get_session(self) -> ContextManager[Session]:
        """Get database session with automatic cleanup"""
        if not self.session_factory:
            raise DatabaseConnectionException("Database not initialized")
        
        session = None
        start_time = time.time()
        
        try:
            session = self.session_factory()
            yield session
            session.commit()
            
        except Exception as e:
            if session:
                session.rollback()
            
            with self.metrics_lock:
                self.metrics.query_errors += 1
            
            logger.error(
                "Database session error",
                error=e,
                event_type=EventType.ERROR_OCCURRED,
                performance_metrics={"session_duration_ms": (time.time() - start_time) * 1000}
            )
            raise DatabaseException(f"Database session error: {str(e)}")
            
        finally:
            if session:
                session.close()
    
    @asynccontextmanager
    async def get_async_session(self):
        """Get async database session (placeholder for future async implementation)"""
        # For now, run sync session in thread pool
        def get_sync_session():
            return self.get_session()
        
        loop = asyncio.get_event_loop()
        session_context = await loop.run_in_executor(None, get_sync_session)
        
        try:
            yield session_context
        finally:
            pass
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute raw SQL query"""
        with self.get_session() as session:
            start_time = time.time()
            
            try:
                result = session.execute(text(query), params or {})
                session.commit()
                
                query_time = (time.time() - start_time) * 1000
                
                logger.debug(
                    "Query executed successfully",
                    event_type=EventType.DATABASE_QUERY,
                    performance_metrics={"query_time_ms": query_time},
                    metadata={"query_length": len(query)}
                )
                
                return result
                
            except Exception as e:
                session.rollback()
                query_time = (time.time() - start_time) * 1000
                
                logger.error(
                    "Query execution failed",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    performance_metrics={"query_time_ms": query_time},
                    metadata={"query": query[:200] + "..." if len(query) > 200 else query}
                )
                raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        start_time = time.time()
        health_status = {"healthy": True, "details": {}}
        
        try:
            # Test basic connectivity
            with self.get_session() as session:
                result = session.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                
                if not row or row[0] != 1:
                    raise DatabaseException("Health check query failed")
            
            # Check pool status
            pool_status = self._get_pool_status()
            health_status["details"]["pool_status"] = pool_status
            
            # Check if pool is overloaded
            if pool_status.get("utilization_percent", 0) > 90:
                health_status["healthy"] = False
                health_status["details"]["warning"] = "Connection pool utilization > 90%"
            
            # Update metrics
            with self.metrics_lock:
                self.metrics.last_health_check = datetime.utcnow()
            
            response_time = (time.time() - start_time) * 1000
            health_status["details"]["response_time_ms"] = response_time
            
            logger.debug(
                "Database health check completed",
                event_type=EventType.SYSTEM_EVENT,
                performance_metrics={"health_check_time_ms": response_time},
                metadata={"pool_utilization": pool_status.get("utilization_percent", 0)}
            )
            
        except Exception as e:
            health_status["healthy"] = False
            health_status["details"]["error"] = str(e)
            
            with self.metrics_lock:
                self.metrics.connection_errors += 1
            
            logger.error(
                "Database health check failed",
                error=e,
                event_type=EventType.ERROR_OCCURRED
            )
        
        return health_status
    
    def _get_pool_status(self) -> Dict[str, Any]:
        """Get current connection pool status"""
        if not self.engine or not hasattr(self.engine, 'pool'):
            return {}
        
        pool = self.engine.pool
        
        status = {
            "pool_size": getattr(pool, 'size', lambda: 0)(),
            "checked_out": getattr(pool, 'checkedout', lambda: 0)(),
            "overflow": getattr(pool, 'overflow', lambda: 0)(),
            "invalid": getattr(pool, 'invalid', lambda: 0)(),
        }
        
        # Calculate utilization percentage
        total_capacity = status["pool_size"] + status["overflow"]
        if total_capacity > 0:
            status["utilization_percent"] = (status["checked_out"] / total_capacity) * 100
        else:
            status["utilization_percent"] = 0
        
        return status
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive connection manager metrics"""
        with self.metrics_lock:
            # Update runtime metrics
            self.metrics.uptime_seconds = time.time() - self.start_time
            self.metrics.pool_size = getattr(self.engine.pool, 'size', lambda: 0)() if self.engine else 0
            self.metrics.checked_out = getattr(self.engine.pool, 'checkedout', lambda: 0)() if self.engine else 0
            self.metrics.overflow = getattr(self.engine.pool, 'overflow', lambda: 0)() if self.engine else 0
            
            # Create metrics copy
            return self.metrics.to_dict()
    
    def _start_monitoring(self):
        """Start monitoring tasks"""
        self.monitoring_active = True
        
        # Start periodic metrics logging
        def log_metrics():
            if self.monitoring_active:
                metrics = self.get_metrics()
                logger.info(
                    "Database connection metrics",
                    event_type=EventType.PERFORMANCE_METRIC,
                    metadata=metrics
                )
                
                # Schedule next log
                threading.Timer(self.config.stats_interval, log_metrics).start()
        
        # Start health checks
        def periodic_health_check():
            if self.monitoring_active:
                try:
                    # Run health check in thread pool to avoid blocking
                    asyncio.run(self.health_check())
                except Exception as e:
                    logger.error(
                        "Periodic health check failed",
                        error=e,
                        event_type=EventType.ERROR_OCCURRED
                    )
                
                # Schedule next health check
                threading.Timer(self.config.health_check_interval, periodic_health_check).start()
        
        # Start both monitoring tasks
        threading.Timer(self.config.stats_interval, log_metrics).start()
        threading.Timer(self.config.health_check_interval, periodic_health_check).start()
        
        logger.info(
            "Database monitoring started",
            event_type=EventType.SYSTEM_EVENT,
            metadata={
                "stats_interval": self.config.stats_interval,
                "health_check_interval": self.config.health_check_interval
            }
        )
    
    def stop_monitoring(self):
        """Stop monitoring tasks"""
        self.monitoring_active = False
        logger.info("Database monitoring stopped", event_type=EventType.SYSTEM_EVENT)
    
    def reset_metrics(self):
        """Reset connection metrics"""
        with self.metrics_lock:
            self.metrics = ConnectionMetrics()
            self.query_times.clear()
            self.checkout_times.clear()
            self.start_time = time.time()
        
        logger.info("Database metrics reset", event_type=EventType.SYSTEM_EVENT)
    
    def close(self):
        """Close database connection manager"""
        self.stop_monitoring()
        
        if self.engine:
            self.engine.dispose()
            logger.info(
                "Database connection manager closed",
                event_type=EventType.SYSTEM_EVENT,
                metadata=self.get_metrics()
            )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()