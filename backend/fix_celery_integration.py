#!/usr/bin/env python3
"""
Fix Celery Integration Issues
This script identifies and fixes the Celery task processing problem
"""
import os
import sys
import subprocess
import time
import json

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_environment():
    """Check environment configuration"""
    print("\n1. Checking Environment...")
    
    required_vars = {
        'DATABASE_URL': 'postgresql://phantom_user:phantom_password@localhost:5432/phantom_db',
        'REDIS_URL': 'redis://localhost:6379',
        'OPENAI_API_KEY': 'sk-your-key-here',
        'JWT_SECRET': 'your-secret-key'
    }
    
    # Load from .env if exists
    env_file = '.env'
    if os.path.exists(env_file):
        print("✅ .env file found")
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    else:
        print("⚠️  .env file not found, using defaults")
        for key, value in required_vars.items():
            if key not in os.environ:
                os.environ[key] = value
                print(f"   Set {key} to default")
    
    return True

def fix_celery_config():
    """Fix Celery configuration"""
    print("\n2. Fixing Celery Configuration...")
    
    celery_config = """from celery import Celery
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "phantom_security",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['app.tasks.scan_tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Important: Set result backend
    result_backend=settings.redis_url,
    # Important: Set default queue
    task_default_queue='celery',
    task_routes={
        'app.tasks.scan_tasks.start_scan_task': {'queue': 'celery'},
        'app.tasks.scan_tasks.quick_scan_task': {'queue': 'celery'},
        'app.tasks.scan_tasks.analyze_with_ai_task': {'queue': 'celery'},
    }
)
"""
    
    # Backup original file
    celery_file = 'app/tasks/celery_app.py'
    if os.path.exists(celery_file):
        with open(celery_file, 'r') as f:
            original = f.read()
        with open(celery_file + '.bak', 'w') as f:
            f.write(original)
        print("✅ Backed up original celery_app.py")
    
    # Write fixed version
    with open(celery_file, 'w') as f:
        f.write(celery_config)
    print("✅ Updated celery_app.py with fixes")
    
    return True

def restart_celery_worker():
    """Restart Celery worker with correct configuration"""
    print("\n3. Restarting Celery Worker...")
    
    # Kill existing workers
    try:
        subprocess.run(['pkill', '-f', 'celery.*app.tasks.celery_app worker'], check=False)
        print("✅ Stopped existing workers")
    except:
        pass
    
    time.sleep(2)
    
    # Start new worker
    cmd = [
        'celery',
        '-A', 'app.tasks.celery_app',
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--pool=prefork',
        '-n', 'phantom_worker',
        '--detach'
    ]
    
    try:
        # Activate venv if exists
        if os.path.exists('venv/bin/activate'):
            activate_cmd = 'source venv/bin/activate && ' + ' '.join(cmd)
            subprocess.run(activate_cmd, shell=True, check=True)
        else:
            subprocess.run(cmd, check=True)
        
        print("✅ Started new Celery worker")
        time.sleep(3)
        return True
    except Exception as e:
        print(f"❌ Failed to start worker: {e}")
        print("   Try manually: celery -A app.tasks.celery_app worker --loglevel=info")
        return False

def test_fixed_integration():
    """Test if the fix worked"""
    print("\n4. Testing Fixed Integration...")
    
    try:
        from app.tasks.celery_app import celery_app
        from app.tasks.scan_tasks import quick_scan_task
        
        # Test simple task
        @celery_app.task
        def test_add(x, y):
            return x + y
        
        result = test_add.delay(5, 7)
        print(f"✅ Test task sent: {result.id}")
        
        # Wait for result
        for i in range(5):
            if result.ready():
                print(f"✅ Test result: {result.get()}")
                break
            time.sleep(1)
        
        # Test scan task
        scan_result = quick_scan_task.delay("scanme.nmap.org")
        print(f"✅ Scan task sent: {scan_result.id}")
        
        # Monitor scan
        for i in range(10):
            state = scan_result.state
            print(f"   Scan state: {state}")
            
            if state in ['SUCCESS', 'FAILURE']:
                print(f"✅ Scan finished with state: {state}")
                return True
            elif state == 'PROGRESS':
                info = scan_result.info or {}
                print(f"   Progress: {info.get('current', 0)}%")
            
            time.sleep(2)
        
        print("⚠️  Scan still pending after 20 seconds")
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_startup_script():
    """Create a startup script for easy launching"""
    print("\n5. Creating Startup Script...")
    
    script = """#!/bin/bash
# PHANTOM Security AI - Celery Worker Startup

echo "Starting PHANTOM Celery Worker..."

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Load environment
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start Celery worker
celery -A app.tasks.celery_app worker \\
    --loglevel=info \\
    --concurrency=4 \\
    --pool=prefork \\
    -n phantom_worker@%h \\
    -Q celery,scans,ai \\
    --max-tasks-per-child=100

echo "Celery worker stopped"
"""
    
    with open('start_celery.sh', 'w') as f:
        f.write(script)
    
    os.chmod('start_celery.sh', 0o755)
    print("✅ Created start_celery.sh")
    
    return True

def main():
    """Main fix process"""
    print("="*60)
    print("PHANTOM SECURITY AI - CELERY FIX")
    print("="*60)
    
    os.chdir('/Users/pedro/PHANTONSECURITY/phantom-security/backend')
    
    steps = [
        ("Environment Check", check_environment),
        ("Fix Celery Config", fix_celery_config),
        ("Restart Worker", restart_celery_worker),
        ("Test Integration", test_fixed_integration),
        ("Create Startup Script", create_startup_script)
    ]
    
    results = {}
    for step_name, step_func in steps:
        results[step_name] = step_func()
        if not results[step_name]:
            print(f"\n⚠️  Step '{step_name}' failed")
            break
    
    print("\n" + "="*60)
    print("FIX SUMMARY")
    print("="*60)
    
    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{step}: {status}")
    
    if all(results.values()):
        print("\n🎉 Celery integration fixed successfully!")
        print("\nNext steps:")
        print("1. Test via API: curl -X POST http://localhost:8000/api/scans/ -H 'Content-Type: application/json' -d '{\"target\":\"scanme.nmap.org\"}'")
        print("2. Monitor worker: tail -f celery.log")
        print("3. Check dashboard: http://localhost:3000")
    else:
        print("\n⚠️  Fix incomplete. Please check errors above.")
        print("\nManual steps:")
        print("1. Check Redis: redis-cli ping")
        print("2. Start worker manually: ./start_celery.sh")
        print("3. Check logs for errors")

if __name__ == "__main__":
    main()