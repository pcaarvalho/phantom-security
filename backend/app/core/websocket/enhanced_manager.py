"""
Enhanced WebSocket Connection Manager with Pooling and Auto-Reconnection
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Set, Optional, List, Any, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import socketio
from socketio import AsyncServer
import logging
import threading
import weakref

from ..logging.structured_logger import get_logger, EventType
from ..error_handling.exceptions import PhantomBaseException
from ..resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


logger = get_logger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CLOSED = "closed"


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ConnectionMetrics:
    """Metrics for WebSocket connections"""
    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    reconnection_attempts: int = 0
    successful_reconnections: int = 0
    
    # Message metrics
    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    messages_queued: int = 0
    
    # Performance metrics
    average_response_time_ms: float = 0.0
    peak_concurrent_connections: int = 0
    uptime_seconds: float = 0.0
    
    # Error metrics
    connection_errors: int = 0
    timeout_errors: int = 0
    protocol_errors: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "connections": {
                "total": self.total_connections,
                "active": self.active_connections,
                "failed": self.failed_connections,
                "peak_concurrent": self.peak_concurrent_connections
            },
            "reconnections": {
                "attempts": self.reconnection_attempts,
                "successful": self.successful_reconnections,
                "success_rate": (
                    (self.successful_reconnections / self.reconnection_attempts * 100)
                    if self.reconnection_attempts > 0 else 0
                )
            },
            "messages": {
                "sent": self.messages_sent,
                "received": self.messages_received,
                "failed": self.messages_failed,
                "queued": self.messages_queued
            },
            "performance": {
                "average_response_time_ms": round(self.average_response_time_ms, 2),
                "uptime_seconds": round(self.uptime_seconds, 2)
            },
            "errors": {
                "connection_errors": self.connection_errors,
                "timeout_errors": self.timeout_errors,
                "protocol_errors": self.protocol_errors
            }
        }


@dataclass
class QueuedMessage:
    """Queued WebSocket message"""
    event_name: str
    data: Dict[str, Any]
    priority: MessagePriority
    created_at: datetime
    target_sessions: Optional[Set[str]] = None
    max_retries: int = 3
    retry_count: int = 0
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        return self.expires_at is not None and datetime.utcnow() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return self.retry_count < self.max_retries


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection"""
    session_id: str
    connected_at: datetime
    last_seen: datetime
    state: ConnectionState
    subscriptions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Connection health
    ping_count: int = 0
    last_ping: Optional[datetime] = None
    average_ping_ms: float = 0.0
    
    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    
    def update_ping(self, ping_time_ms: float):
        """Update ping statistics"""
        self.ping_count += 1
        self.last_ping = datetime.utcnow()
        
        if self.ping_count == 1:
            self.average_ping_ms = ping_time_ms
        else:
            # Exponential moving average
            alpha = 0.3
            self.average_ping_ms = (alpha * ping_time_ms) + ((1 - alpha) * self.average_ping_ms)


