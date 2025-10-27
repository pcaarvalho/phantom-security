#!/usr/bin/env python3
"""
PHANTOM Security AI - Backend Setup Script
Configures and initializes the backend environment
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header():
    """Print setup header"""
    print("\n" + "="*60)
    print("PHANTOM Security AI - Backend Setup")
    print("="*60 + "\n")

def check_python():
    """Check Python version"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("❌ Python 3.11+ required. Current version: {}.{}.{}".format(
            version.major, version.minor, version.micro))
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def check_redis():
    """Check if Redis is installed"""
    print("\n🔍 Checking Redis...")
    try:
        result = subprocess.run(['redis-cli', 'ping'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Redis is running")
            return True
    except FileNotFoundError:
        pass
    
    print("⚠️  Redis not running. Please install and start Redis:")
    print("   Mac: brew install redis && brew services start redis")
    print("   Ubuntu: sudo apt-get install redis-server && sudo service redis-server start")
    print("   Docker: docker run -d -p 6379:6379 redis:alpine")
    return False

def check_postgresql():
    """Check if PostgreSQL is installed"""
    print("\n🔍 Checking PostgreSQL...")
    try:
        result = subprocess.run(['psql', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ PostgreSQL is installed")
            return True
    except FileNotFoundError:
        pass
    
    print("⚠️  PostgreSQL not found. Please install PostgreSQL:")
    print("   Mac: brew install postgresql && brew services start postgresql")
    print("   Ubuntu: sudo apt-get install postgresql postgresql-contrib")
    print("   Docker: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15")
    return False

def check_nmap():
    """Check if Nmap is installed"""
    print("\n🔍 Checking Nmap...")
    try:
        result = subprocess.run(['nmap', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Nmap is installed")
            return True
    except FileNotFoundError:
        pass
    
    print("⚠️  Nmap not found. Please install Nmap:")
    print("   Mac: brew install nmap")
    print("   Ubuntu: sudo apt-get install nmap")
    return False

def install_python_packages():
    """Install Python packages"""
    print("\n📦 Installing Python packages...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                      check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True)
        print("✅ Python packages installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install packages: {e}")
        return False

def setup_database():
    """Setup PostgreSQL database"""
    print("\n🗄️  Setting up database...")
    
    # Create database using Python
    try:
        import psycopg2
        from psycopg2 import sql
        
        # Connect to default database
        conn = psycopg2.connect(
            host="localhost",
            database="postgres",
            user=os.getenv("USER", "postgres"),
            password=""
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create user if not exists
        cursor.execute("""
            SELECT 1 FROM pg_user WHERE usename = 'phantom_user'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                CREATE USER phantom_user WITH PASSWORD 'phantom_password'
            """)
            print("✅ Created database user: phantom_user")
        
        # Create database if not exists
        cursor.execute("""
            SELECT 1 FROM pg_database WHERE datname = 'phantom_db'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                CREATE DATABASE phantom_db OWNER phantom_user
            """)
            print("✅ Created database: phantom_db")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"⚠️  Database setup failed: {e}")
        print("   Please create the database manually:")
        print("   psql -U postgres")
        print("   CREATE USER phantom_user WITH PASSWORD 'phantom_password';")
        print("   CREATE DATABASE phantom_db OWNER phantom_user;")
        return False

def run_migrations():
    """Run database migrations"""
    print("\n🔄 Running database migrations...")
    try:
        # Initialize Alembic if needed
        if not Path("alembic.ini").exists():
            subprocess.run(['alembic', 'init', 'alembic'], check=True)
        
        # Generate migration if needed
        subprocess.run(['alembic', 'revision', '--autogenerate', '-m', 'Initial migration'], 
                      check=False)
        
        # Run migrations
        subprocess.run(['alembic', 'upgrade', 'head'], check=True)
        print("✅ Database migrations completed")
        return True
    except subprocess.CalledProcessError:
        print("⚠️  Migration failed. Database tables will be created on first run.")
        return True

def create_env_file():
    """Create .env file if it doesn't exist"""
    env_file = Path(".env")
    if not env_file.exists():
        print("\n📝 Creating .env file...")
        subprocess.run(['cp', '.env.example', '.env'], check=True)
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env and add your API keys")
        return True
    else:
        print("\n✅ .env file already exists")
        return True

def test_backend():
    """Test backend startup"""
    print("\n🧪 Testing backend...")
    
    # Test import
    try:
        from app.main import app
        from app.config import settings
        print("✅ Backend modules imported successfully")
        
        # Test database connection
        from app.database import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        print("✅ Database connection successful")
        
        return True
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False

def print_next_steps():
    """Print next steps"""
    print("\n" + "="*60)
    print("✨ Setup Complete!")
    print("="*60)
    print("\n📋 Next Steps:\n")
    print("1. Edit .env file with your API keys:")
    print("   - Add your OpenAI API key")
    print("   - Verify database credentials")
    print("")
    print("2. Start Redis server:")
    print("   redis-server")
    print("")
    print("3. Start Celery worker:")
    print("   celery -A app.tasks.celery_app worker --loglevel=info")
    print("")
    print("4. Start FastAPI server:")
    print("   uvicorn app.main:app --reload --port 8000")
    print("")
    print("5. Access API documentation:")
    print("   http://localhost:8000/docs")
    print("")
    print("6. Test the API:")
    print("   curl http://localhost:8000/health")
    print("\n" + "="*60)

def main():
    """Main setup function"""
    print_header()
    
    # Check requirements
    checks = {
        "Python 3.11+": check_python(),
        "Redis": check_redis(),
        "PostgreSQL": check_postgresql(),
        "Nmap": check_nmap()
    }
    
    # Install packages
    if not install_python_packages():
        print("\n❌ Setup failed. Please fix the errors above.")
        return 1
    
    # Setup environment
    create_env_file()
    
    # Setup database if PostgreSQL is available
    if checks["PostgreSQL"]:
        setup_database()
        # run_migrations()
    
    # Test backend
    # test_backend()
    
    # Print summary
    print("\n📊 Setup Summary:")
    for component, status in checks.items():
        icon = "✅" if status else "⚠️"
        print(f"   {icon} {component}")
    
    print_next_steps()
    return 0

if __name__ == "__main__":
    sys.exit(main())