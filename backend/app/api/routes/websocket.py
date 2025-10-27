"""
WebSocket API routes for internal event emission
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from app.websocket.manager import ws_manager
from app.websocket.events import ScanEvent, EventType

router = APIRouter()


class EmitEventRequest(BaseModel):
    event_type: str
    data: Dict[str, Any]


@router.post("/emit")
async def emit_websocket_event(request: EmitEventRequest):
    """
    Internal endpoint for Celery tasks to emit WebSocket events
    """
    try:
        # Map string event type to EventType enum
        event_type_map = {
            "scan_started": EventType.SCAN_STARTED,
            "scan_progress": EventType.SCAN_PROGRESS,
            "scan_completed": EventType.SCAN_COMPLETED,
            "scan_failed": EventType.SCAN_FAILED,
            "vulnerability_found": EventType.VULNERABILITY_FOUND,
            "critical_finding": EventType.CRITICAL_FINDING,
            "notification": EventType.NOTIFICATION
        }
        
        event_type = event_type_map.get(request.event_type)
        if not event_type:
            raise HTTPException(status_code=400, detail=f"Unknown event type: {request.event_type}")
        
        # Create and broadcast event
        event = ScanEvent(
            event_type=event_type,
            scan_id=request.data.get("scan_id"),
            data=request.data
        )
        
        if event.scan_id:
            await ws_manager.broadcast_scan_event(event)
        else:
            await ws_manager.broadcast_to_all(event)
        
        return {"status": "success", "message": "Event emitted"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections")
async def get_websocket_connections():
    """Get current WebSocket connection statistics"""
    return {
        "total_connections": len(ws_manager.all_sessions),
        "active_scans": len(ws_manager.active_connections),
        "connections_per_scan": {
            scan_id: len(sessions) 
            for scan_id, sessions in ws_manager.active_connections.items()
        }
    }