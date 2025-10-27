#!/bin/bash

# PHANTOM Security AI - Stop Script
# Stops all backend services

echo "======================================================"
echo "  🛑 PHANTOM Security AI - Stopping Backend"
echo "======================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Stop FastAPI server
print_info "Stopping FastAPI server..."
pkill -f "uvicorn app.main:app" || true

# Stop Celery worker
print_info "Stopping Celery worker..."
pkill -f "celery.*app.tasks.celery_app worker" || true

# Wait for processes to terminate
sleep 3

# Check if processes are still running
UVICORN_COUNT=$(pgrep -f "uvicorn app.main:app" | wc -l)
CELERY_COUNT=$(pgrep -f "celery.*app.tasks.celery_app worker" | wc -l)

if [ $UVICORN_COUNT -eq 0 ] && [ $CELERY_COUNT -eq 0 ]; then
    print_status "All PHANTOM services stopped successfully"
else
    print_info "Force killing remaining processes..."
    pkill -9 -f "uvicorn app.main:app" || true
    pkill -9 -f "celery.*app.tasks.celery_app worker" || true
    print_status "Processes terminated"
fi

echo ""
echo "🎯 Services stopped. Backend is now offline."
echo "   To restart: ./start_phantom.sh"
echo ""