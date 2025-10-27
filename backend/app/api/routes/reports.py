"""
Report generation API routes
"""
from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.orm import Session
import json
import io
from typing import Dict, Any

from app.database import get_db
from app.models.scan import Scan, ScanStatus
from app.core.reports.pdf_generator import ReportGenerator
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{scan_id}/pdf")
async def get_pdf_report(scan_id: int, db: Session = Depends(get_db)):
    """
    Generate and download PDF report for a completed scan
    """
    try:
        # Get scan record
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan.status != ScanStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Scan must be completed to generate report")
        
        if not scan.scan_results:
            raise HTTPException(status_code=400, detail="No scan results available for report generation")
        
        # Prepare scan data for report
        scan_data = {
            "id": scan.id,
            "target": scan.target,
            "status": scan.status.value,
            "scan_type": scan.scan_type,
            "risk_score": scan.risk_score or 0,
            "vulnerability_count": scan.vulnerability_count or 0,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "started_at": scan.started_at.isoformat() if scan.started_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
            "scan_results": scan.scan_results,
            "ai_analysis": scan.ai_analysis or {},
            "summary": scan.summary or {}
        }
        
        # Generate PDF report
        report_generator = ReportGenerator()
        pdf_data = await report_generator.generate_pdf_report(scan_data)
        
        # Create filename
        target_clean = scan.target.replace("://", "_").replace("/", "_").replace(".", "_")
        filename = f"phantom_security_report_{target_clean}_{scan_id}.pdf"
        
        # Return PDF as response
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/pdf"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to generate PDF report for scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.get("/{scan_id}/json")
async def get_json_report(scan_id: int, db: Session = Depends(get_db)):
    """
    Get scan results in JSON format
    """
    try:
        # Get scan record
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan.status != ScanStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Scan must be completed")
        
        # Return comprehensive JSON report
        return {
            "scan_info": {
                "id": scan.id,
                "target": scan.target,
                "status": scan.status.value,
                "scan_type": scan.scan_type,
                "risk_score": scan.risk_score,
                "vulnerability_count": scan.vulnerability_count,
                "created_at": scan.created_at.isoformat() if scan.created_at else None,
                "started_at": scan.started_at.isoformat() if scan.started_at else None,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None
            },
            "scan_results": scan.scan_results or {},
            "ai_analysis": scan.ai_analysis or {},
            "summary": scan.summary or {},
            "generated_at": scan.completed_at.isoformat() if scan.completed_at else None
        }
        
    except Exception as e:
        logger.error(f"Failed to generate JSON report for scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{scan_id}/summary")
async def get_report_summary(scan_id: int, db: Session = Depends(get_db)):
    """
    Get executive summary of scan results
    """
    try:
        # Get scan record
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan.status != ScanStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Scan must be completed")
        
        # Extract key information
        ai_analysis = scan.ai_analysis or {}
        scan_results = scan.scan_results or {}
        summary = scan.summary or {}
        
        # Get vulnerabilities
        vulnerabilities = []
        if scan_results and 'phases' in scan_results:
            phases = scan_results['phases']
            vuln_phase = phases.get('vulnerability_scan', {}).get('data', {})
            vulnerabilities = vuln_phase.get('vulnerabilities', [])
        
        # Calculate severity breakdown
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'INFO': 0}
        for vuln in vulnerabilities:
            severity = vuln.get('severity', 'INFO').upper()
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        return {
            "scan_id": scan.id,
            "target": scan.target,
            "risk_score": scan.risk_score or 0,
            "risk_level": _get_risk_level(scan.risk_score or 0),
            "total_vulnerabilities": len(vulnerabilities),
            "severity_breakdown": severity_counts,
            "executive_summary": ai_analysis.get('executive_summary', ''),
            "key_findings": vulnerabilities[:5],  # Top 5 vulnerabilities
            "recommendations": ai_analysis.get('recommendations', [])[:5],  # Top 5 recommendations
            "scan_duration": scan_results.get('duration_seconds', 0),
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None
        }
        
    except Exception as e:
        logger.error(f"Failed to generate summary for scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{scan_id}/vulnerabilities/export")
async def export_vulnerabilities_csv(scan_id: int, db: Session = Depends(get_db)):
    """
    Export vulnerabilities as CSV file
    """
    try:
        import csv
        from io import StringIO
        
        # Get scan record
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan.status != ScanStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Scan must be completed")
        
        # Extract vulnerabilities
        vulnerabilities = []
        scan_results = scan.scan_results or {}
        if 'phases' in scan_results:
            phases = scan_results['phases']
            vuln_phase = phases.get('vulnerability_scan', {}).get('data', {})
            vulnerabilities = vuln_phase.get('vulnerabilities', [])
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'ID', 'Name', 'Severity', 'Location', 'Description', 
            'CVE', 'Impact', 'Remediation', 'References'
        ])
        
        # Data rows
        for i, vuln in enumerate(vulnerabilities, 1):
            writer.writerow([
                i,
                vuln.get('template_name', ''),
                vuln.get('severity', ''),
                vuln.get('matched_at', ''),
                (vuln.get('description', '') or '')[:200],  # Limit description length
                ', '.join(vuln.get('cve_id', [])),
                vuln.get('impact', ''),
                (vuln.get('remediation', '') or '')[:200],  # Limit remediation length
                ', '.join(vuln.get('reference', []))
            ])
        
        csv_data = output.getvalue()
        output.close()
        
        # Create filename
        target_clean = scan.target.replace("://", "_").replace("/", "_").replace(".", "_")
        filename = f"phantom_vulnerabilities_{target_clean}_{scan_id}.csv"
        
        return Response(
            content=csv_data.encode(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/csv"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to export vulnerabilities for scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
def _get_risk_level(risk_score: int) -> str:
    """Get risk level from score"""
    if risk_score >= 80:
        return "CRITICAL"
    elif risk_score >= 60:
        return "HIGH"
    elif risk_score >= 40:
        return "MEDIUM"
    elif risk_score >= 20:
        return "LOW"
    else:
        return "MINIMAL"