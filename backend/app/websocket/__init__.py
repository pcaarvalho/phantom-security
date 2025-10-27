"""
WebSocket module for real-time communication
"""

from .manager import WebSocketManager
from .events import ScanEvent, EventType

__all__ = ['WebSocketManager', 'ScanEvent', 'EventType']