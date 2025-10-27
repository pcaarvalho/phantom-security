from abc import ABC, abstractmethod
from typing import Dict, List, Any
import asyncio
import time

class BaseScanner(ABC):
    def __init__(self, target: str):
        self.target = target
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    @abstractmethod
    async def scan(self) -> Dict[str, Any]:
        pass
    
    def get_scan_duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def validate_target(self) -> bool:
        """Basic target validation"""
        if not self.target or len(self.target.strip()) == 0:
            return False
        
        target = self.target.strip()
        
        # Remove protocol if present
        if target.startswith(('http://', 'https://')):
            target = target.split('://', 1)[1]
        
        # Basic domain/IP validation
        parts = target.split('.')
        if len(parts) < 2:
            return False
        
        return True