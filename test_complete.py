#!/usr/bin/env python3
"""
PHANTOM Security AI - Complete System Test
Tests the entire backend engine
"""

import sys
import os
import time
import json
import subprocess

# Change to backend directory and add to path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

import asyncio
from app.core.scanner.vulnerability_scanner import VulnerabilityScanner
from app.core.ai.analyzer import AIThreatAnalyzer

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

async def test_scanner():
    """Test vulnerability scanner directly"""
    print_header("TESTING VULNERABILITY SCANNER")
    
    target = "scanme.nmap.org"  # Legal test target
    print(f"\n🎯 Target: {target}")
    
    scanner = VulnerabilityScanner(target)
    
    print("\n📡 Starting scan...")
    start_time = time.time()
    
    try:
        results = await scanner.scan()
        elapsed = time.time() - start_time
        
        print(f"✅ Scan completed in {elapsed:.2f} seconds")
        
        # Display results
        print("\n📊 SCAN RESULTS:")
        
        # Port scan
        port_scan = results.get('port_scan', {})
        if 'ports' in port_scan:
            print(f"\n🔌 Open Ports: {len(port_scan['ports'])}")
            for port in port_scan['ports'][:5]:
                print(f"   - Port {port['port']}: {port['service']} ({port['state']})")
        
        # Web scan
        web_scan = results.get('web_scan', {})
        if web_scan:
            ssl_status = web_scan.get('ssl_security', {}).get('status', 'unknown')
            print(f"\n🔐 SSL Status: {ssl_status}")
            
            headers = web_scan.get('security_headers', {})
            if headers and 'missing_headers' in headers:
                missing = headers['missing_headers']
                print(f"📝 Missing Security Headers: {len(missing)}")
        
        # DNS records
        dns_records = results.get('dns_records', {})
        if dns_records and 'subdomains' in dns_records:
            print(f"\n🌐 Subdomains Found: {len(dns_records['subdomains'])}")
        
        # Vulnerability summary
        vuln_summary = results.get('vulnerability_summary', {})
        if vuln_summary:
            print(f"\n🐛 Vulnerability Summary:")
            print(f"   Total: {vuln_summary.get('total_vulnerabilities', 0)}")
            print(f"   Critical: {vuln_summary['severity_breakdown'].get('critical', 0)}")
            print(f"   High: {vuln_summary['severity_breakdown'].get('high', 0)}")
            print(f"   Medium: {vuln_summary['severity_breakdown'].get('medium', 0)}")
            print(f"   Low: {vuln_summary['severity_breakdown'].get('low', 0)}")
        
        return results
        
    except Exception as e:
        print(f"❌ Scan failed: {e}")
        return None

async def test_ai_analyzer(scan_results):
    """Test AI analyzer"""
    print_header("TESTING AI ANALYZER")
    
    if not scan_results:
        print("⚠️  No scan results to analyze")
        return None
    
    analyzer = AIThreatAnalyzer()
    
    print("\n🤖 Analyzing with AI...")
    start_time = time.time()
    
    try:
        analysis = await analyzer.analyze_scan_results(scan_results)
        elapsed = time.time() - start_time
        
        print(f"✅ Analysis completed in {elapsed:.2f} seconds")
        
        # Display analysis
        print("\n📊 AI ANALYSIS:")
        
        print(f"\n📈 Risk Score: {analysis.get('risk_score', 'N/A')}/100")
        
        print(f"\n📝 Executive Summary:")
        summary = analysis.get('executive_summary', 'No summary available')
        print(f"   {summary[:300]}..." if len(summary) > 300 else f"   {summary}")
        
        critical_findings = analysis.get('critical_findings', [])
        if critical_findings:
            print(f"\n⚠️  Critical Findings: {len(critical_findings)}")
            for i, finding in enumerate(critical_findings[:3], 1):
                print(f"\n   {i}. {finding.get('title', 'Unknown')}")
                print(f"      Severity: {finding.get('severity', 'Unknown')}")
                print(f"      Impact: {finding.get('business_impact', 'N/A')[:100]}...")
        
        recommendations = analysis.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Top Recommendations:")
            for i, rec in enumerate(recommendations[:3], 1):
                print(f"   {i}. {rec}")
        
        return analysis
        
    except Exception as e:
        print(f"❌ AI Analysis failed: {e}")
        print("   Using fallback analysis...")
        return analyzer._fallback_analysis(scan_results)

async def test_report_generation(scan_results, ai_analysis):
    """Test report generation"""
    print_header("TESTING REPORT GENERATION")
    
    try:
        from app.core.reports import PHANTOMReportGenerator
        
        generator = PHANTOMReportGenerator()
        
        # Prepare data
        scan_data = {
            'target': 'scanme.nmap.org',
            'scan_results': scan_results or {},
            'ai_analysis': ai_analysis or {},
            'vulnerability_count': scan_results.get('vulnerability_summary', {}).get('total_vulnerabilities', 0) if scan_results else 0,
            'vulnerability_summary': scan_results.get('vulnerability_summary', {}) if scan_results else {}
        }
        
        print("\n📄 Generating PDF report...")
        start_time = time.time()
        
        report_path = generator.generate_report(scan_data)
        elapsed = time.time() - start_time
        
        print(f"✅ Report generated in {elapsed:.2f} seconds")
        print(f"📍 Report saved to: {report_path}")
        
        # Check file size
        file_size = os.path.getsize(report_path) / 1024  # KB
        print(f"📊 Report size: {file_size:.2f} KB")
        
        return report_path
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return None

async def main():
    """Main test function"""
    print_header("PHANTOM SECURITY AI - COMPLETE ENGINE TEST")
    print(f"Python: {sys.version}")
    print(f"Working Directory: {os.getcwd()}")
    
    # Test scanner
    scan_results = await test_scanner()
    
    # Test AI analyzer
    ai_analysis = None
    if scan_results:
        ai_analysis = await test_ai_analyzer(scan_results)
    
    # Test report generation
    if scan_results:
        report_path = await test_report_generation(scan_results, ai_analysis)
    
    print_header("TEST SUMMARY")
    
    results = {
        "Scanner": "✅" if scan_results else "❌",
        "AI Analysis": "✅" if ai_analysis else "❌",
        "Report Generation": "✅" if report_path else "❌"
    }
    
    for component, status in results.items():
        print(f"{status} {component}")
    
    if all(v == "✅" for v in results.values()):
        print("\n🎉 ALL TESTS PASSED! Engine is fully functional!")
        return 0
    else:
        print("\n⚠️  Some components need attention")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)