"""
WebSocket event definitions
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class EventType(Enum):
    """Types of WebSocket events"""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    
    # Scan events
    SCAN_STARTED = "scan_started"
    SCAN_PROGRESS = "scan_progress"
    SCAN_PHASE_CHANGE = "scan_phase_change"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"
    
    # Finding events
    VULNERABILITY_FOUND = "vulnerability_found"
    CRITICAL_FINDING = "critical_finding"
    PORT_DISCOVERED = "port_discovered"
    SUBDOMAIN_FOUND = "subdomain_found"
    
    # System events
    NOTIFICATION = "notification"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ScanEvent(BaseModel):
    """WebSocket event model"""
    event_type: EventType
    scan_id: Optional[str] = None
    task_id: Optional[str] = None
    data: Dict[str, Any]
    timestamp: datetime = None
    severity: Optional[str] = None  # critical, high, medium, low, info
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return {
            "event_type": self.event_type.value,
            "scan_id": self.scan_id,
            "task_id": self.task_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity
        }


class ProgressEvent(ScanEvent):
    """Special event for progress updates"""
    def __init__(self, scan_id: str, progress: int, phase: str, message: str):
        super().__init__(
            event_type=EventType.SCAN_PROGRESS,
            scan_id=scan_id,
            data={
                "progress": progress,
                "phase": phase,
                "message": message
            }
        )


class VulnerabilityEvent(ScanEvent):
    """Special event for vulnerability findings"""
    def __init__(self, scan_id: str, vulnerability: Dict[str, Any]):
        severity = vulnerability.get("severity", "medium").lower()
        event_type = EventType.CRITICAL_FINDING if severity == "critical" else EventType.VULNERABILITY_FOUND
        
        super().__init__(
            event_type=event_type,
            scan_id=scan_id,
            data=vulnerability,
            severity=severity
        )


class NotificationEvent(ScanEvent):
    """Special event for notifications"""
    def __init__(self, title: str, message: str, severity: str = "info"):
        super().__init__(
            event_type=EventType.NOTIFICATION,
            data={
                "title": title,
                "message": message
            },
            severity=severity
        )