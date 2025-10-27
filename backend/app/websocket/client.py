"""
WebSocket client for Celery tasks to send events
Since Celery runs in separate processes, we need a client to communicate with the WebSocket server
"""

import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class WebSocketClient:
    """Client for sending WebSocket events from Celery tasks"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    async def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Send event via HTTP to the WebSocket server"""
        try:
            # Since we can't directly access the WebSocket from Celery,
            # we'll use an HTTP endpoint to trigger WebSocket events
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/websocket/emit"
                payload = {
                    "event_type": event_type,
                    "data": data
                }
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to emit WebSocket event: {await response.text()}")
        except Exception as e:
            logger.error(f"Error emitting WebSocket event: {e}")
    
    def emit_sync(self, event_type: str, data: Dict[str, Any]):
        """Synchronous wrapper for emit_event"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.emit_event(event_type, data))
        except Exception as e:
            logger.error(f"Error in sync emit: {e}")
    
    def send_progress(self, scan_id: str, progress: int, phase: str, message: str):
        """Send progress update"""
        self.emit_sync("scan_progress", {
            "scan_id": scan_id,
            "progress": progress,
            "phase": phase,
            "message": message
        })
    
    def send_scan_started(self, scan_id: str, target: str):
        """Send scan started event"""
        self.emit_sync("scan_started", {
            "scan_id": scan_id,
            "target": target
        })
    
    def send_scan_completed(self, scan_id: str, results: Dict):
        """Send scan completed event"""
        self.emit_sync("scan_completed", {
            "scan_id": scan_id,
            "results": results
        })
    
    def send_scan_failed(self, scan_id: str, error: str):
        """Send scan failed event"""
        self.emit_sync("scan_failed", {
            "scan_id": scan_id,
            "error": error
        })


# Global client instance for Celery tasks
ws_client = WebSocketClient()