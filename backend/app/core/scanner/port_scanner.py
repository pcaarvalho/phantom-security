import nmap
import asyncio
from typing import Dict, List, Any
from app.core.scanner.base_scanner import BaseScanner

class PortScanner(BaseScanner):
    def __init__(self, target: str, port_range: str = "1-1000"):
        super().__init__(target)
        self.port_range = port_range
        self.nm = nmap.PortScanner()
    
    async def scan(self) -> Dict[str, Any]:
        """Perform port scan using nmap"""
        if not self.validate_target():
            raise ValueError(f"Invalid target: {self.target}")
        
        self.start_time = asyncio.get_event_loop().time()
        
        try:
            # Run nmap scan in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._run_nmap_scan
            )
            
            self.end_time = asyncio.get_event_loop().time()
            return self.results
            
        except Exception as e:
            self.end_time = asyncio.get_event_loop().time()
            raise Exception(f"Port scan failed: {str(e)}")
    
    def _run_nmap_scan(self):
        """Run nmap scan synchronously"""
        try:
            # Clean target for nmap
            target = self.target.replace('http://', '').replace('https://', '').split('/')[0]
            
            # Perform TCP SYN scan with service detection
            self.nm.scan(
                target,
                self.port_range,
                arguments='-sS -sV -O --version-intensity 5'
            )
            
            self.results = {
                "target": target,
                "scan_type": "port_scan",
                "ports": self._parse_ports(),
                "host_info": self._parse_host_info(),
                "scan_stats": dict(self.nm.scanstats())
            }
            
        except Exception as e:
            self.results = {
                "target": self.target,
                "scan_type": "port_scan",
                "error": str(e),
                "ports": [],
                "host_info": {}
            }
    
    def _parse_ports(self) -> List[Dict[str, Any]]:
        """Parse open ports from nmap results"""
        ports = []
        
        for host in self.nm.all_hosts():
            host_ports = []
            
            for proto in self.nm[host].all_protocols():
                port_list = self.nm[host][proto].keys()
                
                for port in port_list:
                    port_info = self.nm[host][proto][port]
                    
                    if port_info['state'] == 'open':
                        host_ports.append({
                            'port': port,
                            'protocol': proto,
                            'state': port_info['state'],
                            'service': port_info.get('name', 'unknown'),
                            'version': port_info.get('version', ''),
                            'product': port_info.get('product', ''),
                            'extrainfo': port_info.get('extrainfo', ''),
                            'cpe': port_info.get('cpe', '')
                        })
            
            ports.extend(host_ports)
        
        return ports
    
    def _parse_host_info(self) -> Dict[str, Any]:
        """Parse host information from nmap results"""
        host_info = {}
        
        for host in self.nm.all_hosts():
            host_data = self.nm[host]
            
            host_info[host] = {
                'status': host_data.state(),
                'hostname': host_data.hostname(),
                'hostnames': list(host_data.hostnames()),
                'addresses': dict(host_data['addresses']),
                'vendor': host_data.get('vendor', {}),
                'os_info': self._parse_os_info(host_data)
            }
        
        return host_info
    
    def _parse_os_info(self, host_data) -> Dict[str, Any]:
        """Parse OS detection information"""
        os_info = {}
        
        if 'osmatch' in host_data:
            matches = []
            for osmatch in host_data['osmatch']:
                matches.append({
                    'name': osmatch['name'],
                    'accuracy': osmatch['accuracy'],
                    'line': osmatch['line']
                })
            os_info['matches'] = matches
        
        if 'osclass' in host_data:
            classes = []
            for osclass in host_data['osclass']:
                classes.append({
                    'type': osclass['type'],
                    'vendor': osclass['vendor'],
                    'osfamily': osclass['osfamily'],
                    'osgen': osclass['osgen'],
                    'accuracy': osclass['accuracy']
                })
            os_info['classes'] = classes
        
        return os_info