"""
Results aggregation and summary generation system
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import statistics
import re
from enum import Enum

logger = logging.getLogger(__name__)


class AggregationType(Enum):
    """Types of aggregation operations"""
    EXECUTIVE_SUMMARY = "executive_summary"
    TECHNICAL_SUMMARY = "technical_summary"
    VULNERABILITY_BREAKDOWN = "vulnerability_breakdown"
    RISK_ASSESSMENT = "risk_assessment"
    COMPLIANCE_SUMMARY = "compliance_summary"
    TIMELINE_ANALYSIS = "timeline_analysis"


@dataclass
class ScanSummary:
    """Comprehensive scan summary"""
    scan_id: str
    target: str
    scan_type: str
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    
    # High-level metrics
    overall_risk_score: float
    total_vulnerabilities: int
    critical_vulnerabilities: int
    high_vulnerabilities: int
    medium_vulnerabilities: int
    low_vulnerabilities: int
    
    # Discovery metrics
    open_ports: int
    detected_services: int
    discovered_subdomains: int
    web_technologies: int
    
    # Phase completion status
    phases_completed: List[str]
    phases_failed: List[str]
    
    # Key findings
    critical_findings: List[Dict[str, Any]]
    security_misconfigurations: List[Dict[str, Any]]
    exposed_services: List[Dict[str, Any]]
    
    # AI analysis
    ai_insights: Optional[str] = None
    business_impact: Optional[str] = None
    attack_scenarios: List[str] = field(default_factory=list)
    
    # Compliance
    compliance_issues: List[Dict[str, Any]] = field(default_factory=list)
    
    # Recommendations
    immediate_actions: List[str] = field(default_factory=list)
    short_term_actions: List[str] = field(default_factory=list)
    long_term_actions: List[str] = field(default_factory=list)


class ResultsAggregator:
    """Aggregates and summarizes scan results"""
    
    def __init__(self):
        self.vulnerability_categories = {
            "injection": ["sql injection", "command injection", "ldap injection", "xpath injection"],
            "broken_auth": ["authentication bypass", "session management", "weak credentials"],
            "sensitive_data": ["data exposure", "information disclosure", "privacy violation"],
            "xxe": ["xml external entity", "xxe"],
            "broken_access": ["privilege escalation", "authorization bypass", "idor"],
            "security_misconfig": ["default credentials", "misconfiguration", "debug enabled"],
            "xss": ["cross-site scripting", "reflected xss", "stored xss", "dom xss"],
            "insecure_deserial": ["deserialization", "unsafe deserialization"],
            "known_vulns": ["cve-", "known vulnerability", "outdated component"],
            "insufficient_logging": ["logging", "monitoring", "audit trail"]
        }
        
        self.severity_weights = {
            "critical": 10.0,
            "high": 7.0,
            "medium": 4.0,
            "low": 2.0,
            "info": 0.5
        }
    
    def aggregate_scan_results(self, scan_data: Dict[str, Any]) -> ScanSummary:
        """Create comprehensive summary from scan results"""
        
        # Extract basic information
        scan_id = scan_data.get("scan_id", "unknown")
        target = scan_data.get("target", "unknown")
        scan_type = scan_data.get("scan_type", "standard")
        
        # Parse timestamps
        start_time = self._parse_timestamp(scan_data.get("start_time"))
        end_time = self._parse_timestamp(scan_data.get("end_time"))
        duration_minutes = (end_time - start_time).total_seconds() / 60 if start_time and end_time else 0
        
        # Process phases
        phases = scan_data.get("phases", {})
        phases_completed = [name for name, phase in phases.items() if phase.get("status") == "completed"]
        phases_failed = [name for name, phase in phases.items() if phase.get("status") == "failed"]
        
        # Aggregate vulnerabilities
        vulnerability_stats = self._aggregate_vulnerabilities(scan_data)
        
        # Aggregate discovery data
        discovery_stats = self._aggregate_discovery_data(scan_data)
        
        # Extract critical findings
        critical_findings = self._extract_critical_findings(scan_data)
        
        # Generate risk score
        risk_score = self._calculate_overall_risk_score(scan_data, vulnerability_stats)
        
        # Extract AI insights
        ai_analysis = scan_data.get("phases", {}).get("ai_analysis", {}).get("data", {})
        ai_insights = ai_analysis.get("executive_summary")
        business_impact = ai_analysis.get("business_impact")
        attack_scenarios = ai_analysis.get("attack_narratives", [])
        if isinstance(attack_scenarios, str):
            attack_scenarios = [attack_scenarios]
        
        # Identify security misconfigurations
        security_misconfigs = self._identify_security_misconfigurations(scan_data)
        
        # Identify exposed services
        exposed_services = self._identify_exposed_services(scan_data)
        
        # Generate recommendations
        immediate_actions, short_term_actions, long_term_actions = self._generate_recommendations(
            scan_data, vulnerability_stats, critical_findings
        )
        
        # Check compliance issues
        compliance_issues = self._check_compliance_issues(scan_data)
        
        return ScanSummary(
            scan_id=scan_id,
            target=target,
            scan_type=scan_type,
            start_time=start_time or datetime.utcnow(),
            end_time=end_time or datetime.utcnow(),
            duration_minutes=duration_minutes,
            overall_risk_score=risk_score,
            total_vulnerabilities=vulnerability_stats["total"],
            critical_vulnerabilities=vulnerability_stats["critical"],
            high_vulnerabilities=vulnerability_stats["high"],
            medium_vulnerabilities=vulnerability_stats["medium"],
            low_vulnerabilities=vulnerability_stats["low"],
            open_ports=discovery_stats["open_ports"],
            detected_services=discovery_stats["services"],
            discovered_subdomains=discovery_stats["subdomains"],
            web_technologies=discovery_stats["technologies"],
            phases_completed=phases_completed,
            phases_failed=phases_failed,
            critical_findings=critical_findings,
            security_misconfigurations=security_misconfigs,
            exposed_services=exposed_services,
            ai_insights=ai_insights,
            business_impact=business_impact,
            attack_scenarios=attack_scenarios,
            compliance_issues=compliance_issues,
            immediate_actions=immediate_actions,
            short_term_actions=short_term_actions,
            long_term_actions=long_term_actions
        )
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string to datetime object"""
        if not timestamp_str:
            return None
        
        try:
            # Try multiple formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
            
            # If all else fails, try fromisoformat
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            
        except Exception as e:
            logger.warning(f"Could not parse timestamp {timestamp_str}: {e}")
            return None
    
    def _aggregate_vulnerabilities(self, scan_data: Dict[str, Any]) -> Dict[str, int]:
        """Aggregate vulnerability statistics"""
        stats = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        
        # Get vulnerabilities from different phases
        vuln_scan = scan_data.get("phases", {}).get("vulnerability_scan", {}).get("data", {})
        vulnerabilities = vuln_scan.get("vulnerabilities", [])
        
        # Also check web scan for web-specific vulns
        web_scan = scan_data.get("phases", {}).get("web_scan", {}).get("data", {})
        web_vulns = web_scan.get("vulnerabilities", [])
        vulnerabilities.extend(web_vulns)
        
        for vuln in vulnerabilities:
            severity = vuln.get("severity", "info").lower()
            stats["total"] += 1
            if severity in stats:
                stats[severity] += 1
        
        return stats
    
    def _aggregate_discovery_data(self, scan_data: Dict[str, Any]) -> Dict[str, int]:
        """Aggregate discovery statistics"""
        stats = {"open_ports": 0, "services": 0, "subdomains": 0, "technologies": 0}
        
        # Port scan data
        port_scan = scan_data.get("phases", {}).get("port_scan", {}).get("data", {})
        ports = port_scan.get("ports", [])
        stats["open_ports"] = len([p for p in ports if p.get("state") == "open"])
        stats["services"] = len(set(p.get("service", "unknown") for p in ports))
        
        # Reconnaissance data
        recon = scan_data.get("phases", {}).get("reconnaissance", {}).get("data", {})
        subdomains = recon.get("subdomains", [])
        stats["subdomains"] = len(subdomains)
        
        # Web scan data
        web_scan = scan_data.get("phases", {}).get("web_scan", {}).get("data", {})
        technologies = web_scan.get("technologies", [])
        stats["technologies"] = len(technologies)
        
        return stats
    
    def _extract_critical_findings(self, scan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract the most critical findings"""
        critical_findings = []
        
        # Get vulnerabilities
        vuln_scan = scan_data.get("phases", {}).get("vulnerability_scan", {}).get("data", {})
        vulnerabilities = vuln_scan.get("vulnerabilities", [])
        
        # Filter for critical and high severity
        for vuln in vulnerabilities:
            severity = vuln.get("severity", "").lower()
            if severity in ["critical", "high"]:
                critical_findings.append({
                    "name": vuln.get("name", "Unknown Vulnerability"),
                    "severity": severity,
                    "description": vuln.get("description", ""),
                    "affected_component": vuln.get("affected_component", ""),
                    "cve": vuln.get("cve", ""),
                    "cvss_score": vuln.get("cvss_score", 0)
                })
        
        # Sort by severity and CVSS score
        critical_findings.sort(key=lambda x: (
            0 if x["severity"] == "critical" else 1,
            -x.get("cvss_score", 0)
        ))
        
        return critical_findings[:10]  # Top 10 critical findings
    
    def _calculate_overall_risk_score(
        self, 
        scan_data: Dict[str, Any], 
        vuln_stats: Dict[str, int]
    ) -> float:
        """Calculate overall risk score based on findings"""
        
        # Base score from vulnerabilities (weighted by severity)
        vuln_score = (
            vuln_stats["critical"] * self.severity_weights["critical"] +
            vuln_stats["high"] * self.severity_weights["high"] +
            vuln_stats["medium"] * self.severity_weights["medium"] +
            vuln_stats["low"] * self.severity_weights["low"]
        )
        
        # Normalize to 0-100 scale (assuming max of 10 critical vulns as 100)
        max_possible_score = 10 * self.severity_weights["critical"]
        base_risk = min((vuln_score / max_possible_score) * 100, 100)
        
        # Adjust for exposure factors
        exposure_multiplier = 1.0
        
        # Check for external exposure
        port_scan = scan_data.get("phases", {}).get("port_scan", {}).get("data", {})
        ports = port_scan.get("ports", [])
        external_ports = [22, 23, 25, 53, 80, 110, 143, 443, 993, 995]
        
        exposed_services = [p for p in ports if p.get("port") in external_ports and p.get("state") == "open"]
        if exposed_services:
            exposure_multiplier *= 1.2
        
        # Check for web services
        web_scan = scan_data.get("phases", {}).get("web_scan", {}).get("data", {})
        if web_scan.get("web_server_detected"):
            exposure_multiplier *= 1.1
        
        # Check for SSL/TLS issues
        ssl_issues = web_scan.get("ssl_issues", [])
        if ssl_issues:
            exposure_multiplier *= 1.15
        
        # Apply AI risk assessment if available
        ai_analysis = scan_data.get("phases", {}).get("ai_analysis", {}).get("data", {})
        ai_risk_score = ai_analysis.get("risk_score")
        if ai_risk_score is not None:
            # Blend AI assessment with calculated score
            base_risk = (base_risk * 0.7) + (ai_risk_score * 0.3)
        
        final_score = min(base_risk * exposure_multiplier, 100.0)
        return round(final_score, 1)
    
    def _identify_security_misconfigurations(self, scan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify security misconfigurations"""
        misconfigs = []
        
        # Web security headers
        web_scan = scan_data.get("phases", {}).get("web_scan", {}).get("data", {})
        security_headers = web_scan.get("security_headers", {})
        
        missing_headers = [header for header, present in security_headers.items() if not present]
        for header in missing_headers:
            misconfigs.append({
                "type": "missing_security_header",
                "description": f"Missing security header: {header}",
                "severity": "medium",
                "recommendation": f"Implement {header} security header"
            })
        
        # SSL/TLS issues
        ssl_issues = web_scan.get("ssl_issues", [])
        for issue in ssl_issues:
            misconfigs.append({
                "type": "ssl_misconfiguration",
                "description": issue,
                "severity": "high",
                "recommendation": "Fix SSL/TLS configuration"
            })
        
        # Default credentials or common misconfigurations
        vulnerabilities = scan_data.get("phases", {}).get("vulnerability_scan", {}).get("data", {}).get("vulnerabilities", [])
        for vuln in vulnerabilities:
            vuln_name = vuln.get("name", "").lower()
            if any(keyword in vuln_name for keyword in ["default", "misconfiguration", "config"]):
                misconfigs.append({
                    "type": "configuration_issue",
                    "description": vuln.get("description", ""),
                    "severity": vuln.get("severity", "medium"),
                    "recommendation": "Review and secure configuration"
                })
        
        return misconfigs
    
    def _identify_exposed_services(self, scan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify exposed services that may pose risks"""
        exposed = []
        
        port_scan = scan_data.get("phases", {}).get("port_scan", {}).get("data", {})
        ports = port_scan.get("ports", [])
        
        # Define risky services
        risky_services = {
            21: {"name": "FTP", "risk": "high", "reason": "Unencrypted file transfer"},
            22: {"name": "SSH", "risk": "medium", "reason": "Remote access service"},
            23: {"name": "Telnet", "risk": "critical", "reason": "Unencrypted remote access"},
            25: {"name": "SMTP", "risk": "medium", "reason": "Email service"},
            53: {"name": "DNS", "risk": "low", "reason": "Domain name service"},
            80: {"name": "HTTP", "risk": "medium", "reason": "Unencrypted web service"},
            110: {"name": "POP3", "risk": "medium", "reason": "Unencrypted email retrieval"},
            135: {"name": "RPC", "risk": "high", "reason": "Windows RPC service"},
            139: {"name": "NetBIOS", "risk": "high", "reason": "Windows file sharing"},
            143: {"name": "IMAP", "risk": "medium", "reason": "Unencrypted email service"},
            443: {"name": "HTTPS", "risk": "low", "reason": "Encrypted web service"},
            445: {"name": "SMB", "risk": "high", "reason": "Windows file sharing"},
            993: {"name": "IMAPS", "risk": "low", "reason": "Encrypted email service"},
            995: {"name": "POP3S", "risk": "low", "reason": "Encrypted email retrieval"},
            1433: {"name": "MSSQL", "risk": "critical", "reason": "Database service"},
            3306: {"name": "MySQL", "risk": "critical", "reason": "Database service"},
            3389: {"name": "RDP", "risk": "high", "reason": "Remote desktop service"},
            5432: {"name": "PostgreSQL", "risk": "critical", "reason": "Database service"},
            6379: {"name": "Redis", "risk": "high", "reason": "In-memory database"},
            27017: {"name": "MongoDB", "risk": "critical", "reason": "NoSQL database"}
        }
        
        for port in ports:
            if port.get("state") == "open":
                port_num = port.get("port")
                service_info = risky_services.get(port_num)
                
                if service_info:
                    exposed.append({
                        "port": port_num,
                        "service": service_info["name"],
                        "detected_service": port.get("service", "unknown"),
                        "version": port.get("version", ""),
                        "risk_level": service_info["risk"],
                        "risk_reason": service_info["reason"],
                        "recommendation": f"Review necessity of exposing {service_info['name']} service"
                    })
        
        # Sort by risk level
        risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        exposed.sort(key=lambda x: risk_order.get(x["risk_level"], 4))
        
        return exposed
    
    def _generate_recommendations(
        self, 
        scan_data: Dict[str, Any], 
        vuln_stats: Dict[str, int], 
        critical_findings: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], List[str]]:
        """Generate prioritized recommendations"""
        
        immediate = []
        short_term = []
        long_term = []
        
        # Immediate actions (critical issues)
        if vuln_stats["critical"] > 0:
            immediate.append(f"Address {vuln_stats['critical']} critical vulnerabilities immediately")
        
        for finding in critical_findings[:3]:  # Top 3 critical
            if finding["severity"] == "critical":
                immediate.append(f"Fix critical vulnerability: {finding['name']}")
        
        # Check for exposed databases
        port_scan = scan_data.get("phases", {}).get("port_scan", {}).get("data", {})
        ports = port_scan.get("ports", [])
        db_ports = [1433, 3306, 5432, 27017]
        exposed_dbs = [p for p in ports if p.get("port") in db_ports and p.get("state") == "open"]
        
        if exposed_dbs:
            immediate.append("Secure or close exposed database services")
        
        # Short-term actions
        if vuln_stats["high"] > 0:
            short_term.append(f"Remediate {vuln_stats['high']} high-severity vulnerabilities")
        
        # Check for missing security headers
        web_scan = scan_data.get("phases", {}).get("web_scan", {}).get("data", {})
        security_headers = web_scan.get("security_headers", {})
        missing_critical_headers = [
            header for header in ["X-Frame-Options", "Content-Security-Policy", "X-XSS-Protection"] 
            if not security_headers.get(header, True)
        ]
        
        if missing_critical_headers:
            short_term.append("Implement missing critical security headers")
        
        # SSL/TLS issues
        ssl_issues = web_scan.get("ssl_issues", [])
        if ssl_issues:
            short_term.append("Address SSL/TLS configuration issues")
        
        # Long-term actions
        if vuln_stats["medium"] > 5:
            long_term.append(f"Plan remediation for {vuln_stats['medium']} medium-severity issues")
        
        long_term.append("Implement regular vulnerability scanning")
        long_term.append("Establish security monitoring and incident response procedures")
        
        # Add AI recommendations if available
        ai_analysis = scan_data.get("phases", {}).get("ai_analysis", {}).get("data", {})
        ai_recommendations = ai_analysis.get("recommendations", [])
        
        if ai_recommendations:
            # Categorize AI recommendations
            for rec in ai_recommendations[:5]:  # Top 5 AI recommendations
                if any(keyword in rec.lower() for keyword in ["immediate", "critical", "urgent"]):
                    immediate.append(f"AI Recommendation: {rec}")
                elif any(keyword in rec.lower() for keyword in ["short", "soon", "priority"]):
                    short_term.append(f"AI Recommendation: {rec}")
                else:
                    long_term.append(f"AI Recommendation: {rec}")
        
        return immediate[:5], short_term[:7], long_term[:5]  # Limit recommendations
    
    def _check_compliance_issues(self, scan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for compliance-related issues"""
        compliance_issues = []
        
        # PCI DSS checks
        vulnerabilities = scan_data.get("phases", {}).get("vulnerability_scan", {}).get("data", {}).get("vulnerabilities", [])
        for vuln in vulnerabilities:
            vuln_name = vuln.get("name", "").lower()
            if any(keyword in vuln_name for keyword in ["pci", "payment", "card"]):
                compliance_issues.append({
                    "standard": "PCI DSS",
                    "issue": vuln.get("description", ""),
                    "severity": vuln.get("severity", "medium"),
                    "requirement": "Various PCI DSS requirements"
                })
        
        # GDPR/Privacy checks
        web_scan = scan_data.get("phases", {}).get("web_scan", {}).get("data", {})
        if not web_scan.get("privacy_policy_detected"):
            compliance_issues.append({
                "standard": "GDPR",
                "issue": "No privacy policy detected",
                "severity": "medium",
                "requirement": "Art. 13 - Information to be provided"
            })
        
        # SSL/TLS compliance
        ssl_issues = web_scan.get("ssl_issues", [])
        if ssl_issues:
            compliance_issues.append({
                "standard": "Various compliance standards",
                "issue": "SSL/TLS configuration issues detected",
                "severity": "high",
                "requirement": "Encryption in transit requirements"
            })
        
        return compliance_issues
    
    def generate_executive_summary(self, summary: ScanSummary) -> str:
        """Generate executive summary text"""
        
        # Risk level determination
        if summary.overall_risk_score >= 80:
            risk_level = "CRITICAL"
            risk_description = "immediate attention and remediation required"
        elif summary.overall_risk_score >= 60:
            risk_level = "HIGH"
            risk_description = "significant security concerns that should be addressed promptly"
        elif summary.overall_risk_score >= 40:
            risk_level = "MEDIUM"
            risk_description = "moderate security issues requiring attention"
        elif summary.overall_risk_score >= 20:
            risk_level = "LOW"
            risk_description = "minor security concerns with low impact"
        else:
            risk_level = "MINIMAL"
            risk_description = "very low security risk with minimal concerns"
        
        # Key statistics
        total_issues = summary.total_vulnerabilities
        critical_count = summary.critical_vulnerabilities
        high_count = summary.high_vulnerabilities
        
        # Build executive summary
        summary_text = f"""
PHANTOM Security Assessment - Executive Summary

Target: {summary.target}
Scan Type: {summary.scan_type.title()}
Assessment Date: {summary.start_time.strftime('%B %d, %Y')}
Duration: {summary.duration_minutes:.1f} minutes

OVERALL RISK RATING: {risk_level} ({summary.overall_risk_score}/100)

This security assessment reveals {risk_description}. A total of {total_issues} security issues were identified during the comprehensive scan.

KEY FINDINGS:
• {critical_count} Critical vulnerabilities requiring immediate action
• {high_count} High-severity issues needing prompt remediation  
• {summary.medium_vulnerabilities} Medium-severity concerns for planned remediation
• {summary.open_ports} network services exposed
• {summary.discovered_subdomains} subdomains discovered
• {len(summary.security_misconfigurations)} security misconfigurations identified

IMMEDIATE PRIORITY ACTIONS:
"""
        
        for i, action in enumerate(summary.immediate_actions[:3], 1):
            summary_text += f"{i}. {action}\n"
        
        if summary.business_impact:
            summary_text += f"\nBUSINESS IMPACT:\n{summary.business_impact}\n"
        
        summary_text += f"\nThis assessment provides a comprehensive view of the current security posture and includes detailed technical findings, remediation guidance, and strategic recommendations for improving the overall security stance."
        
        return summary_text.strip()
    
    def generate_comparison_report(self, summaries: List[ScanSummary]) -> Dict[str, Any]:
        """Generate comparison report across multiple scans"""
        if not summaries:
            return {"error": "No scan summaries provided"}
        
        # Sort by scan date
        summaries.sort(key=lambda x: x.start_time)
        
        # Calculate trends
        risk_scores = [s.overall_risk_score for s in summaries]
        vuln_counts = [s.total_vulnerabilities for s in summaries]
        critical_counts = [s.critical_vulnerabilities for s in summaries]
        
        # Determine trends
        risk_trend = "stable"
        if len(risk_scores) >= 2:
            if risk_scores[-1] > risk_scores[0] + 5:
                risk_trend = "increasing"
            elif risk_scores[-1] < risk_scores[0] - 5:
                risk_trend = "decreasing"
        
        return {
            "scan_count": len(summaries),
            "date_range": {
                "from": summaries[0].start_time.isoformat(),
                "to": summaries[-1].start_time.isoformat()
            },
            "risk_score_trend": {
                "current": risk_scores[-1],
                "previous": risk_scores[0] if len(risk_scores) > 1 else risk_scores[-1],
                "trend": risk_trend,
                "change": risk_scores[-1] - risk_scores[0] if len(risk_scores) > 1 else 0
            },
            "vulnerability_trends": {
                "total_vulnerabilities": {
                    "current": vuln_counts[-1],
                    "average": statistics.mean(vuln_counts),
                    "max": max(vuln_counts),
                    "min": min(vuln_counts)
                },
                "critical_vulnerabilities": {
                    "current": critical_counts[-1],
                    "average": statistics.mean(critical_counts),
                    "max": max(critical_counts),
                    "min": min(critical_counts)
                }
            },
            "targets_scanned": list(set(s.target for s in summaries)),
            "scan_types_used": list(set(s.scan_type for s in summaries)),
            "most_common_findings": self._get_common_findings(summaries),
            "improvement_areas": self._identify_improvement_areas(summaries)
        }
    
    def _get_common_findings(self, summaries: List[ScanSummary]) -> List[Dict[str, Any]]:
        """Identify most common findings across scans"""
        finding_counter = Counter()
        
        for summary in summaries:
            for finding in summary.critical_findings:
                finding_name = finding.get("name", "Unknown")
                finding_counter[finding_name] += 1
        
        common_findings = []
        for finding_name, count in finding_counter.most_common(5):
            common_findings.append({
                "finding": finding_name,
                "occurrence_count": count,
                "percentage": (count / len(summaries)) * 100
            })
        
        return common_findings
    
    def _identify_improvement_areas(self, summaries: List[ScanSummary]) -> List[str]:
        """Identify areas for security improvement based on scan history"""
        improvements = []
        
        # Check if critical vulnerabilities persist
        if any(s.critical_vulnerabilities > 0 for s in summaries[-3:]):  # Last 3 scans
            improvements.append("Critical vulnerabilities continue to be discovered - strengthen vulnerability management")
        
        # Check risk score trends
        recent_scores = [s.overall_risk_score for s in summaries[-3:]]
        if len(recent_scores) >= 2 and recent_scores[-1] > recent_scores[0]:
            improvements.append("Risk score trending upward - review security controls effectiveness")
        
        # Check for recurring misconfigurations
        common_misconfigs = []
        for summary in summaries:
            for misconfig in summary.security_misconfigurations:
                common_misconfigs.append(misconfig.get("type"))
        
        if len(set(common_misconfigs)) < len(common_misconfigs) * 0.5:  # Many duplicates
            improvements.append("Recurring security misconfigurations - implement configuration management")
        
        return improvements


# Global results aggregator instance
results_aggregator = ResultsAggregator()