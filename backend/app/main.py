from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import socketio
from app.config import settings
from app.api.routes import scans, reports, auth, websocket
from app.websocket.manager import ws_manager

app = FastAPI(
    title="PHANTOM Security AI",
    description="Autonomous vulnerability detection powered by artificial intelligence",
    version="1.0.0"
)

# Create Socket.IO app
socket_app = socketio.ASGIApp(ws_manager.sio, app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(scans.router, prefix="/api/scans", tags=["scans"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(websocket.router, prefix="/api/websocket", tags=["websocket"])

@app.get("/")
async def root():
    return {"message": "PHANTOM Security AI API", "status": "running"}

@app.get("/health")
async def health_check():
    """Enhanced health check with detailed service monitoring"""
    from app.core.resilience.health_checks import health_manager
    from app.database import get_db_health
    
    try:
        # Get comprehensive health status
        health_status = await health_manager.check_all()
        
        # Add basic API health info
        health_status["api"] = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": health_status["timestamp"]
        }
        
        return health_status
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/health/metrics")
async def health_metrics():
    """Get detailed health metrics"""
    from app.core.resilience.health_checks import health_manager
    from app.core.resilience.circuit_breaker import circuit_breaker_manager
    from app.core.resilience.rate_limiter import rate_limiter_manager
    from app.core.error_handling.error_handler import global_error_handler
    
    try:
        return {
            "health_checks": health_manager.get_statistics(),
            "circuit_breakers": circuit_breaker_manager.get_all_metrics(),
            "rate_limiters": rate_limiter_manager.get_all_metrics(),
            "error_handlers": global_error_handler.get_all_metrics(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred"}
    )

# Export the Socket.IO app for uvicorn
# Run with: uvicorn app.main:socket_app --reload --port 8000
__all__ = ['app', 'socket_app']