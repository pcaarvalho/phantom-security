"""
WebSocket connection manager for real-time updates
"""

import json
import asyncio
from typing import Dict, Set, Optional, List
from datetime import datetime
import socketio
from .events import ScanEvent, EventType, ProgressEvent, VulnerabilityEvent, NotificationEvent


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events"""
    
    def __init__(self):
        # Create Socket.IO server with CORS support
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins="*",  # In production, specify exact origins
            logger=True,
            engineio_logger=False
        )
        
        # Track connected clients
        self.active_connections: Dict[str, Set[str]] = {}  # scan_id -> set of session_ids
        self.session_to_scans: Dict[str, Set[str]] = {}  # session_id -> set of scan_ids
        self.all_sessions: Set[str] = set()
        
        # Setup event handlers
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup Socket.IO event handlers"""
        
        @self.sio.event
        async def connect(sid, environ):
            """Handle new client connection"""
            print(f"[WebSocket] Client connected: {sid}")
            self.all_sessions.add(sid)
            self.session_to_scans[sid] = set()
            
            # Send connection confirmation
            await self.sio.emit(
                'connected',
                {'message': 'Connected to PHANTOM Security WebSocket', 'sid': sid},
                to=sid
            )
            
            return True
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection"""
            print(f"[WebSocket] Client disconnected: {sid}")
            
            # Remove from all tracking
            self.all_sessions.discard(sid)
            
            # Remove from scan subscriptions
            if sid in self.session_to_scans:
                for scan_id in self.session_to_scans[sid]:
                    if scan_id in self.active_connections:
                        self.active_connections[scan_id].discard(sid)
                del self.session_to_scans[sid]
        
        @self.sio.event
        async def subscribe_scan(sid, data):
            """Subscribe to scan updates"""
            scan_id = data.get('scan_id')
            if not scan_id:
                await self.sio.emit('error', {'message': 'scan_id required'}, to=sid)
                return
            
            # Add to tracking
            if scan_id not in self.active_connections:
                self.active_connections[scan_id] = set()
            self.active_connections[scan_id].add(sid)
            self.session_to_scans[sid].add(scan_id)
            
            print(f"[WebSocket] {sid} subscribed to scan {scan_id}")
            await self.sio.emit(
                'subscribed',
                {'scan_id': scan_id, 'message': f'Subscribed to scan {scan_id}'},
                to=sid
            )
        
        @self.sio.event
        async def unsubscribe_scan(sid, data):
            """Unsubscribe from scan updates"""
            scan_id = data.get('scan_id')
            if not scan_id:
                return
            
            # Remove from tracking
            if scan_id in self.active_connections:
                self.active_connections[scan_id].discard(sid)
            if sid in self.session_to_scans:
                self.session_to_scans[sid].discard(scan_id)
            
            print(f"[WebSocket] {sid} unsubscribed from scan {scan_id}")
            await self.sio.emit(
                'unsubscribed',
                {'scan_id': scan_id},
                to=sid
            )
    
    async def broadcast_scan_event(self, event: ScanEvent):
        """Broadcast event to all subscribers of a scan"""
        if event.scan_id and event.scan_id in self.active_connections:
            subscribers = list(self.active_connections[event.scan_id])
            if subscribers:
                print(f"[WebSocket] Broadcasting {event.event_type.value} to {len(subscribers)} clients")
                await self.sio.emit(
                    event.event_type.value,
                    event.to_dict(),
                    room=subscribers
                )
    
    async def broadcast_to_all(self, event: ScanEvent):
        """Broadcast event to all connected clients"""
        if self.all_sessions:
            print(f"[WebSocket] Broadcasting {event.event_type.value} to all clients")
            await self.sio.emit(
                event.event_type.value,
                event.to_dict()
            )
    
    async def send_progress(self, scan_id: str, progress: int, phase: str, message: str):
        """Send progress update for a scan"""
        event = ProgressEvent(scan_id, progress, phase, message)
        await self.broadcast_scan_event(event)
    
    async def send_vulnerability(self, scan_id: str, vulnerability: Dict):
        """Send vulnerability finding"""
        event = VulnerabilityEvent(scan_id, vulnerability)
        await self.broadcast_scan_event(event)
        
        # Also broadcast critical findings to all
        if vulnerability.get("severity", "").lower() == "critical":
            await self.broadcast_to_all(event)
    
    async def send_notification(self, title: str, message: str, severity: str = "info", scan_id: Optional[str] = None):
        """Send notification"""
        event = NotificationEvent(title, message, severity)
        if scan_id:
            event.scan_id = scan_id
            await self.broadcast_scan_event(event)
        else:
            await self.broadcast_to_all(event)
    
    async def send_scan_started(self, scan_id: str, target: str):
        """Notify scan started"""
        event = ScanEvent(
            event_type=EventType.SCAN_STARTED,
            scan_id=scan_id,
            data={"target": target, "started_at": datetime.utcnow().isoformat()}
        )
        await self.broadcast_scan_event(event)
    
    async def send_scan_completed(self, scan_id: str, results: Dict):
        """Notify scan completed"""
        event = ScanEvent(
            event_type=EventType.SCAN_COMPLETED,
            scan_id=scan_id,
            data={
                "completed_at": datetime.utcnow().isoformat(),
                "risk_score": results.get("risk_score", 0),
                "vulnerabilities_count": len(results.get("vulnerabilities", [])),
                "critical_findings": results.get("critical_findings", [])
            }
        )
        await self.broadcast_scan_event(event)
    
    async def send_scan_failed(self, scan_id: str, error: str):
        """Notify scan failed"""
        event = ScanEvent(
            event_type=EventType.SCAN_FAILED,
            scan_id=scan_id,
            data={"error": error, "failed_at": datetime.utcnow().isoformat()},
            severity="error"
        )
        await self.broadcast_scan_event(event)
    
    def get_app(self):
        """Get Socket.IO ASGI app"""
        return self.sio


# Global WebSocket manager instance
ws_manager = WebSocketManager()