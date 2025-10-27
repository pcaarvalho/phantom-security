#!/usr/bin/env python3
"""
Test Complete Workflow - Celery Integration
"""
import requests
import time
import json

def test_api_health():
    """Test API is running"""
    print("1. Testing API Health...")
    try:
        response = requests.get('http://localhost:8000/health')
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
    except:
        pass
    print("❌ API not responding")
    return False

def test_create_scan():
    """Create a new scan"""
    print("\n2. Creating New Scan...")
    
    scan_data = {
        "target": "scanme.nmap.org",
        "scan_type": "quick"
    }
    
    try:
        response = requests.post(
            'http://localhost:8000/api/scans/',
            json=scan_data
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            scan_id = data['id']
            print(f"✅ Created scan {scan_id}")
            print(f"   Target: {data['target']}")
            print(f"   Status: {data['status']}")
            return scan_id
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"   {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def monitor_scan(scan_id):
    """Monitor scan progress"""
    print(f"\n3. Monitoring Scan {scan_id}...")
    
    max_attempts = 15
    for i in range(max_attempts):
        try:
            response = requests.get(f'http://localhost:8000/api/scans/{scan_id}/status')
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                progress = data.get('progress', 0)
                task_state = data.get('task_state', 'UNKNOWN')
                
                print(f"   [{i+1}/{max_attempts}] Status: {status}, Progress: {progress}%, Task State: {task_state}")
                
                if status == 'completed':
                    print("✅ Scan completed successfully!")
                    return True
                elif status == 'failed':
                    print(f"❌ Scan failed")
                    return False
            else:
                print(f"   Error: {response.status_code}")
        except Exception as e:
            print(f"   Error: {e}")
        
        time.sleep(2)
    
    print("⚠️ Scan timeout")
    return False

def get_scan_results(scan_id):
    """Get scan results"""
    print(f"\n4. Getting Results for Scan {scan_id}...")
    
    try:
        response = requests.get(f'http://localhost:8000/api/scans/{scan_id}/results')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Got scan results:")
            print(f"   Vulnerabilities: {data.get('vulnerability_count', 0)}")
            print(f"   Risk Score: {data.get('risk_score', 0)}")
            return True
        else:
            print(f"❌ Failed to get results: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_quick_scan():
    """Test quick scan endpoint"""
    print("\n5. Testing Quick Scan Endpoint...")
    
    try:
        response = requests.post(
            'http://localhost:8000/api/scans/quick?target=scanme.nmap.org'
        )
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            print(f"✅ Quick scan started, task_id: {task_id}")
            
            # Check task status
            for i in range(5):
                response = requests.get(f'http://localhost:8000/api/scans/task/{task_id}')
                if response.status_code == 200:
                    task_data = response.json()
                    state = task_data.get('state', 'UNKNOWN')
                    print(f"   Task state: {state}")
                    if state == 'SUCCESS':
                        print("✅ Quick scan completed!")
                        return True
                time.sleep(2)
            
            return False
        else:
            print(f"❌ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("PHANTOM SECURITY - WORKFLOW TEST")
    print("="*60)
    
    # Test sequence
    if not test_api_health():
        print("\n⚠️ API not running. Start with:")
        print("uvicorn app.main:app --reload --port 8000")
        return
    
    # Create and monitor scan
    scan_id = test_create_scan()
    if scan_id:
        if monitor_scan(scan_id):
            get_scan_results(scan_id)
    
    # Test quick scan
    test_quick_scan()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()