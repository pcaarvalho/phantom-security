from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Float
from sqlalchemy.sql import func
from app.database import Base
from enum import Enum

class ScanStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Scan(Base):
    __tablename__ = "scans"
    
    id = Column(Integer, primary_key=True, index=True)
    target = Column(String, nullable=False, index=True)
    status = Column(String, default=ScanStatus.PENDING, nullable=False)
    
    # Scan results
    scan_results = Column(JSON)
    ai_analysis = Column(JSON)
    vulnerabilities = Column(JSON)
    
    # Metrics
    risk_score = Column(Float, default=0.0)
    vulnerability_count = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)
    
    # Metadata
    scan_type = Column(String, default="full")
    error_message = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())