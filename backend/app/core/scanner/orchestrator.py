"""
PHANTOM Brain Orchestrator - The core engine that coordinates all security scans
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

from app.core.scanner.port_scanner import PortScanner
from app.core.scanner.web_scanner import WebScanner
from app.core.scanner.vulnerability_scanner import VulnerabilityScanner
from app.core.scanner.recon_engine import ReconEngine
from app.core.ai.analyzer import AIThreatAnalyzer
from app.core.ai.exploit_generator import ExploitGenerator
from app.config import settings

# Import WebSocket manager for real-time updates
try:
    from app.websocket.manager import ws_manager
    WEBSOCKET_ENABLED = True
except ImportError:
    WEBSOCKET_ENABLED = False
    ws_manager = None

# Import notification service
try:
    from app.notifications.service import notification_service
    NOTIFICATIONS_ENABLED = True
except ImportError:
    NOTIFICATIONS_ENABLED = False
    notification_service = None

logger = logging.getLogger(__name__)

class PhantomBrain:
    """
    The central orchestrator that coordinates all security scanning operations
    """
    
    def __init__(self):
        self.port_scanner = None
        self.web_scanner = None
        self.vuln_scanner = None
        self.recon_engine = None
        self.ai_analyzer = AIThreatAnalyzer()
        self.exploit_gen = ExploitGenerator()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.scan_id = None
        self.target = None
        self.start_time = None
        self.end_time = None
        self.status = "idle"
        self.progress = 0
        self.current_phase = ""
        self.results = {}
        
    async def initialize_scan(self, target: str, scan_id: str, options: Dict = None) -> None:
        """Initialize a new scan with the given target"""
        self.target = target
        self.scan_id = scan_id
        self.start_time = datetime.now()
        self.status = "initializing"
        self.progress = 0
        self.results = {
            "scan_id": scan_id,
            "target": target,
            "start_time": self.start_time.isoformat(),
            "options": options or {},
            "phases": {}
        }
        
        # Initialize scanners
        self.port_scanner = PortScanner(target)
        self.web_scanner = WebScanner(target)
        self.vuln_scanner = VulnerabilityScanner(target)
        self.recon_engine = ReconEngine(target)
        
        logger.info(f"[PHANTOM] Initialized scan {scan_id} for target {target}")
        
    async def execute_full_scan(self, target: str, scan_id: str, options: Dict = None) -> Dict:
        """
        Execute a comprehensive security scan on the target
        """
        try:
            await self.initialize_scan(target, scan_id, options)
            self.status = "scanning"
            
            # Send scan started notification
            if WEBSOCKET_ENABLED and ws_manager:
                await ws_manager.send_scan_started(scan_id, target)
            
            # Send email/webhook notification
            if NOTIFICATIONS_ENABLED and notification_service:
                await notification_service.notify_scan_started(scan_id, target)
            
            # Phase 1: Reconnaissance (15% of progress)
            await self._update_progress(0, "Starting reconnaissance...")
            recon_data = await self._execute_phase(
                "reconnaissance",
                self._run_reconnaissance,
                progress_weight=15
            )
            
            # Phase 2: Port Scanning (20% of progress)
            await self._update_progress(15, "Scanning ports and services...")
            port_data = await self._execute_phase(
                "port_scan",
                self._run_port_scan,
                progress_weight=20
            )
            
            # Phase 3: Web Scanning (20% of progress)
            await self._update_progress(35, "Analyzing web application...")
            web_data = await self._execute_phase(
                "web_scan",
                self._run_web_scan,
                progress_weight=20
            )
            
            # Phase 4: Vulnerability Detection (25% of progress)
            await self._update_progress(55, "Detecting vulnerabilities...")
            vuln_data = await self._execute_phase(
                "vulnerability_scan",
                self._run_vulnerability_scan,
                progress_weight=25
            )
            
            # Phase 5: AI Analysis (15% of progress)
            await self._update_progress(80, "Analyzing with AI...")
            ai_analysis = await self._execute_phase(
                "ai_analysis",
                self._run_ai_analysis,
                progress_weight=15
            )
            
            # Phase 6: Exploit Generation (5% of progress)
            await self._update_progress(95, "Generating exploit scenarios...")
            exploits = await self._execute_phase(
                "exploit_generation",
                self._run_exploit_generation,
                progress_weight=5,
                data={"vulnerabilities": vuln_data.get("vulnerabilities", [])}
            )
            
            # Finalize results
            await self._finalize_scan()
            
            # Send scan completed notification
            if WEBSOCKET_ENABLED and ws_manager:
                await ws_manager.send_scan_completed(scan_id, self.results)
            
            # Send completion notification via email/webhook
            if NOTIFICATIONS_ENABLED and notification_service:
                risk_score = self.results.get("risk_score", 0)
                vuln_count = self.results.get("vulnerability_count", 0)
                critical_count = len(self.results.get("critical_findings", []))
                await notification_service.notify_scan_completed(
                    scan_id, self.target, risk_score, vuln_count, critical_count
                )
            
            return self.results
            
        except Exception as e:
            logger.error(f"[PHANTOM] Scan failed: {str(e)}")
            self.status = "failed"
            self.results["error"] = str(e)
            self.results["status"] = "failed"
            
            # Send scan failed notification
            if WEBSOCKET_ENABLED and ws_manager:
                await ws_manager.send_scan_failed(scan_id, str(e))
            
            return self.results
            
    async def _execute_phase(self, phase_name: str, phase_func: callable, 
                           progress_weight: int = 10, data: Dict = None) -> Dict:
        """Execute a single scan phase"""
        try:
            self.current_phase = phase_name
            logger.info(f"[PHANTOM] Starting phase: {phase_name}")
            
            # Execute the phase
            if data:
                result = await phase_func(data)
            else:
                result = await phase_func()
            
            # Store results
            self.results["phases"][phase_name] = {
                "status": "completed",
                "data": result,
                "timestamp": datetime.now().isoformat()
            }
            
            # Update progress
            self.progress = min(100, self.progress + progress_weight)
            
            logger.info(f"[PHANTOM] Completed phase: {phase_name}")
            return result
            
        except Exception as e:
            logger.error(f"[PHANTOM] Phase {phase_name} failed: {str(e)}")
            self.results["phases"][phase_name] = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            return {}
            
    async def _run_reconnaissance(self) -> Dict:
        """Run reconnaissance phase"""
        return await self.recon_engine.gather_intel()
        
    async def _run_port_scan(self) -> Dict:
        """Run port scanning phase"""
        return await self.port_scanner.scan()
        
    async def _run_web_scan(self) -> Dict:
        """Run web scanning phase"""
        return await self.web_scanner.scan()
        
    async def _run_vulnerability_scan(self) -> Dict:
        """Run vulnerability scanning phase"""
        # Enhance with discovered services and web findings
        services = self.results.get("phases", {}).get("port_scan", {}).get("data", {}).get("ports", [])
        web_findings = self.results.get("phases", {}).get("web_scan", {}).get("data", {})
        
        result = await self.vuln_scanner.scan_comprehensive(
            services=services,
            web_findings=web_findings
        )
        
        # Send critical vulnerability notifications
        if WEBSOCKET_ENABLED and ws_manager:
            vulnerabilities = result.get("vulnerabilities", [])
            for vuln in vulnerabilities:
                if vuln.get("severity", "").lower() in ["critical", "high"]:
                    await ws_manager.send_vulnerability(self.scan_id, vuln)
        
        # Send critical vulnerability alerts via email/webhook
        if NOTIFICATIONS_ENABLED and notification_service:
            vulnerabilities = result.get("vulnerabilities", [])
            for vuln in vulnerabilities:
                if vuln.get("severity", "").lower() == "critical":
                    await notification_service.notify_critical_vulnerability(
                        self.scan_id, self.target, vuln
                    )
        
        return result
        
    async def _run_ai_analysis(self) -> Dict:
        """Run AI analysis on all collected data"""
        # Aggregate all scan data for AI analysis
        scan_data = {
            "target": self.target,
            "recon": self.results.get("phases", {}).get("reconnaissance", {}).get("data", {}),
            "port_scan": self.results.get("phases", {}).get("port_scan", {}).get("data", {}),
            "web_scan": self.results.get("phases", {}).get("web_scan", {}).get("data", {}),
            "nuclei_scan": self.results.get("phases", {}).get("vulnerability_scan", {}).get("data", {}),
            "dns_records": self.results.get("phases", {}).get("reconnaissance", {}).get("data", {}).get("dns", {})
        }
        
        return await self.ai_analyzer.analyze_scan_results(scan_data)
        
    async def _run_exploit_generation(self, data: Dict) -> Dict:
        """Generate potential exploits for discovered vulnerabilities"""
        vulnerabilities = data.get("vulnerabilities", [])
        
        if not vulnerabilities:
            return {"exploits": [], "message": "No vulnerabilities to exploit"}
            
        # Select top vulnerabilities for exploit generation
        critical_vulns = [v for v in vulnerabilities if v.get("severity", "").lower() in ["critical", "high"]][:5]
        
        if not critical_vulns:
            critical_vulns = vulnerabilities[:3]
            
        return await self.exploit_gen.generate_exploits(critical_vulns)
        
    async def _update_progress(self, progress: int, message: str) -> None:
        """Update scan progress and send WebSocket event"""
        self.progress = progress
        self.current_phase = message
        logger.info(f"[PHANTOM] Progress: {progress}% - {message}")
        
        # Send WebSocket update if available
        if WEBSOCKET_ENABLED and ws_manager:
            try:
                await ws_manager.send_progress(
                    self.scan_id,
                    progress,
                    self.current_phase,
                    message
                )
            except Exception as e:
                logger.warning(f"Failed to send WebSocket progress: {e}")
        
        
    async def _finalize_scan(self) -> None:
        """Finalize the scan and prepare results"""
        self.end_time = datetime.now()
        self.status = "completed"
        self.progress = 100
        
        # Calculate summary statistics
        summary = self._calculate_summary()
        
        self.results.update({
            "status": "completed",
            "end_time": self.end_time.isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "summary": summary,
            "risk_score": self._calculate_risk_score(),
            "vulnerability_count": self._count_vulnerabilities(),
            "critical_findings": self._extract_critical_findings()
        })
        
        logger.info(f"[PHANTOM] Scan {self.scan_id} completed successfully")
        
    def _calculate_summary(self) -> Dict:
        """Calculate scan summary statistics"""
        summary = {
            "total_ports_scanned": 0,
            "open_ports": 0,
            "vulnerabilities_found": 0,
            "critical_vulnerabilities": 0,
            "high_vulnerabilities": 0,
            "services_detected": 0,
            "subdomains_found": 0,
            "security_headers_missing": 0
        }
        
        # Extract statistics from scan phases
        if "port_scan" in self.results.get("phases", {}):
            port_data = self.results["phases"]["port_scan"].get("data", {})
            summary["open_ports"] = len(port_data.get("ports", []))
            summary["services_detected"] = len(set([p.get("service") for p in port_data.get("ports", [])]))
            
        if "vulnerability_scan" in self.results.get("phases", {}):
            vuln_data = self.results["phases"]["vulnerability_scan"].get("data", {})
            vulns = vuln_data.get("vulnerabilities", [])
            summary["vulnerabilities_found"] = len(vulns)
            summary["critical_vulnerabilities"] = len([v for v in vulns if v.get("severity", "").lower() == "critical"])
            summary["high_vulnerabilities"] = len([v for v in vulns if v.get("severity", "").lower() == "high"])
            
        if "reconnaissance" in self.results.get("phases", {}):
            recon_data = self.results["phases"]["reconnaissance"].get("data", {})
            summary["subdomains_found"] = len(recon_data.get("subdomains", []))
            
        if "web_scan" in self.results.get("phases", {}):
            web_data = self.results["phases"]["web_scan"].get("data", {})
            headers = web_data.get("security_headers", {})
            summary["security_headers_missing"] = len([h for h, present in headers.items() if not present])
            
        return summary
        
    def _calculate_risk_score(self) -> int:
        """Calculate overall risk score based on findings"""
        score = 0
        
        # Get AI risk score if available
        if "ai_analysis" in self.results.get("phases", {}):
            ai_data = self.results["phases"]["ai_analysis"].get("data", {})
            if "risk_score" in ai_data:
                return ai_data["risk_score"]
                
        # Fallback calculation
        summary = self.results.get("summary", {})
        
        # Critical vulnerabilities have highest impact
        score += summary.get("critical_vulnerabilities", 0) * 20
        score += summary.get("high_vulnerabilities", 0) * 10
        score += summary.get("vulnerabilities_found", 0) * 2
        
        # Open ports increase risk
        open_ports = summary.get("open_ports", 0)
        if open_ports > 20:
            score += 15
        elif open_ports > 10:
            score += 10
        elif open_ports > 5:
            score += 5
            
        # Missing security headers
        missing_headers = summary.get("security_headers_missing", 0)
        if missing_headers > 3:
            score += 10
            
        return min(100, score)
        
    def _count_vulnerabilities(self) -> int:
        """Count total vulnerabilities found"""
        if "vulnerability_scan" in self.results.get("phases", {}):
            vuln_data = self.results["phases"]["vulnerability_scan"].get("data", {})
            return len(vuln_data.get("vulnerabilities", []))
        return 0
        
    def _extract_critical_findings(self) -> List[Dict]:
        """Extract the most critical findings from the scan"""
        findings = []
        
        # Get critical vulnerabilities
        if "vulnerability_scan" in self.results.get("phases", {}):
            vuln_data = self.results["phases"]["vulnerability_scan"].get("data", {})
            vulns = vuln_data.get("vulnerabilities", [])
            critical_vulns = [v for v in vulns if v.get("severity", "").lower() in ["critical", "high"]]
            findings.extend(critical_vulns[:5])
            
        # Get AI-identified critical findings
        if "ai_analysis" in self.results.get("phases", {}):
            ai_data = self.results["phases"]["ai_analysis"].get("data", {})
            ai_findings = ai_data.get("critical_findings", [])
            findings.extend(ai_findings[:3])
            
        return findings[:10]  # Return top 10 critical findings
        
    async def get_scan_status(self) -> Dict:
        """Get current scan status"""
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "status": self.status,
            "progress": self.progress,
            "current_phase": self.current_phase,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "duration": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }