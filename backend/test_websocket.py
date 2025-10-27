#!/usr/bin/env python3
"""
Test WebSocket functionality
"""

import asyncio
import socketio
import sys
import json
from datetime import datetime

# Colors for terminal output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
WHITE = '\033[97m'
RESET = '\033[0m'


async def test_websocket():
    """Test WebSocket connection and events"""
    
    print(f"{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}🧪 PHANTOM Security WebSocket Test{RESET}")
    print(f"{CYAN}{'='*60}{RESET}\n")
    
    # Create Socket.IO client
    sio = socketio.AsyncClient()
    
    # Event handlers
    @sio.event
    async def connect():
        print(f"{GREEN}✅ Connected to WebSocket server{RESET}")
        print(f"   Session ID: {sio.sid}")
    
    @sio.event
    async def connected(data):
        print(f"{BLUE}📨 Received 'connected' event:{RESET}")
        print(f"   {json.dumps(data, indent=2)}")
    
    @sio.event
    async def disconnect():
        print(f"{YELLOW}❌ Disconnected from WebSocket server{RESET}")
    
    @sio.event
    async def scan_started(data):
        print(f"\n{GREEN}🚀 SCAN STARTED:{RESET}")
        print(f"   Target: {data.get('data', {}).get('target')}")
        print(f"   Scan ID: {data.get('scan_id')}")
    
    @sio.event
    async def scan_progress(data):
        progress = data.get('data', {}).get('progress', 0)
        phase = data.get('data', {}).get('phase', '')
        message = data.get('data', {}).get('message', '')
        
        # Create progress bar
        bar_length = 30
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"\r{CYAN}Progress: [{bar}] {progress}% - {message}{RESET}", end='')
        if progress == 100:
            print()  # New line at 100%
    
    @sio.event
    async def vulnerability_found(data):
        vuln = data.get('data', {})
        severity = vuln.get('severity', 'unknown')
        color = RED if severity == 'critical' else YELLOW if severity == 'high' else WHITE
        print(f"\n{color}⚠️  VULNERABILITY FOUND:{RESET}")
        print(f"   Name: {vuln.get('name', 'Unknown')}")
        print(f"   Severity: {severity.upper()}")
        print(f"   CVE: {vuln.get('cve', 'N/A')}")
    
    @sio.event
    async def critical_finding(data):
        print(f"\n{RED}🚨 CRITICAL FINDING:{RESET}")
        print(f"   {json.dumps(data.get('data', {}), indent=2)}")
    
    @sio.event
    async def scan_completed(data):
        results = data.get('data', {})
        print(f"\n{GREEN}✅ SCAN COMPLETED:{RESET}")
        print(f"   Risk Score: {results.get('risk_score', 0)}/100")
        print(f"   Vulnerabilities: {results.get('vulnerabilities_count', 0)}")
        print(f"   Critical Findings: {len(results.get('critical_findings', []))}")
    
    @sio.event
    async def scan_failed(data):
        print(f"\n{RED}❌ SCAN FAILED:{RESET}")
        print(f"   Error: {data.get('data', {}).get('error', 'Unknown error')}")
    
    @sio.event
    async def notification(data):
        notification = data.get('data', {})
        severity = data.get('severity', 'info')
        color = MAGENTA if severity == 'critical' else YELLOW if severity == 'high' else BLUE
        print(f"\n{color}📢 NOTIFICATION:{RESET}")
        print(f"   Title: {notification.get('title', '')}")
        print(f"   Message: {notification.get('message', '')}")
    
    try:
        # Connect to WebSocket server
        print(f"{BLUE}Connecting to ws://localhost:8000...{RESET}")
        await sio.connect('http://localhost:8000', socketio_path='/socket.io/')
        
        # Wait for connection
        await asyncio.sleep(1)
        
        # Subscribe to a test scan
        test_scan_id = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"\n{YELLOW}Subscribing to scan: {test_scan_id}{RESET}")
        await sio.emit('subscribe_scan', {'scan_id': test_scan_id})
        
        # Keep connection alive
        print(f"\n{CYAN}Listening for events... (Press Ctrl+C to stop){RESET}\n")
        
        # Test progress updates
        print(f"{YELLOW}You can now run a scan to see real-time updates:{RESET}")
        print(f"  python backend/run.py scanme.nmap.org --quick")
        print(f"  Or via API:")
        print(f'  curl -X POST http://localhost:8000/api/scans/ -H "Content-Type: application/json" -d \'{{"target": "scanme.nmap.org"}}\'')
        print()
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopping test...{RESET}")
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}")
    finally:
        await sio.disconnect()
        print(f"{GREEN}Test completed!{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted by user{RESET}")
        sys.exit(0)