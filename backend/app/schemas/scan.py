from pydantic import BaseModel, validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum

class ScanStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ScanCreate(BaseModel):
    target: str
    scan_type: Optional[str] = "full"
    
    @validator('target')
    def validate_target(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Target cannot be empty')
        
        # Basic validation for domain/IP
        target = v.strip()
        if not target.replace('.', '').replace('-', '').replace('_', '').isalnum():
            # More sophisticated validation would go here
            pass
        return target

class ScanResponse(BaseModel):
    id: int
    target: str
    status: ScanStatus
    risk_score: Optional[float] = None
    vulnerability_count: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ScanDetails(ScanResponse):
    scan_results: Optional[Dict[str, Any]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    vulnerabilities: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    
class VulnerabilityInfo(BaseModel):
    title: str
    severity: str
    description: str
    exploitation_method: Optional[str] = None
    remediation: Optional[str] = None

class AIAnalysis(BaseModel):
    executive_summary: str
    critical_findings: List[VulnerabilityInfo]
    attack_narrative: str
    business_impact: str
    recommendations: List[str]
    risk_score: int