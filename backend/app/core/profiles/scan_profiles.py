"""
Scan profiles for different use cases and scenarios
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ScanType(Enum):
    """Scan type enumeration"""
    QUICK = "quick"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    STEALTH = "stealth"
    COMPLIANCE = "compliance"
    TARGETED = "targeted"


class PhaseType(Enum):
    """Scan phase types"""
    RECONNAISSANCE = "reconnaissance"
    PORT_SCAN = "port_scan"
    WEB_SCAN = "web_scan"
    VULNERABILITY_SCAN = "vulnerability_scan"
    AI_ANALYSIS = "ai_analysis"
    EXPLOIT_GENERATION = "exploit_generation"


@dataclass
class PhaseConfig:
    """Configuration for a specific scan phase"""
    enabled: bool = True
    timeout_seconds: int = 300
    max_retries: int = 2
    parallel_execution: bool = True
    priority: int = 1  # 1 = highest priority
    
    # Phase-specific parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Dependencies - phases that must complete first
    dependencies: Set[PhaseType] = field(default_factory=set)


@dataclass
class ScanProfile:
    """Complete scan profile definition"""
    name: str
    description: str
    scan_type: ScanType
    estimated_duration_minutes: int
    
    # Phase configurations
    phases: Dict[PhaseType, PhaseConfig] = field(default_factory=dict)
    
    # Global settings
    max_concurrent_phases: int = 3
    overall_timeout_minutes: int = 60
    enable_caching: bool = True
    enable_ai_analysis: bool = True
    
    # Resource limits
    cpu_intensive_limit: int = 2
    network_request_limit: int = 100
    memory_limit_mb: int = 512
    
    # Output settings
    generate_report: bool = True
    include_exploits: bool = False
    detailed_logging: bool = False


class ScanProfileManager:
    """Manages scan profiles and their configurations"""
    
    def __init__(self):
        self.profiles: Dict[ScanType, ScanProfile] = {}
        self._initialize_default_profiles()
    
    def _initialize_default_profiles(self):
        """Initialize default scan profiles"""
        
        # QUICK Profile - Fast reconnaissance and basic checks
        quick_profile = ScanProfile(
            name="Quick Scan",
            description="Fast reconnaissance and basic vulnerability checks",
            scan_type=ScanType.QUICK,
            estimated_duration_minutes=5,
            max_concurrent_phases=2,
            overall_timeout_minutes=10,
            enable_caching=True,
            enable_ai_analysis=False,  # Skip AI for speed
            cpu_intensive_limit=1,
            network_request_limit=50,
            memory_limit_mb=256,
            include_exploits=False,
            phases={
                PhaseType.RECONNAISSANCE: PhaseConfig(
                    enabled=True,
                    timeout_seconds=60,
                    max_retries=1,
                    priority=1,
                    parameters={
                        "dns_enumeration": True,
                        "subdomain_discovery": False,  # Skip for speed
                        "certificate_transparency": False,
                        "whois_lookup": False,
                        "max_subdomains": 5
                    }
                ),
                PhaseType.PORT_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=120,
                    max_retries=1,
                    priority=2,
                    dependencies={PhaseType.RECONNAISSANCE},
                    parameters={
                        "port_range": "1-1000",  # Limited range
                        "scan_type": "syn",
                        "timing": "aggressive",
                        "service_detection": False
                    }
                ),
                PhaseType.WEB_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=90,
                    max_retries=1,
                    priority=3,
                    dependencies={PhaseType.PORT_SCAN},
                    parameters={
                        "check_ssl": True,
                        "check_headers": True,
                        "directory_bruteforce": False,
                        "technology_detection": True,
                        "max_paths": 10
                    }
                ),
                PhaseType.VULNERABILITY_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=180,
                    max_retries=1,
                    priority=4,
                    dependencies={PhaseType.WEB_SCAN, PhaseType.PORT_SCAN},
                    parameters={
                        "nuclei_templates": ["cves/critical", "exposures/configs"],
                        "custom_payloads": False,
                        "deep_scan": False
                    }
                ),
                PhaseType.AI_ANALYSIS: PhaseConfig(enabled=False),
                PhaseType.EXPLOIT_GENERATION: PhaseConfig(enabled=False)
            }
        )
        
        # STANDARD Profile - Balanced speed and coverage
        standard_profile = ScanProfile(
            name="Standard Scan",
            description="Balanced security assessment with good coverage",
            scan_type=ScanType.STANDARD,
            estimated_duration_minutes=15,
            max_concurrent_phases=3,
            overall_timeout_minutes=30,
            enable_caching=True,
            enable_ai_analysis=True,
            cpu_intensive_limit=2,
            network_request_limit=200,
            memory_limit_mb=512,
            include_exploits=False,
            phases={
                PhaseType.RECONNAISSANCE: PhaseConfig(
                    enabled=True,
                    timeout_seconds=180,
                    max_retries=2,
                    priority=1,
                    parameters={
                        "dns_enumeration": True,
                        "subdomain_discovery": True,
                        "certificate_transparency": True,
                        "whois_lookup": True,
                        "max_subdomains": 20,
                        "passive_recon": True
                    }
                ),
                PhaseType.PORT_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=300,
                    max_retries=2,
                    priority=2,
                    dependencies={PhaseType.RECONNAISSANCE},
                    parameters={
                        "port_range": "1-10000",
                        "scan_type": "syn",
                        "timing": "normal",
                        "service_detection": True,
                        "version_detection": True
                    }
                ),
                PhaseType.WEB_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=240,
                    max_retries=2,
                    priority=3,
                    parallel_execution=True,
                    dependencies={PhaseType.PORT_SCAN},
                    parameters={
                        "check_ssl": True,
                        "check_headers": True,
                        "directory_bruteforce": True,
                        "technology_detection": True,
                        "max_paths": 50,
                        "check_robots_txt": True,
                        "check_sitemap": True
                    }
                ),
                PhaseType.VULNERABILITY_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=450,
                    max_retries=2,
                    priority=4,
                    dependencies={PhaseType.WEB_SCAN, PhaseType.PORT_SCAN},
                    parameters={
                        "nuclei_templates": ["cves/", "vulnerabilities/", "misconfiguration/"],
                        "custom_payloads": True,
                        "deep_scan": False,
                        "severity_filter": ["critical", "high", "medium"]
                    }
                ),
                PhaseType.AI_ANALYSIS: PhaseConfig(
                    enabled=True,
                    timeout_seconds=120,
                    max_retries=1,
                    priority=5,
                    dependencies={PhaseType.VULNERABILITY_SCAN},
                    parameters={
                        "model": "gpt-4-turbo",
                        "analysis_depth": "standard",
                        "include_business_context": False
                    }
                ),
                PhaseType.EXPLOIT_GENERATION: PhaseConfig(enabled=False)
            }
        )
        
        # COMPREHENSIVE Profile - Deep and thorough scanning
        comprehensive_profile = ScanProfile(
            name="Comprehensive Scan",
            description="Thorough security assessment with deep analysis",
            scan_type=ScanType.COMPREHENSIVE,
            estimated_duration_minutes=45,
            max_concurrent_phases=4,
            overall_timeout_minutes=90,
            enable_caching=True,
            enable_ai_analysis=True,
            cpu_intensive_limit=3,
            network_request_limit=500,
            memory_limit_mb=1024,
            include_exploits=True,
            detailed_logging=True,
            phases={
                PhaseType.RECONNAISSANCE: PhaseConfig(
                    enabled=True,
                    timeout_seconds=360,
                    max_retries=3,
                    priority=1,
                    parameters={
                        "dns_enumeration": True,
                        "subdomain_discovery": True,
                        "certificate_transparency": True,
                        "whois_lookup": True,
                        "max_subdomains": 100,
                        "passive_recon": True,
                        "shodan_lookup": True,
                        "social_media_recon": True,
                        "email_discovery": True
                    }
                ),
                PhaseType.PORT_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=600,
                    max_retries=3,
                    priority=2,
                    dependencies={PhaseType.RECONNAISSANCE},
                    parameters={
                        "port_range": "1-65535",  # Full port range
                        "scan_type": "comprehensive",
                        "timing": "normal",
                        "service_detection": True,
                        "version_detection": True,
                        "script_scanning": True,
                        "os_detection": True
                    }
                ),
                PhaseType.WEB_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=480,
                    max_retries=3,
                    priority=3,
                    parallel_execution=True,
                    dependencies={PhaseType.PORT_SCAN},
                    parameters={
                        "check_ssl": True,
                        "check_headers": True,
                        "directory_bruteforce": True,
                        "technology_detection": True,
                        "max_paths": 200,
                        "check_robots_txt": True,
                        "check_sitemap": True,
                        "parameter_discovery": True,
                        "form_analysis": True,
                        "cookie_analysis": True
                    }
                ),
                PhaseType.VULNERABILITY_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=900,
                    max_retries=3,
                    priority=4,
                    dependencies={PhaseType.WEB_SCAN, PhaseType.PORT_SCAN},
                    parameters={
                        "nuclei_templates": ["cves/", "vulnerabilities/", "misconfiguration/", "exposures/"],
                        "custom_payloads": True,
                        "deep_scan": True,
                        "severity_filter": ["critical", "high", "medium", "low"],
                        "authenticated_scan": True,
                        "brute_force_checks": True
                    }
                ),
                PhaseType.AI_ANALYSIS: PhaseConfig(
                    enabled=True,
                    timeout_seconds=180,
                    max_retries=2,
                    priority=5,
                    dependencies={PhaseType.VULNERABILITY_SCAN},
                    parameters={
                        "model": "gpt-4-turbo",
                        "analysis_depth": "comprehensive",
                        "include_business_context": True,
                        "threat_modeling": True,
                        "risk_assessment": True
                    }
                ),
                PhaseType.EXPLOIT_GENERATION: PhaseConfig(
                    enabled=True,
                    timeout_seconds=240,
                    max_retries=2,
                    priority=6,
                    dependencies={PhaseType.AI_ANALYSIS},
                    parameters={
                        "generate_poc": True,
                        "severity_threshold": "medium",
                        "include_metasploit": True,
                        "custom_exploits": True
                    }
                )
            }
        )
        
        # STEALTH Profile - Evade detection
        stealth_profile = ScanProfile(
            name="Stealth Scan",
            description="Low-profile scanning to evade detection",
            scan_type=ScanType.STEALTH,
            estimated_duration_minutes=60,
            max_concurrent_phases=1,  # Sequential execution
            overall_timeout_minutes=120,
            enable_caching=True,
            enable_ai_analysis=True,
            cpu_intensive_limit=1,
            network_request_limit=50,
            memory_limit_mb=256,
            include_exploits=False,
            phases={
                PhaseType.RECONNAISSANCE: PhaseConfig(
                    enabled=True,
                    timeout_seconds=600,
                    max_retries=1,
                    priority=1,
                    parallel_execution=False,
                    parameters={
                        "dns_enumeration": True,
                        "subdomain_discovery": True,
                        "certificate_transparency": True,
                        "whois_lookup": False,  # Avoid leaving traces
                        "max_subdomains": 10,
                        "passive_recon": True,
                        "delay_between_requests": 5,  # Slow down
                        "randomize_user_agents": True
                    }
                ),
                PhaseType.PORT_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=1200,
                    max_retries=1,
                    priority=2,
                    parallel_execution=False,
                    dependencies={PhaseType.RECONNAISSANCE},
                    parameters={
                        "port_range": "22,80,443,8080,8443",  # Only common ports
                        "scan_type": "connect",  # Less suspicious
                        "timing": "paranoid",  # Very slow
                        "service_detection": False,
                        "randomize_order": True,
                        "source_port_randomization": True
                    }
                ),
                PhaseType.WEB_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=480,
                    max_retries=1,
                    priority=3,
                    parallel_execution=False,
                    dependencies={PhaseType.PORT_SCAN},
                    parameters={
                        "check_ssl": True,
                        "check_headers": True,
                        "directory_bruteforce": False,  # Too noisy
                        "technology_detection": True,
                        "max_paths": 5,
                        "delay_between_requests": 3,
                        "randomize_user_agents": True,
                        "respect_robots_txt": True
                    }
                ),
                PhaseType.VULNERABILITY_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=600,
                    max_retries=1,
                    priority=4,
                    parallel_execution=False,
                    dependencies={PhaseType.WEB_SCAN},
                    parameters={
                        "nuclei_templates": ["cves/critical"],  # Only critical
                        "custom_payloads": False,
                        "deep_scan": False,
                        "rate_limit": "1req/5s",
                        "randomize_payloads": True
                    }
                ),
                PhaseType.AI_ANALYSIS: PhaseConfig(
                    enabled=True,
                    timeout_seconds=120,
                    priority=5,
                    dependencies={PhaseType.VULNERABILITY_SCAN},
                    parameters={
                        "model": "gpt-3.5-turbo",  # Faster/cheaper
                        "analysis_depth": "basic"
                    }
                ),
                PhaseType.EXPLOIT_GENERATION: PhaseConfig(enabled=False)
            }
        )
        
        # COMPLIANCE Profile - Focus on compliance requirements
        compliance_profile = ScanProfile(
            name="Compliance Scan",
            description="Security assessment focused on compliance requirements",
            scan_type=ScanType.COMPLIANCE,
            estimated_duration_minutes=30,
            max_concurrent_phases=3,
            overall_timeout_minutes=60,
            enable_caching=True,
            enable_ai_analysis=True,
            generate_report=True,
            detailed_logging=True,
            phases={
                PhaseType.RECONNAISSANCE: PhaseConfig(
                    enabled=True,
                    timeout_seconds=240,
                    priority=1,
                    parameters={
                        "dns_enumeration": True,
                        "certificate_analysis": True,
                        "compliance_focused": True
                    }
                ),
                PhaseType.PORT_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=360,
                    priority=2,
                    dependencies={PhaseType.RECONNAISSANCE},
                    parameters={
                        "port_range": "1-10000",
                        "focus_on_compliance_ports": True,
                        "banner_grabbing": True
                    }
                ),
                PhaseType.WEB_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=300,
                    priority=3,
                    dependencies={PhaseType.PORT_SCAN},
                    parameters={
                        "ssl_compliance_check": True,
                        "security_headers_compliance": True,
                        "cookie_security": True,
                        "privacy_policy_check": True
                    }
                ),
                PhaseType.VULNERABILITY_SCAN: PhaseConfig(
                    enabled=True,
                    timeout_seconds=540,
                    priority=4,
                    dependencies={PhaseType.WEB_SCAN},
                    parameters={
                        "compliance_templates": ["pci-dss", "gdpr", "hipaa", "sox"],
                        "focus_on_data_protection": True,
                        "encryption_checks": True
                    }
                ),
                PhaseType.AI_ANALYSIS: PhaseConfig(
                    enabled=True,
                    timeout_seconds=150,
                    priority=5,
                    dependencies={PhaseType.VULNERABILITY_SCAN},
                    parameters={
                        "compliance_focus": True,
                        "risk_assessment": True,
                        "remediation_priority": "compliance_first"
                    }
                ),
                PhaseType.EXPLOIT_GENERATION: PhaseConfig(enabled=False)
            }
        )
        
        # Store profiles
        self.profiles[ScanType.QUICK] = quick_profile
        self.profiles[ScanType.STANDARD] = standard_profile
        self.profiles[ScanType.COMPREHENSIVE] = comprehensive_profile
        self.profiles[ScanType.STEALTH] = stealth_profile
        self.profiles[ScanType.COMPLIANCE] = compliance_profile
        
        logger.info(f"Initialized {len(self.profiles)} scan profiles")
    
    def get_profile(self, scan_type: ScanType) -> Optional[ScanProfile]:
        """Get scan profile by type"""
        return self.profiles.get(scan_type)
    
    def get_all_profiles(self) -> Dict[ScanType, ScanProfile]:
        """Get all available profiles"""
        return self.profiles.copy()
    
    def create_custom_profile(
        self,
        name: str,
        description: str,
        base_profile: ScanType = ScanType.STANDARD,
        modifications: Dict[str, Any] = None
    ) -> ScanProfile:
        """Create a custom profile based on existing one"""
        base = self.get_profile(base_profile)
        if not base:
            raise ValueError(f"Base profile {base_profile} not found")
        
        # Create copy of base profile
        custom_profile = ScanProfile(
            name=name,
            description=description,
            scan_type=ScanType.TARGETED,
            estimated_duration_minutes=base.estimated_duration_minutes,
            phases=base.phases.copy(),
            max_concurrent_phases=base.max_concurrent_phases,
            overall_timeout_minutes=base.overall_timeout_minutes,
            enable_caching=base.enable_caching,
            enable_ai_analysis=base.enable_ai_analysis,
            cpu_intensive_limit=base.cpu_intensive_limit,
            network_request_limit=base.network_request_limit,
            memory_limit_mb=base.memory_limit_mb,
            generate_report=base.generate_report,
            include_exploits=base.include_exploits,
            detailed_logging=base.detailed_logging
        )
        
        # Apply modifications
        if modifications:
            for key, value in modifications.items():
                if hasattr(custom_profile, key):
                    setattr(custom_profile, key, value)
                else:
                    logger.warning(f"Unknown profile attribute: {key}")
        
        return custom_profile
    
    def get_profile_summary(self) -> Dict[str, Any]:
        """Get summary of all profiles"""
        summary = {}
        
        for scan_type, profile in self.profiles.items():
            enabled_phases = [phase.name for phase, config in profile.phases.items() if config.enabled]
            
            summary[scan_type.value] = {
                "name": profile.name,
                "description": profile.description,
                "estimated_duration_minutes": profile.estimated_duration_minutes,
                "enabled_phases": enabled_phases,
                "ai_analysis_enabled": profile.enable_ai_analysis,
                "includes_exploits": profile.include_exploits,
                "max_concurrent_phases": profile.max_concurrent_phases
            }
        
        return summary
    
    def validate_profile(self, profile: ScanProfile) -> List[str]:
        """Validate profile configuration and return any issues"""
        issues = []
        
        # Check if at least one phase is enabled
        enabled_phases = [phase for phase, config in profile.phases.items() if config.enabled]
        if not enabled_phases:
            issues.append("No phases are enabled")
        
        # Check for circular dependencies
        for phase_type, config in profile.phases.items():
            if not config.enabled:
                continue
                
            if phase_type in config.dependencies:
                issues.append(f"Phase {phase_type.value} has circular dependency on itself")
            
            # Check if dependencies are enabled
            for dep in config.dependencies:
                if dep not in profile.phases or not profile.phases[dep].enabled:
                    issues.append(f"Phase {phase_type.value} depends on disabled phase {dep.value}")
        
        # Check timeout values
        if profile.overall_timeout_minutes <= 0:
            issues.append("Overall timeout must be positive")
        
        total_phase_timeout = sum(
            config.timeout_seconds for config in profile.phases.values() if config.enabled
        )
        if total_phase_timeout > profile.overall_timeout_minutes * 60:
            issues.append("Sum of phase timeouts exceeds overall timeout")
        
        # Check resource limits
        if profile.max_concurrent_phases <= 0:
            issues.append("Max concurrent phases must be positive")
        
        if profile.cpu_intensive_limit <= 0:
            issues.append("CPU intensive limit must be positive")
        
        return issues


# Global profile manager instance
profile_manager = ScanProfileManager()