#!/usr/bin/env python3
"""
Debug script para diagnosticar problemas com Celery
"""
import os
import sys
import time
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables if needed
os.environ['DATABASE_URL'] = 'postgresql://phantom_user:phantom_password@localhost:5432/phantom_db'
os.environ['REDIS_URL'] = 'redis://localhost:6379'

def test_redis_connection():
    """Test Redis connection"""
    print("\n1. Testing Redis Connection...")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis is running and accessible")
        
        # Check Celery queues
        keys = r.keys("*celery*")
        print(f"   Found {len(keys)} Celery-related keys in Redis")
        for key in keys[:5]:
            print(f"   - {key.decode('utf-8')}")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_celery_import():
    """Test Celery imports"""
    print("\n2. Testing Celery Imports...")
    try:
        from app.tasks.celery_app import celery_app
        print("✅ Celery app imported successfully")
        
        # Check registered tasks
        tasks = list(celery_app.tasks.keys())
        print(f"   Found {len(tasks)} registered tasks:")
        for task in tasks:
            if 'app.tasks' in task:
                print(f"   - {task}")
        return True
    except Exception as e:
        print(f"❌ Celery import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_task_send():
    """Test sending a task to Celery"""
    print("\n3. Testing Task Send...")
    try:
        from app.tasks.celery_app import celery_app
        
        # Create a simple test task
        @celery_app.task
        def test_task(x, y):
            return x + y
        
        # Send task
        result = test_task.delay(2, 3)
        print(f"✅ Task sent successfully")
        print(f"   Task ID: {result.id}")
        print(f"   Task State: {result.state}")
        
        # Wait for result (max 5 seconds)
        print("   Waiting for result...")
        for i in range(5):
            if result.ready():
                print(f"✅ Task completed with result: {result.get()}")
                return True
            time.sleep(1)
            print(f"   State: {result.state}")
        
        print("⚠️  Task not completed within 5 seconds")
        return False
    except Exception as e:
        print(f"❌ Task send failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scan_task():
    """Test the actual scan task"""
    print("\n4. Testing Scan Task...")
    try:
        from app.tasks.scan_tasks import start_scan_task
        from app.database import SessionLocal
        from app.models.scan import Scan, ScanStatus
        
        db = SessionLocal()
        
        # Create a test scan
        scan = Scan(
            target="scanme.nmap.org",
            status=ScanStatus.PENDING,
            scan_type="test",
            created_at=datetime.utcnow()
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        
        print(f"✅ Created test scan with ID: {scan.id}")
        
        # Send scan task
        result = start_scan_task.delay(scan.id)
        print(f"✅ Scan task sent")
        print(f"   Task ID: {result.id}")
        
        # Update scan with task ID
        scan.task_id = str(result.id)
        db.commit()
        
        # Monitor task
        print("   Monitoring task progress...")
        for i in range(10):
            state = result.state
            print(f"   [{i+1}/10] State: {state}")
            
            if state == 'SUCCESS':
                print("✅ Scan completed successfully!")
                return True
            elif state == 'FAILURE':
                print(f"❌ Scan failed: {result.info}")
                return False
            elif state == 'PROGRESS':
                info = result.info or {}
                print(f"      Progress: {info.get('current', 0)}/{info.get('total', 100)}")
                print(f"      Status: {info.get('status', '')}")
            
            time.sleep(2)
        
        print("⚠️  Scan did not complete within 20 seconds")
        print(f"   Final state: {result.state}")
        
        # Check scan in database
        db.refresh(scan)
        print(f"   DB Status: {scan.status}")
        
        db.close()
        return False
        
    except Exception as e:
        print(f"❌ Scan task test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_worker_status():
    """Check if Celery worker is running and processing"""
    print("\n5. Checking Worker Status...")
    try:
        from app.tasks.celery_app import celery_app
        
        # Inspect active workers
        i = celery_app.control.inspect()
        
        # Get active workers
        active = i.active()
        if active:
            print(f"✅ Found {len(active)} active worker(s):")
            for worker, tasks in active.items():
                print(f"   - {worker}: {len(tasks)} active tasks")
        else:
            print("⚠️  No active workers found")
            print("   Make sure to run: celery -A app.tasks.celery_app worker --loglevel=info")
            return False
        
        # Get registered tasks
        registered = i.registered()
        if registered:
            for worker, tasks in registered.items():
                print(f"\n   Worker {worker} has {len(tasks)} registered tasks")
                scan_tasks = [t for t in tasks if 'scan' in t.lower()]
                if scan_tasks:
                    print("   Scan-related tasks:")
                    for task in scan_tasks[:5]:
                        print(f"     - {task}")
        
        # Get stats
        stats = i.stats()
        if stats:
            for worker, stat in stats.items():
                print(f"\n   Worker {worker} stats:")
                print(f"     - Total tasks: {stat.get('total', {})}")
        
        return True
        
    except Exception as e:
        print(f"❌ Worker status check failed: {e}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("PHANTOM SECURITY AI - CELERY DEBUG")
    print("="*60)
    
    results = {
        "Redis": test_redis_connection(),
        "Celery Import": test_celery_import(),
        "Worker Status": check_worker_status(),
        "Task Send": test_task_send(),
        "Scan Task": test_scan_task()
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test}: {status}")
    
    if all(results.values()):
        print("\n🎉 All tests passed! Celery is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        print("\nTroubleshooting tips:")
        print("1. Make sure Redis is running: redis-cli ping")
        print("2. Start Celery worker: celery -A app.tasks.celery_app worker --loglevel=info")
        print("3. Check .env file for correct configuration")
        print("4. Verify database connection settings")

if __name__ == "__main__":
    main()