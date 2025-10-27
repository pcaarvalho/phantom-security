#!/bin/bash

# PHANTOM Security AI - Complete Startup Script
# Starts all backend services in the correct order

set -e  # Exit on any error

echo "======================================================"
echo "  🚀 PHANTOM Security AI - Starting Backend"
echo "======================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Change to backend directory
cd "$(dirname "$0")/backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_warning "Python virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    print_status "Virtual environment created"
else
    source venv/bin/activate
    print_status "Virtual environment activated"
fi

# Check Redis
print_info "Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    print_status "Redis is running"
else
    print_warning "Redis not running. Starting Redis..."
    if command -v brew >/dev/null 2>&1; then
        brew services start redis
    else
        redis-server --daemonize yes
    fi
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        print_status "Redis started successfully"
    else
        print_error "Failed to start Redis"
        exit 1
    fi
fi

# Check PostgreSQL
print_info "Checking PostgreSQL..."
if pg_isready > /dev/null 2>&1; then
    print_status "PostgreSQL is running"
else
    print_warning "PostgreSQL not running. Please start it manually:"
    print_info "  brew services start postgresql (macOS)"
    print_info "  sudo service postgresql start (Linux)"
    print_info "Or use Docker: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15"
fi

# Initialize database
print_info "Initializing database..."
python init_db.py
if [ $? -eq 0 ]; then
    print_status "Database initialized"
else
    print_warning "Database initialization had issues"
fi

# Check .env file
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your API keys!"
    print_info "  - Add your OpenAI API key"
    print_info "  - Update database credentials if needed"
fi

# Kill any existing processes
print_info "Stopping any existing processes..."
pkill -f "uvicorn app.main:app" || true
pkill -f "celery.*app.tasks.celery_app worker" || true
sleep 2

# Start Celery worker in background
print_info "Starting Celery worker..."
celery -A app.tasks.celery_app worker --loglevel=info --detach
if [ $? -eq 0 ]; then
    print_status "Celery worker started"
else
    print_error "Failed to start Celery worker"
    exit 1
fi

# Start FastAPI server
print_info "Starting FastAPI server..."
uvicorn app.main:app --reload --port 8000 &
API_PID=$!

# Wait for server to start
print_info "Waiting for server to start..."
sleep 5

# Test API health
if curl -s http://localhost:8000/health > /dev/null; then
    print_status "API server is healthy"
else
    print_error "API server failed to start"
    kill $API_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "======================================================"
echo "  🎉 PHANTOM Security AI Backend Started Successfully!"
echo "======================================================"
echo ""
echo "📍 Service URLs:"
echo "   • API Server:        http://localhost:8000"
echo "   • API Documentation: http://localhost:8000/docs"
echo "   • Health Check:      http://localhost:8000/health"
echo ""
echo "🧪 Test Commands:"
echo "   • Test Engine:       python ../test_complete.py"
echo "   • API Test:          curl http://localhost:8000/health"
echo ""
echo "📊 Monitor Services:"
echo "   • View Logs:         tail -f /tmp/celery.log"
echo "   • Check Processes:   ps aux | grep -E '(uvicorn|celery)'"
echo ""
echo "🛑 Stop Services:"
echo "   • Stop All:          ./stop_phantom.sh"
echo "   • Or manually:       pkill -f 'uvicorn|celery'"
echo ""
echo "💡 Next Steps:"
echo "   1. Edit .env file with your OpenAI API key"
echo "   2. Test the engine: python ../test_complete.py"
echo "   3. Start the frontend from the frontend/ directory"
echo "   4. Access the dashboard at http://localhost:3000"
echo ""
echo "======================================================"

# Keep the script running
print_info "Backend is running. Press Ctrl+C to stop."
wait