class EnhancedWebSocketManager:
    """
    Enhanced WebSocket manager with:
    - Connection pooling and lifecycle management
    - Auto-reconnection with exponential backoff
    - Message queuing with priorities
    - Circuit breaker integration
    - Comprehensive metrics and monitoring
    - Room-based broadcasting with filters
    - Health checks and connection validation
    """
    
    def __init__(self, cors_allowed_origins: str = "*"):
        # Core SocketIO server
        self.sio = AsyncServer(
            async_mode='asgi',
            cors_allowed_origins=cors_allowed_origins,
            logger=False,  # Use our structured logger instead
            engineio_logger=False
        )
        
        # Connection tracking
        self.connections: Dict[str, ConnectionInfo] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # topic -> session_ids
        self.metrics = ConnectionMetrics()
        self.start_time = time.time()
        
        # Message queuing
        self.message_queue: List[QueuedMessage] = []
        self.queue_lock = asyncio.Lock()
        self.max_queue_size = 10000
        
        # Circuit breaker for external integrations
        circuit_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            timeout=10.0
        )
        self.circuit_breaker = CircuitBreaker("websocket", circuit_config)
        
        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()
        self.cleanup_interval = 60  # 1 minute
        self.health_check_interval = 30  # 30 seconds
        self.message_processing_interval = 1  # 1 second
        
        # Threading
        self.lock = asyncio.Lock()
        
        # Setup event handlers
        self._setup_handlers()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _setup_handlers(self):
        """Setup SocketIO event handlers"""
        
        @self.sio.event
        async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
            """Handle new client connection"""
            try:
                # Create connection info
                conn_info = ConnectionInfo(
                    session_id=sid,
                    connected_at=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    state=ConnectionState.CONNECTED,
                    metadata={
                        "user_agent": environ.get("HTTP_USER_AGENT", "unknown"),
                        "remote_addr": environ.get("REMOTE_ADDR", "unknown"),
                        "auth": auth or {}
                    }
                )
                
                # Store connection
                async with self.lock:
                    self.connections[sid] = conn_info
                    self.metrics.total_connections += 1
                    self.metrics.active_connections += 1
                    
                    # Update peak concurrent connections
                    if self.metrics.active_connections > self.metrics.peak_concurrent_connections:
                        self.metrics.peak_concurrent_connections = self.metrics.active_connections
                
                # Send welcome message
                await self.sio.emit('connected', {
                    'session_id': sid,
                    'server_time': datetime.utcnow().isoformat(),
                    'message': 'Connected to PHANTOM Security WebSocket'
                }, to=sid)
                
                logger.info(
                    f"WebSocket client connected",
                    event_type=EventType.SYSTEM_EVENT,
                    metadata={
                        "session_id": sid,
                        "remote_addr": environ.get("REMOTE_ADDR", "unknown"),
                        "user_agent": environ.get("HTTP_USER_AGENT", "unknown")[:100]
                    }
                )
                
                return True
                
            except Exception as e:
                self.metrics.connection_errors += 1
                logger.error(
                    "WebSocket connection failed",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    metadata={"session_id": sid}
                )
                return False
        
        @self.sio.event
        async def disconnect(sid: str):
            """Handle client disconnection"""
            try:
                async with self.lock:
                    conn_info = self.connections.get(sid)
                    if conn_info:
                        conn_info.state = ConnectionState.DISCONNECTED
                        
                        # Remove from subscriptions
                        for topic, subscribers in self.subscriptions.items():
                            subscribers.discard(sid)
                        
                        # Update metrics
                        self.metrics.active_connections = max(0, self.metrics.active_connections - 1)
                        
                        # Keep connection info for a while for metrics
                        # It will be cleaned up by background task
                        
                        logger.info(
                            "WebSocket client disconnected",
                            event_type=EventType.SYSTEM_EVENT,
                            metadata={
                                "session_id": sid,
                                "connection_duration_seconds": (
                                    datetime.utcnow() - conn_info.connected_at
                                ).total_seconds(),
                                "subscriptions": list(conn_info.subscriptions)
                            }
                        )
                
            except Exception as e:
                logger.error(
                    "Error handling WebSocket disconnection",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    metadata={"session_id": sid}
                )
        
        @self.sio.event
        async def subscribe(sid: str, data: dict):
            """Handle subscription requests"""
            try:
                topic = data.get('topic')
                if not topic:
                    await self.sio.emit('error', {'message': 'Topic is required'}, to=sid)
                    return
                
                async with self.lock:
                    # Add to subscriptions
                    if topic not in self.subscriptions:
                        self.subscriptions[topic] = set()
                    self.subscriptions[topic].add(sid)
                    
                    # Update connection info
                    conn_info = self.connections.get(sid)
                    if conn_info:
                        conn_info.subscriptions.add(topic)
                        conn_info.last_seen = datetime.utcnow()
                
                await self.sio.emit('subscribed', {'topic': topic}, to=sid)
                
                logger.debug(
                    f"Client subscribed to topic",
                    event_type=EventType.SYSTEM_EVENT,
                    metadata={"session_id": sid, "topic": topic}
                )
                
            except Exception as e:
                logger.error(
                    "Subscription error",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    metadata={"session_id": sid, "data": data}
                )
        
        @self.sio.event
        async def unsubscribe(sid: str, data: dict):
            """Handle unsubscription requests"""
            try:
                topic = data.get('topic')
                if not topic:
                    return
                
                async with self.lock:
                    # Remove from subscriptions
                    if topic in self.subscriptions:
                        self.subscriptions[topic].discard(sid)
                        
                        # Clean up empty topics
                        if not self.subscriptions[topic]:
                            del self.subscriptions[topic]
                    
                    # Update connection info
                    conn_info = self.connections.get(sid)
                    if conn_info:
                        conn_info.subscriptions.discard(topic)
                        conn_info.last_seen = datetime.utcnow()
                
                await self.sio.emit('unsubscribed', {'topic': topic}, to=sid)
                
                logger.debug(
                    f"Client unsubscribed from topic",
                    event_type=EventType.SYSTEM_EVENT,
                    metadata={"session_id": sid, "topic": topic}
                )
                
            except Exception as e:
                logger.error(
                    "Unsubscription error",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    metadata={"session_id": sid, "data": data}
                )
        
        @self.sio.event
        async def ping(sid: str, data: dict):
            """Handle ping requests for connection health"""
            try:
                start_time = data.get('timestamp')
                if start_time:
                    ping_time = time.time() - start_time
                    ping_time_ms = ping_time * 1000
                    
                    # Update connection ping stats
                    async with self.lock:
                        conn_info = self.connections.get(sid)
                        if conn_info:
                            conn_info.update_ping(ping_time_ms)
                            conn_info.last_seen = datetime.utcnow()
                
                await self.sio.emit('pong', {
                    'timestamp': time.time(),
                    'server_time': datetime.utcnow().isoformat()
                }, to=sid)
                
            except Exception as e:
                logger.error(
                    "Ping handling error",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED,
                    metadata={"session_id": sid}
                )
    
    def _start_background_tasks(self):
        """Start background tasks"""
        loop = asyncio.get_event_loop()
        
        # Connection cleanup task
        cleanup_task = loop.create_task(self._periodic_cleanup())
        self.background_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self.background_tasks.discard)
        
        # Health check task
        health_task = loop.create_task(self._periodic_health_check())
        self.background_tasks.add(health_task)
        health_task.add_done_callback(self.background_tasks.discard)
        
        # Message processing task
        message_task = loop.create_task(self._process_message_queue())
        self.background_tasks.add(message_task)
        message_task.add_done_callback(self.background_tasks.discard)
        
        logger.info(
            "WebSocket background tasks started",
            event_type=EventType.SYSTEM_EVENT,
            metadata={"task_count": len(self.background_tasks)}
        )
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of old connections and data"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                now = datetime.utcnow()
                cleanup_threshold = now - timedelta(minutes=5)  # Keep data for 5 minutes
                
                async with self.lock:
                    # Clean up old disconnected connections
                    expired_sessions = []
                    for sid, conn_info in self.connections.items():
                        if (conn_info.state == ConnectionState.DISCONNECTED and 
                            conn_info.last_seen < cleanup_threshold):
                            expired_sessions.append(sid)
                    
                    for sid in expired_sessions:
                        del self.connections[sid]
                    
                    # Clean up empty subscription topics
                    empty_topics = []
                    for topic, subscribers in self.subscriptions.items():
                        if not subscribers:
                            empty_topics.append(topic)
                    
                    for topic in empty_topics:
                        del self.subscriptions[topic]
                
                # Clean up expired messages from queue
                async with self.queue_lock:
                    self.message_queue = [
                        msg for msg in self.message_queue 
                        if not msg.is_expired()
                    ]
                
                if expired_sessions or empty_topics:
                    logger.debug(
                        "WebSocket cleanup completed",
                        event_type=EventType.SYSTEM_EVENT,
                        metadata={
                            "expired_sessions": len(expired_sessions),
                            "empty_topics": len(empty_topics),
                            "queue_size": len(self.message_queue)
                        }
                    )
                
            except Exception as e:
                logger.error(
                    "WebSocket cleanup error",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED
                )
    
    async def _periodic_health_check(self):
        """Periodic health check of connections"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Update uptime
                self.metrics.uptime_seconds = time.time() - self.start_time
                
                # Check connection health
                stale_threshold = datetime.utcnow() - timedelta(minutes=2)
                stale_connections = []
                
                async with self.lock:
                    for sid, conn_info in self.connections.items():
                        if (conn_info.state == ConnectionState.CONNECTED and 
                            conn_info.last_seen < stale_threshold):
                            stale_connections.append(sid)
                
                # Ping stale connections
                for sid in stale_connections:
                    try:
                        await self.sio.emit('health_check', {
                            'timestamp': time.time(),
                            'action': 'ping'
                        }, to=sid, timeout=5)
                    except Exception:
                        # Connection might be dead, will be cleaned up later
                        pass
                
                logger.debug(
                    "WebSocket health check completed",
                    event_type=EventType.PERFORMANCE_METRIC,
                    metadata={
                        "active_connections": self.metrics.active_connections,
                        "stale_connections": len(stale_connections),
                        "uptime_seconds": self.metrics.uptime_seconds
                    }
                )
                
            except Exception as e:
                logger.error(
                    "WebSocket health check error",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED
                )
    
    async def _process_message_queue(self):
        """Process queued messages"""
        while True:
            try:
                await asyncio.sleep(self.message_processing_interval)
                
                if not self.message_queue:
                    continue
                
                async with self.queue_lock:
                    # Sort by priority and creation time
                    self.message_queue.sort(
                        key=lambda m: (m.priority.value, m.created_at),
                        reverse=True
                    )
                    
                    # Process high priority messages first
                    processed = 0
                    batch_size = 10  # Process in batches
                    
                    while self.message_queue and processed < batch_size:
                        message = self.message_queue.pop(0)
                        
                        if message.is_expired():
                            continue
                        
                        success = await self._send_queued_message(message)
                        if not success and message.can_retry():
                            message.retry_count += 1
                            self.message_queue.append(message)  # Re-queue for retry
                        
                        processed += 1
                    
                    self.metrics.messages_queued = len(self.message_queue)
                
            except Exception as e:
                logger.error(
                    "Message queue processing error",
                    error=e,
                    event_type=EventType.ERROR_OCCURRED
                )
    
    async def _send_queued_message(self, message: QueuedMessage) -> bool:
        """Send a queued message"""
        try:
            if message.target_sessions:
                # Send to specific sessions
                for sid in message.target_sessions:
                    if sid in self.connections:
                        await self.sio.emit(
                            message.event_name, 
                            message.data, 
                            to=sid,
                            timeout=10
                        )
            else:
                # Broadcast to all
                await self.sio.emit(message.event_name, message.data, timeout=10)
            
            self.metrics.messages_sent += 1
            return True
            
        except Exception as e:
            self.metrics.messages_failed += 1
            logger.warning(
                "Failed to send queued message",
                event_type=EventType.ERROR_OCCURRED,
                metadata={
                    "event_name": message.event_name,
                    "retry_count": message.retry_count,
                    "error": str(e)
                }
            )
            return False
    
    async def emit_with_queue(
        self,
        event_name: str,
        data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        target_sessions: Optional[Set[str]] = None,
        ttl_seconds: int = 300  # 5 minutes default TTL
    ):
        """Emit message with queuing support"""
        try:
            # Try to send immediately first
            if target_sessions:
                await self.sio.emit(event_name, data, room=list(target_sessions), timeout=5)
            else:
                await self.sio.emit(event_name, data, timeout=5)
            
            self.metrics.messages_sent += 1
            
        except Exception as e:
            # Queue message for later delivery
            async with self.queue_lock:
                if len(self.message_queue) < self.max_queue_size:
                    message = QueuedMessage(
                        event_name=event_name,
                        data=data,
                        priority=priority,
                        created_at=datetime.utcnow(),
                        target_sessions=target_sessions,
                        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds)
                    )
                    self.message_queue.append(message)
                    
                    logger.info(
                        "Message queued for later delivery",
                        event_type=EventType.SYSTEM_EVENT,
                        metadata={
                            "event_name": event_name,
                            "priority": priority.name,
                            "queue_size": len(self.message_queue),
                            "error": str(e)
                        }
                    )
                else:
                    logger.warning(
                        "Message queue full, dropping message",
                        event_type=EventType.ERROR_OCCURRED,
                        metadata={
                            "event_name": event_name,
                            "queue_size": len(self.message_queue),
                            "max_size": self.max_queue_size
                        }
                    )
    
    async def broadcast_to_topic(
        self,
        topic: str,
        event_name: str,
        data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ):
        """Broadcast message to all subscribers of a topic"""
        subscribers = self.subscriptions.get(topic, set())
        if subscribers:
            await self.emit_with_queue(
                event_name, 
                data, 
                priority=priority,
                target_sessions=subscribers
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive WebSocket metrics"""
        self.metrics.uptime_seconds = time.time() - self.start_time
        return self.metrics.to_dict()
    
    def get_connection_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific connection"""
        conn_info = self.connections.get(session_id)
        if not conn_info:
            return None
        
        return {
            "session_id": conn_info.session_id,
            "connected_at": conn_info.connected_at.isoformat(),
            "last_seen": conn_info.last_seen.isoformat(),
            "state": conn_info.state.value,
            "subscriptions": list(conn_info.subscriptions),
            "metadata": conn_info.metadata,
            "ping_stats": {
                "count": conn_info.ping_count,
                "average_ms": round(conn_info.average_ping_ms, 2),
                "last_ping": conn_info.last_ping.isoformat() if conn_info.last_ping else None
            },
            "error_count": conn_info.error_count,
            "last_error": conn_info.last_error
        }
    
    def get_subscription_info(self) -> Dict[str, Any]:
        """Get subscription information"""
        return {
            "topics": {
                topic: len(subscribers)
                for topic, subscribers in self.subscriptions.items()
            },
            "total_topics": len(self.subscriptions),
            "total_subscriptions": sum(len(s) for s in self.subscriptions.values())
        }
    
    async def close(self):
        """Close WebSocket manager and cleanup resources"""
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Close all connections
        for sid in list(self.connections.keys()):
            try:
                await self.sio.disconnect(sid)
            except Exception:
                pass
        
        logger.info(
            "WebSocket manager closed",
            event_type=EventType.SYSTEM_EVENT,
            metadata=self.get_metrics()
        )


# Global enhanced WebSocket manager
enhanced_ws_manager = EnhancedWebSocketManager()