"""
API routes for vulnerability scanning operations
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from app.database import get_db
from app.models.scan import Scan, ScanStatus
from app.schemas.scan import ScanCreate, ScanResponse, ScanDetails
from app.tasks.scan_tasks import (
    start_scan_task, 
    quick_scan_task, 
    recon_task,
    generate_exploits_task,
    get_task_status
)
from app.core.scanner.orchestrator import PhantomBrain

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ScanResponse)
async def create_scan(
    scan_data: ScanCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create and start a new vulnerability scan
    """
    try:
        # Validate target
        if not scan_data.target:
            raise HTTPException(status_code=400, detail="Target is required")
            
        # Create scan record
        scan = Scan(
            target=scan_data.target,
            status=ScanStatus.PENDING,
            scan_type=scan_data.scan_type or "comprehensive",
            created_at=datetime.utcnow()
        )
        
        db.add(scan)
        db.commit()
        db.refresh(scan)
        
        # Start background task based on scan type
        if scan_data.scan_type == "quick":
            task = quick_scan_task.delay(scan_data.target)
        elif scan_data.scan_type == "recon":
            task = recon_task.delay(scan_data.target)
        else:
            task = start_scan_task.delay(scan.id)
        
        # Update scan with task ID
        scan.task_id = str(task.id)
        db.commit()
        
        logger.info(f"Created scan {scan.id} for target {scan.target}, task ID: {task.id}")
        
        return ScanResponse(
            id=scan.id,
            target=scan.target,
            status=scan.status,
            scan_type=scan.scan_type,
            task_id=scan.task_id,
            started_at=scan.started_at,
            created_at=scan.created_at
        )
        
    except Exception as e:
        logger.error(f"Failed to create scan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ScanResponse])
async def get_scans(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[ScanStatus] = None,
    target: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get list of scans with optional filtering
    """
    query = db.query(Scan)
    
    # Apply filters
    if status:
        query = query.filter(Scan.status == status)
    if target:
        query = query.filter(Scan.target.contains(target))
        
    # Get total count
    total = query.count()
    
    # Get paginated results
    scans = query.order_by(Scan.created_at.desc()).offset(skip).limit(limit).all()
    
    return [ScanResponse.model_validate(scan) for scan in scans]

@router.get("/{scan_id}", response_model=ScanDetails)
async def get_scan(scan_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific scan
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Include task status if available
    task_status = None
    if scan.task_id:
        task_status = get_task_status(scan.task_id)
    
    response = ScanDetails.model_validate(scan)
    response.task_status = task_status
    
    return response

@router.get("/{scan_id}/status")
async def get_scan_status(scan_id: int, db: Session = Depends(get_db)):
    """
    Get current status of a scan including task progress
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Get task status
    task_status = {}
    if scan.task_id:
        task_status = get_task_status(scan.task_id)
    
    return {
        "scan_id": scan.id,
        "target": scan.target,
        "status": scan.status.value,
        "progress": task_status.get("progress", 0),
        "current_phase": task_status.get("status", ""),
        "task_state": task_status.get("state", "UNKNOWN"),
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "vulnerability_count": scan.vulnerability_count,
        "risk_score": scan.risk_score
    }

@router.get("/{scan_id}/results")
async def get_scan_results(scan_id: int, db: Session = Depends(get_db)):
    """
    Get detailed scan results
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    if scan.status != ScanStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Scan not completed yet")
    
    return {
        "scan_id": scan.id,
        "target": scan.target,
        "scan_results": scan.scan_results,
        "ai_analysis": scan.ai_analysis,
        "vulnerability_count": scan.vulnerability_count,
        "risk_score": scan.risk_score,
        "summary": scan.summary
    }

@router.get("/{scan_id}/vulnerabilities")
async def get_scan_vulnerabilities(
    scan_id: int,
    severity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get vulnerabilities found in a scan
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    if not scan.scan_results:
        return {"vulnerabilities": [], "total": 0}
    
    # Extract vulnerabilities from scan results
    vulnerabilities = []
    
    # Get from different scan phases
    phases = scan.scan_results.get("phases", {})
    
    # From vulnerability scan phase
    vuln_phase = phases.get("vulnerability_scan", {}).get("data", {})
    vulnerabilities.extend(vuln_phase.get("vulnerabilities", []))
    
    # Filter by severity if requested
    if severity:
        vulnerabilities = [
            v for v in vulnerabilities 
            if v.get("severity", "").upper() == severity.upper()
        ]
    
    return {
        "vulnerabilities": vulnerabilities,
        "total": len(vulnerabilities),
        "by_severity": _count_by_severity(vulnerabilities)
    }

@router.post("/{scan_id}/exploits")
async def generate_exploits(
    scan_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Generate proof-of-concept exploits for scan vulnerabilities
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    if scan.status != ScanStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Scan must be completed first")
    
    # Get vulnerabilities
    vulnerabilities = []
    phases = scan.scan_results.get("phases", {})
    vuln_phase = phases.get("vulnerability_scan", {}).get("data", {})
    vulnerabilities = vuln_phase.get("vulnerabilities", [])
    
    if not vulnerabilities:
        return {"message": "No vulnerabilities to exploit"}
    
    # Start exploit generation task
    task = generate_exploits_task.delay(vulnerabilities[:10])  # Limit to top 10
    
    return {
        "message": "Exploit generation started",
        "task_id": str(task.id),
        "vulnerability_count": len(vulnerabilities)
    }

@router.post("/{scan_id}/restart")
async def restart_scan(scan_id: int, db: Session = Depends(get_db)):
    """
    Restart a failed or completed scan
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Reset scan status
    scan.status = ScanStatus.PENDING
    scan.scan_results = None
    scan.ai_analysis = None
    scan.vulnerability_count = 0
    scan.risk_score = 0
    scan.error_message = None
    scan.started_at = None
    scan.completed_at = None
    
    db.commit()
    
    # Restart background task
    task = start_scan_task.delay(scan.id)
    scan.task_id = str(task.id)
    db.commit()
    
    logger.info(f"Restarted scan {scan.id}, new task ID: {task.id}")
    
    return {
        "message": "Scan restarted successfully",
        "scan_id": scan.id,
        "task_id": str(task.id)
    }

@router.delete("/{scan_id}")
async def delete_scan(scan_id: int, db: Session = Depends(get_db)):
    """
    Delete a scan and its results
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Cancel task if running
    if scan.task_id and scan.status == ScanStatus.PROCESSING:
        try:
            from app.tasks.celery_app import celery_app
            celery_app.control.revoke(scan.task_id, terminate=True)
        except:
            pass
    
    db.delete(scan)
    db.commit()
    
    logger.info(f"Deleted scan {scan_id}")
    
    return {"message": "Scan deleted successfully"}

@router.post("/quick")
async def quick_scan(
    background_tasks: BackgroundTasks,
    target: str = Query(..., description="Target domain or IP")
):
    """
    Run a quick scan without saving to database
    """
    try:
        # Validate target
        if not target:
            raise HTTPException(status_code=400, detail="Target is required")
        
        # Start quick scan task
        task = quick_scan_task.delay(target)
        
        logger.info(f"Started quick scan for {target}, task ID: {task.id}")
        
        return {
            "message": "Quick scan started",
            "target": target,
            "task_id": str(task.id)
        }
        
    except Exception as e:
        logger.error(f"Quick scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recon")
async def reconnaissance(
    background_tasks: BackgroundTasks,
    target: str = Query(..., description="Target domain")
):
    """
    Run reconnaissance only
    """
    try:
        if not target:
            raise HTTPException(status_code=400, detail="Target is required")
        
        # Start recon task
        task = recon_task.delay(target)
        
        logger.info(f"Started reconnaissance for {target}, task ID: {task.id}")
        
        return {
            "message": "Reconnaissance started",
            "target": target,
            "task_id": str(task.id)
        }
        
    except Exception as e:
        logger.error(f"Reconnaissance failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task/{task_id}")
async def get_task_result(task_id: str):
    """
    Get the status and result of a Celery task
    """
    try:
        status = get_task_status(task_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/summary")
async def get_scan_statistics(db: Session = Depends(get_db)):
    """
    Get overall scan statistics
    """
    total_scans = db.query(Scan).count()
    completed_scans = db.query(Scan).filter(Scan.status == ScanStatus.COMPLETED).count()
    failed_scans = db.query(Scan).filter(Scan.status == ScanStatus.FAILED).count()
    processing_scans = db.query(Scan).filter(Scan.status == ScanStatus.PROCESSING).count()
    
    # Calculate average risk score
    from sqlalchemy import func
    avg_risk = db.query(func.avg(Scan.risk_score)).filter(
        Scan.status == ScanStatus.COMPLETED,
        Scan.risk_score.isnot(None)
    ).scalar() or 0
    
    # Total vulnerabilities found
    total_vulns = db.query(func.sum(Scan.vulnerability_count)).filter(
        Scan.status == ScanStatus.COMPLETED
    ).scalar() or 0
    
    return {
        "total_scans": total_scans,
        "completed_scans": completed_scans,
        "failed_scans": failed_scans,
        "processing_scans": processing_scans,
        "average_risk_score": round(avg_risk, 2),
        "total_vulnerabilities_found": total_vulns,
        "success_rate": round((completed_scans / total_scans * 100) if total_scans > 0 else 0, 2)
    }

@router.get("/recent")
async def get_recent_scans(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get most recent scans
    """
    scans = db.query(Scan).order_by(Scan.created_at.desc()).limit(limit).all()
    
    return [
        {
            "id": scan.id,
            "target": scan.target,
            "status": scan.status.value,
            "risk_score": scan.risk_score,
            "vulnerability_count": scan.vulnerability_count,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None
        }
        for scan in scans
    ]

@router.get("/high-risk")
async def get_high_risk_targets(
    threshold: int = Query(70, ge=0, le=100),
    db: Session = Depends(get_db)
):
    """
    Get targets with high risk scores
    """
    scans = db.query(Scan).filter(
        Scan.status == ScanStatus.COMPLETED,
        Scan.risk_score >= threshold
    ).order_by(Scan.risk_score.desc()).all()
    
    return [
        {
            "id": scan.id,
            "target": scan.target,
            "risk_score": scan.risk_score,
            "vulnerability_count": scan.vulnerability_count,
            "critical_findings": _extract_critical_count(scan),
            "scanned_at": scan.completed_at.isoformat() if scan.completed_at else None
        }
        for scan in scans
    ]

# Helper functions
def _count_by_severity(vulnerabilities: List[Dict]) -> Dict[str, int]:
    """Count vulnerabilities by severity"""
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for vuln in vulnerabilities:
        severity = vuln.get("severity", "INFO").upper()
        if severity in counts:
            counts[severity] += 1
    return counts

def _extract_critical_count(scan: Scan) -> int:
    """Extract critical vulnerability count from scan"""
    if not scan.summary:
        return 0
    return scan.summary.get("critical_count", 0)