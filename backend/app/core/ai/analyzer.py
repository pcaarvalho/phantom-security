import openai
import json
import asyncio
from typing import Dict, List, Any
from app.config import settings
from ..resilience.circuit_breaker import circuit_breaker, CircuitBreakerConfig
from ..resilience.rate_limiter import rate_limited, RateLimitConfig
from ..error_handling.error_handler import with_error_handling, RetryConfig
from ..logging.structured_logger import get_logger, EventType

logger = get_logger(__name__)

class AIThreatAnalyzer:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4-turbo"
        self.fallback_model = "gpt-3.5-turbo"
    
    async def analyze_scan_results(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use GPT-4 to analyze vulnerability scan results"""
        
        if not settings.openai_api_key:
            return self._fallback_analysis(scan_data)
        
        try:
            prompt = self._build_analysis_prompt(scan_data)
            
            # Try GPT-4 first, fallback to GPT-3.5 if needed
            analysis = await self._call_openai_api(prompt, self.model)
            
            if not analysis:
                analysis = await self._call_openai_api(prompt, self.fallback_model)
            
            return analysis or self._fallback_analysis(scan_data)
            
        except Exception as e:
            print(f"AI Analysis error: {e}")
            return self._fallback_analysis(scan_data)
    
    @circuit_breaker(
        "openai_service",
        CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            timeout=60.0,
            max_calls_per_minute=50
        )
    )
    @rate_limited(
        "openai_api",
        RateLimitConfig(
            max_requests=50,
            time_window_seconds=60,
            backoff_strategy=RateLimitConfig().backoff_strategy
        )
    )
    @with_error_handling(
        RetryConfig(max_attempts=3, base_delay_seconds=2.0),
        handler_name="openai_analyzer"
    )
    async def _call_openai_api(self, prompt: str, model: str) -> Dict[str, Any]:
        """Make API call to OpenAI with resilience features"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(
                "Starting OpenAI API call",
                event_type=EventType.EXTERNAL_SERVICE,
                metadata={
                    "model": model,
                    "prompt_length": len(prompt)
                }
            )
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert cybersecurity analyst with deep knowledge of:
                        - Network security and penetration testing
                        - Web application vulnerabilities (OWASP Top 10)
                        - Infrastructure security
                        - Risk assessment and business impact analysis
                        - Executive reporting and communication
                        
                        Your analysis should be thorough, accurate, and actionable.
                        Always consider the business context and provide clear remediation steps."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent security analysis
                max_tokens=2500,
                timeout=60
            )
            
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            logger.info(
                "OpenAI API call completed successfully",
                event_type=EventType.EXTERNAL_SERVICE,
                performance_metrics={
                    "response_time_ms": response_time_ms,
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                },
                metadata={
                    "model": model,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0
                }
            )
            
            content = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # If not valid JSON, try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                
                # If still no valid JSON, return structured response
                return self._parse_unstructured_response(content)
                
        except Exception as e:
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            logger.error(
                "OpenAI API call failed",
                error=e,
                event_type=EventType.ERROR_OCCURRED,
                performance_metrics={"response_time_ms": response_time_ms},
                metadata={"model": model, "prompt_length": len(prompt)}
            )
            raise
    
    def _build_analysis_prompt(self, scan_data: Dict[str, Any]) -> str:
        """Build comprehensive analysis prompt for AI"""
        
        # Extract key information from scan results
        target = scan_data.get('target', 'Unknown')
        port_scan = scan_data.get('port_scan', {})
        web_scan = scan_data.get('web_scan', {})
        nuclei_scan = scan_data.get('nuclei_scan', {})
        dns_records = scan_data.get('dns_records', {})
        
        # Count vulnerabilities by severity
        vuln_counts = self._count_vulnerabilities(nuclei_scan)
        
        prompt = f"""
        Please analyze the following comprehensive security scan results and provide a detailed assessment:

        TARGET: {target}
        
        === SCAN RESULTS ===
        
        1. PORT SCAN RESULTS:
        {json.dumps(port_scan, indent=2)[:1000]}...
        
        2. WEB APPLICATION SCAN:
        {json.dumps(web_scan, indent=2)[:1000]}...
        
        3. VULNERABILITY SCAN (Nuclei):
        Found {vuln_counts['total']} vulnerabilities
        - Critical: {vuln_counts['critical']}
        - High: {vuln_counts['high']}
        - Medium: {vuln_counts['medium']}
        - Low: {vuln_counts['low']}
        
        Detailed vulnerabilities:
        {json.dumps(nuclei_scan.get('vulnerabilities', [])[:10], indent=2)[:1500]}...
        
        4. DNS RECONNAISSANCE:
        {json.dumps(dns_records, indent=2)[:500]}...
        
        === ANALYSIS REQUIREMENTS ===
        
        Provide your analysis in this exact JSON format:
        
        {{
            "executive_summary": "2-3 paragraph executive summary suitable for C-level executives",
            "risk_score": <integer from 0-100>,
            "critical_findings": [
                {{
                    "title": "Vulnerability title",
                    "severity": "Critical/High/Medium/Low",
                    "description": "Technical description",
                    "exploitation_method": "How an attacker would exploit this",
                    "business_impact": "Impact on business operations",
                    "remediation": "Specific steps to fix"
                }}
            ],
            "attack_narrative": "Step-by-step description of how an attacker would compromise this system",
            "business_impact": "Detailed assessment of potential business consequences",
            "recommendations": [
                "Prioritized list of remediation actions"
            ],
            "compliance_notes": "Relevant compliance framework violations (GDPR, SOX, HIPAA, etc.)",
            "timeline_for_remediation": "Recommended timeline for addressing issues"
        }}
        
        === ANALYSIS GUIDELINES ===
        
        1. Risk Score Calculation:
        - 0-25: Low risk (minor issues, no critical vulnerabilities)
        - 26-50: Medium risk (some security gaps, potential for exploitation)
        - 51-75: High risk (significant vulnerabilities, likely exploitation)
        - 76-100: Critical risk (immediate threat, active exploitation likely)
        
        2. Focus on:
        - Exploitable vulnerabilities with high impact
        - Missing security controls
        - Configuration weaknesses
        - Information disclosure
        - Authentication and authorization flaws
        
        3. Consider:
        - Ease of exploitation
        - Potential for lateral movement
        - Data exposure risks
        - Service disruption possibilities
        - Reputational damage
        
        4. Provide actionable recommendations prioritized by:
        - Risk reduction impact
        - Implementation difficulty
        - Cost considerations
        - Compliance requirements
        """
        
        return prompt
    
    def _count_vulnerabilities(self, nuclei_scan: Dict[str, Any]) -> Dict[str, int]:
        """Count vulnerabilities by severity"""
        counts = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        
        vulnerabilities = nuclei_scan.get("vulnerabilities", [])
        counts["total"] = len(vulnerabilities)
        
        for vuln in vulnerabilities:
            severity = vuln.get("severity", "unknown").lower()
            if severity in counts:
                counts[severity] += 1
        
        return counts
    
    def _parse_unstructured_response(self, content: str) -> Dict[str, Any]:
        """Parse unstructured AI response into structured format"""
        lines = content.split('\n')
        
        analysis = {
            "executive_summary": "AI analysis completed but response format was unstructured.",
            "risk_score": 50,  # Default medium risk
            "critical_findings": [],
            "attack_narrative": "Analysis available in raw format.",
            "business_impact": "Impact assessment requires manual review.",
            "recommendations": ["Review raw AI output for detailed recommendations"],
            "raw_response": content
        }
        
        # Try to extract key information using simple patterns
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            if "risk score" in line_lower or "score:" in line_lower:
                import re
                score_match = re.search(r'(\d+)', line)
                if score_match:
                    analysis["risk_score"] = min(100, max(0, int(score_match.group(1))))
        
        return analysis
    
    def _fallback_analysis(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback analysis when AI is not available"""
        
        # Count vulnerabilities and open ports
        nuclei_scan = scan_data.get("nuclei_scan", {})
        port_scan = scan_data.get("port_scan", {})
        web_scan = scan_data.get("web_scan", {})
        
        vuln_counts = self._count_vulnerabilities(nuclei_scan)
        open_ports = len(port_scan.get("ports", []))
        
        # Calculate risk score based on findings
        risk_score = 0
        risk_factors = []
        
        if vuln_counts["critical"] > 0:
            risk_score += 40
            risk_factors.append(f"{vuln_counts['critical']} critical vulnerabilities")
        
        if vuln_counts["high"] > 0:
            risk_score += 25
            risk_factors.append(f"{vuln_counts['high']} high-severity vulnerabilities")
        
        if vuln_counts["medium"] > 0:
            risk_score += 15
            risk_factors.append(f"{vuln_counts['medium']} medium-severity vulnerabilities")
        
        if open_ports > 10:
            risk_score += 10
            risk_factors.append(f"{open_ports} open ports detected")
        
        # Check for missing security headers
        web_security = web_scan.get("security_headers", {})
        if isinstance(web_security, dict):
            missing_headers = len(web_security.get("missing_headers", []))
            if missing_headers > 3:
                risk_score += 10
                risk_factors.append(f"{missing_headers} security headers missing")
        
        risk_score = min(100, risk_score)
        
        return {
            "executive_summary": f"Automated security scan of {scan_data.get('target')} completed. "
                               f"Found {vuln_counts['total']} vulnerabilities across {open_ports} open services. "
                               f"Risk assessment indicates {'immediate attention required' if risk_score > 70 else 'security improvements needed'}.",
            "risk_score": risk_score,
            "critical_findings": self._extract_critical_findings(nuclei_scan),
            "attack_narrative": "Detailed attack analysis requires AI integration. Manual review recommended.",
            "business_impact": f"Security vulnerabilities detected may impact business operations. "
                             f"Risk level: {'Critical' if risk_score > 70 else 'High' if risk_score > 40 else 'Medium'}",
            "recommendations": [
                "Address critical and high-severity vulnerabilities immediately",
                "Review and harden network service configurations", 
                "Implement missing security headers for web applications",
                "Conduct regular security assessments",
                "Consider engaging security professionals for detailed analysis"
            ],
            "analysis_method": "fallback_heuristic",
            "risk_factors": risk_factors
        }
    
    def _extract_critical_findings(self, nuclei_scan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract critical findings from nuclei scan"""
        findings = []
        vulnerabilities = nuclei_scan.get("vulnerabilities", [])
        
        # Get up to 5 most critical vulnerabilities
        critical_vulns = [v for v in vulnerabilities if v.get("severity", "").lower() == "critical"]
        high_vulns = [v for v in vulnerabilities if v.get("severity", "").lower() == "high"]
        
        top_vulns = (critical_vulns + high_vulns)[:5]
        
        for vuln in top_vulns:
            findings.append({
                "title": vuln.get("template_name", "Unknown Vulnerability"),
                "severity": vuln.get("severity", "Unknown").title(),
                "description": vuln.get("description", "No description available"),
                "exploitation_method": "Manual analysis required for exploitation details",
                "business_impact": f"Potential {vuln.get('severity', 'unknown')} impact on business operations",
                "remediation": "Refer to security best practices for this vulnerability type"
            })
        
        return findings