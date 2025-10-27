#!/usr/bin/env python3
"""
PHANTOM Security AI - Engine Test Script
Tests all components of the backend engine
"""

import requests
import json
import time
import sys
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_TARGET = "scanme.nmap.org"  # Legal test target

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_health():
    """Test health endpoint"""
    print("\n🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API is healthy: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False

def test_scan_creation():
    """Test scan creation"""
    print("\n🚀 Creating new scan...")
    try:
        payload = {"target": TEST_TARGET}
        response = requests.post(
            f"{API_BASE_URL}/api/scans/",
            json=payload
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Scan created successfully")
            print(f"   Scan ID: {data.get('id')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Target: {data.get('target')}")
            return data.get('id')
        else:
            print(f"❌ Failed to create scan: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error creating scan: {e}")
        return None

def monitor_scan(scan_id):
    """Monitor scan progress"""
    print(f"\n📊 Monitoring scan {scan_id}...")
    
    start_time = time.time()
    max_wait = 300  # 5 minutes max
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                
                # Print progress
                print(f"\r   Status: {status}", end="")
                
                if status == 'completed':
                    print(f"\n✅ Scan completed successfully!")
                    return data
                elif status == 'failed':
                    print(f"\n❌ Scan failed: {data.get('error_message', 'Unknown error')}")
                    return None
                
                time.sleep(2)  # Check every 2 seconds
            else:
                print(f"\n❌ Failed to get scan status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"\n❌ Error monitoring scan: {e}")
            return None
    
    print(f"\n⏱️  Scan timed out after {max_wait} seconds")
    return None

def display_results(scan_data):
    """Display scan results"""
    print_header("SCAN RESULTS")
    
    if not scan_data:
        print("❌ No scan data available")
        return
    
    # Basic info
    print(f"\n📍 Target: {scan_data.get('target')}")
    print(f"🕒 Created: {scan_data.get('created_at')}")
    print(f"⏱️  Duration: {scan_data.get('duration', 'N/A')} seconds")
    
    # Vulnerability count
    vuln_count = scan_data.get('vulnerability_count', 0)
    risk_score = scan_data.get('risk_score', 0)
    
    print(f"\n🔍 Vulnerabilities Found: {vuln_count}")
    print(f"⚠️  Risk Score: {risk_score}/100")
    
    # Scan results details
    scan_results = scan_data.get('scan_results', {})
    
    if scan_results:
        # Port scan results
        port_scan = scan_results.get('port_scan', {})
        if port_scan and 'ports' in port_scan:
            ports = port_scan['ports']
            print(f"\n🔌 Open Ports: {len(ports)}")
            for port in ports[:5]:  # Show first 5 ports
                print(f"   - Port {port['port']}: {port['service']} ({port['state']})")
        
        # Web scan results
        web_scan = scan_results.get('web_scan', {})
        if web_scan:
            ssl_status = web_scan.get('ssl_security', {}).get('status', 'unknown')
            print(f"\n🔐 SSL Status: {ssl_status}")
            
            headers = web_scan.get('security_headers', {})
            if headers and 'missing_headers' in headers:
                missing = headers['missing_headers']
                print(f"📝 Missing Security Headers: {len(missing)}")
                for header in missing[:3]:  # Show first 3
                    print(f"   - {header}")
        
        # Nuclei vulnerabilities
        nuclei_scan = scan_results.get('nuclei_scan', {})
        if nuclei_scan and 'vulnerabilities' in nuclei_scan:
            vulns = nuclei_scan['vulnerabilities']
            print(f"\n🐛 Nuclei Vulnerabilities: {len(vulns)}")
            for vuln in vulns[:3]:  # Show first 3
                print(f"   - {vuln.get('template_name', 'Unknown')}: {vuln.get('severity', 'unknown')}")
    
    # AI Analysis
    ai_analysis = scan_data.get('ai_analysis', {})
    if ai_analysis:
        print_header("AI ANALYSIS")
        
        print(f"\n🤖 Executive Summary:")
        print(f"   {ai_analysis.get('executive_summary', 'No summary available')[:200]}...")
        
        print(f"\n📊 Risk Assessment: {ai_analysis.get('risk_score', 'N/A')}/100")
        
        recommendations = ai_analysis.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Top Recommendations:")
            for i, rec in enumerate(recommendations[:3], 1):
                print(f"   {i}. {rec}")

def test_report_generation(scan_id):
    """Test report generation"""
    print("\n📄 Testing report generation...")
    
    try:
        # Test JSON report
        response = requests.get(f"{API_BASE_URL}/api/reports/{scan_id}/json")
        if response.status_code == 200:
            print("✅ JSON report generated successfully")
        else:
            print(f"⚠️  JSON report failed: {response.status_code}")
        
        # Test PDF report
        response = requests.get(f"{API_BASE_URL}/api/reports/{scan_id}/pdf")
        if response.status_code == 200:
            print("✅ PDF report generated successfully")
            # Save PDF for inspection
            with open(f"test_report_{scan_id}.pdf", "wb") as f:
                f.write(response.content)
            print(f"   Saved to: test_report_{scan_id}.pdf")
        else:
            print(f"⚠️  PDF report failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error generating reports: {e}")

def run_full_test():
    """Run complete engine test"""
    print_header("PHANTOM SECURITY AI - ENGINE TEST")
    print(f"Target: {TEST_TARGET}")
    print(f"Time: {datetime.now()}")
    
    # Step 1: Test health
    if not test_health():
        print("\n❌ API is not running. Please start the backend first:")
        print("   uvicorn app.main:app --reload --port 8000")
        return False
    
    # Step 2: Create scan
    scan_id = test_scan_creation()
    if not scan_id:
        print("\n❌ Failed to create scan")
        return False
    
    # Step 3: Monitor scan
    scan_data = monitor_scan(scan_id)
    if not scan_data:
        print("\n⚠️  Scan did not complete successfully")
        # Try to get partial results
        try:
            response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
            if response.status_code == 200:
                scan_data = response.json()
        except:
            pass
    
    # Step 4: Display results
    if scan_data:
        display_results(scan_data)
    
    # Step 5: Test reports
    if scan_id:
        test_report_generation(scan_id)
    
    print_header("TEST COMPLETE")
    print("\n✅ Engine test completed successfully!")
    return True

def main():
    """Main function"""
    try:
        success = run_full_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()