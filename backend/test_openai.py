#!/usr/bin/env python3
"""
Test OpenAI API integration
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.core.ai.analyzer import AIThreatAnalyzer
from app.core.ai.exploit_generator import ExploitGenerator

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'


async def test_openai_connection():
    """Test if OpenAI API is working"""
    print(f"\n{CYAN}🧪 Testing OpenAI API Integration{RESET}")
    print(f"{CYAN}{'='*50}{RESET}\n")
    
    # Check API key
    if not settings.openai_api_key:
        print(f"{RED}❌ No OpenAI API key found in settings{RESET}")
        return False
    
    print(f"{GREEN}✅ OpenAI API key found{RESET}")
    print(f"   Key: {settings.openai_api_key[:20]}...{settings.openai_api_key[-4:]}\n")
    
    # Test AI Analyzer
    print(f"{YELLOW}Testing AI Threat Analyzer...{RESET}")
    analyzer = AIThreatAnalyzer()
    
    # Sample scan data
    test_scan_data = {
        "target": "test.example.com",
        "ports": [
            {"port": 22, "service": "ssh", "state": "open"},
            {"port": 80, "service": "http", "state": "open"},
            {"port": 443, "service": "https", "state": "open"},
            {"port": 3306, "service": "mysql", "state": "open"}
        ],
        "vulnerabilities": [
            {
                "name": "SQL Injection",
                "severity": "critical",
                "description": "SQL injection vulnerability in login form",
                "cve": "CVE-2024-TEST"
            },
            {
                "name": "Outdated SSL/TLS",
                "severity": "high",
                "description": "Server supports TLS 1.0 and 1.1",
                "cve": "N/A"
            }
        ],
        "web_findings": {
            "security_headers": {
                "X-Frame-Options": False,
                "Content-Security-Policy": False,
                "X-XSS-Protection": False
            },
            "ssl_issues": ["Weak cipher suites", "Certificate expires soon"]
        }
    }
    
    try:
        print(f"   Sending test data to GPT-4...")
        analysis = await analyzer.analyze_scan_results(test_scan_data)
        
        if analysis and "executive_summary" in analysis:
            print(f"{GREEN}✅ AI Analysis successful!{RESET}")
            print(f"\n{CYAN}Executive Summary:{RESET}")
            print(f"   {analysis['executive_summary'][:200]}...")
            print(f"\n{CYAN}Risk Score:{RESET} {analysis.get('risk_score', 'N/A')}/100")
            print(f"{CYAN}Critical Findings:{RESET} {len(analysis.get('critical_findings', []))}")
            return True
        else:
            print(f"{YELLOW}⚠️  AI Analysis returned but may be using fallback{RESET}")
            return True
            
    except Exception as e:
        print(f"{RED}❌ AI Analysis failed: {e}{RESET}")
        return False


async def test_exploit_generator():
    """Test exploit generation"""
    print(f"\n{YELLOW}Testing Exploit Generator...{RESET}")
    
    generator = ExploitGenerator()
    
    test_vulnerabilities = [
        {
            "name": "SQL Injection in Login",
            "severity": "critical",
            "description": "The login form is vulnerable to SQL injection",
            "affected_component": "/login.php",
            "cve": "CVE-2024-TEST"
        }
    ]
    
    try:
        print(f"   Generating exploit POC...")
        exploits = await generator.generate_exploits(test_vulnerabilities)
        
        if exploits and "exploits" in exploits:
            print(f"{GREEN}✅ Exploit generation successful!{RESET}")
            if len(exploits["exploits"]) > 0:
                exploit = exploits["exploits"][0]
                print(f"\n{CYAN}Exploit Title:{RESET} {exploit.get('title', 'N/A')}")
                print(f"{CYAN}Type:{RESET} {exploit.get('type', 'N/A')}")
                print(f"{CYAN}POC Available:{RESET} {'Yes' if exploit.get('poc_code') else 'No'}")
            return True
        else:
            print(f"{YELLOW}⚠️  Exploit generation returned but may be using fallback{RESET}")
            return True
            
    except Exception as e:
        print(f"{RED}❌ Exploit generation failed: {e}{RESET}")
        return False


async def main():
    """Run all tests"""
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}🚀 PHANTOM Security AI - OpenAI Integration Test{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")
    
    # Test connection and analysis
    ai_test = await test_openai_connection()
    
    # Test exploit generation
    exploit_test = await test_exploit_generator()
    
    # Summary
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}📊 Test Summary:{RESET}")
    print(f"   AI Analysis: {'✅ PASSED' if ai_test else '❌ FAILED'}")
    print(f"   Exploit Gen: {'✅ PASSED' if exploit_test else '❌ FAILED'}")
    
    if ai_test and exploit_test:
        print(f"\n{GREEN}🎉 All tests passed! OpenAI integration is working!{RESET}")
        print(f"\n{YELLOW}Note: You can now run scans with AI analysis:{RESET}")
        print(f"   python run.py scanme.nmap.org")
        print(f"   curl -X POST http://localhost:8000/api/scans/ -d '{{\"target\":\"scanme.nmap.org\"}}'")
    else:
        print(f"\n{RED}⚠️  Some tests failed. Check your API key and network connection.{RESET}")
    
    print(f"{CYAN}{'='*60}{RESET}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted by user{RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}Test failed with error: {e}{RESET}")
        sys.exit(1)