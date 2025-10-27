#!/usr/bin/env python3
"""
Test Celery task execution directly
"""
import os
import sys
import time

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment
os.environ['DATABASE_URL'] = 'postgresql://phantom_user:phantom_password@localhost:5432/phantom_db'
os.environ['REDIS_URL'] = 'redis://localhost:6379'

def test_simple_task():
    """Test with a simple calculation task"""
    print("\nTesting Simple Task Execution...")
    
    from app.tasks.celery_app import celery_app
    
    # Register a simple test task
    @celery_app.task(name='test.add')
    def add(x, y):
        return x + y
    
    # Send task
    result = add.delay(4, 6)
    print(f"Task ID: {result.id}")
    
    # Wait for result
    for i in range(5):
        print(f"Attempt {i+1}: State = {result.state}")
        if result.ready():
            print(f"✅ Result: {result.get(timeout=1)}")
            return True
        time.sleep(1)
    
    print(f"❌ Task still in state: {result.state}")
    return False

def test_quick_scan():
    """Test quick scan task"""
    print("\nTesting Quick Scan Task...")
    
    from app.tasks.scan_tasks import quick_scan_task
    
    # Send task
    result = quick_scan_task.delay("scanme.nmap.org")
    print(f"Task ID: {result.id}")
    
    # Monitor progress
    for i in range(15):
        state = result.state
        print(f"[{i+1}/15] State: {state}")
        
        if state == 'PROGRESS':
            info = result.info or {}
            print(f"   Progress: {info.get('current', 0)}%")
            print(f"   Status: {info.get('status', '')}")
        elif state == 'SUCCESS':
            print("✅ Scan completed!")
            print(f"   Result: {result.get()}")
            return True
        elif state == 'FAILURE':
            print(f"❌ Scan failed: {result.info}")
            return False
        
        time.sleep(2)
    
    print(f"⚠️ Timeout - Final state: {result.state}")
    return False

def check_redis_tasks():
    """Check tasks in Redis queue"""
    print("\nChecking Redis Queue...")
    
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    
    # Check Celery queues
    queues = ['celery', 'scans', 'ai']
    for queue in queues:
        key = f"_kombu.binding.{queue}"
        if r.exists(key):
            print(f"✅ Queue '{queue}' exists")
    
    # Check for pending tasks
    task_keys = r.keys("celery-task-meta-*")
    print(f"\nFound {len(task_keys)} task metadata entries")
    
    for key in task_keys[-5:]:  # Show last 5
        task_data = r.get(key)
        if task_data:
            import json
            try:
                data = json.loads(task_data)
                print(f"  Task: {key.decode()[-8:]}")
                print(f"    Status: {data.get('status')}")
                print(f"    Result: {data.get('result')}")
            except:
                pass

if __name__ == "__main__":
    print("="*60)
    print("CELERY DIRECT TEST")
    print("="*60)
    
    # Check Redis first
    check_redis_tasks()
    
    # Test simple task
    if test_simple_task():
        print("\n✅ Simple task works!")
        
        # Test scan task
        if test_quick_scan():
            print("\n🎉 Scan tasks are working!")
        else:
            print("\n⚠️ Scan task failed")
    else:
        print("\n❌ Basic Celery not working")
        print("\nMake sure worker is running:")
        print("celery -A app.tasks.celery_app worker --loglevel=info")