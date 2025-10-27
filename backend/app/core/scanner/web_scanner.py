import requests
import ssl
import socket
import asyncio
from urllib.parse import urlparse
from typing import Dict, List, Any
from app.core.scanner.base_scanner import BaseScanner

class WebScanner(BaseScanner):
    def __init__(self, target: str):
        super().__init__(target)
        self.timeout = 10
        self.user_agent = "PHANTOM Security Scanner 1.0"
    
    async def scan(self) -> Dict[str, Any]:
        """Perform web vulnerability scan"""
        if not self.validate_target():
            raise ValueError(f"Invalid target: {self.target}")
        
        self.start_time = asyncio.get_event_loop().time()
        
        try:
            # Ensure target has protocol
            if not self.target.startswith(('http://', 'https://')):
                self.target = f"https://{self.target}"
            
            # Run various web security checks
            tasks = [
                self._check_ssl_security(),
                self._check_security_headers(),
                self._check_common_files(),
                self._check_server_info(),
                self._check_cors_policy()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            self.results = {
                "target": self.target,
                "scan_type": "web_scan",
                "ssl_security": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
                "security_headers": results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
                "common_files": results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
                "server_info": results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])},
                "cors_policy": results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])}
            }
            
            self.end_time = asyncio.get_event_loop().time()
            return self.results
            
        except Exception as e:
            self.end_time = asyncio.get_event_loop().time()
            raise Exception(f"Web scan failed: {str(e)}")
    
    async def _check_ssl_security(self) -> Dict[str, Any]:
        """Check SSL/TLS security configuration"""
        if not self.target.startswith('https://'):
            return {"status": "not_applicable", "reason": "Not HTTPS"}
        
        try:
            parsed_url = urlparse(self.target)
            hostname = parsed_url.hostname
            port = parsed_url.port or 443
            
            # Get SSL certificate info
            context = ssl.create_default_context()
            
            loop = asyncio.get_event_loop()
            sock = await loop.run_in_executor(
                None,
                lambda: socket.create_connection((hostname, port), timeout=self.timeout)
            )
            
            ssock = context.wrap_socket(sock, server_hostname=hostname)
            cert = ssock.getpeercert()
            cipher = ssock.cipher()
            
            ssock.close()
            
            return {
                "status": "success",
                "certificate": {
                    "subject": dict(x[0] for x in cert.get('subject', [])),
                    "issuer": dict(x[0] for x in cert.get('issuer', [])),
                    "version": cert.get('version'),
                    "serial_number": cert.get('serialNumber'),
                    "not_before": cert.get('notBefore'),
                    "not_after": cert.get('notAfter'),
                    "subject_alt_names": cert.get('subjectAltName', [])
                },
                "cipher": {
                    "name": cipher[0] if cipher else None,
                    "version": cipher[1] if cipher else None,
                    "bits": cipher[2] if cipher else None
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def _check_security_headers(self) -> Dict[str, Any]:
        """Check for security headers"""
        try:
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    self.target,
                    timeout=self.timeout,
                    headers={'User-Agent': self.user_agent},
                    verify=False,
                    allow_redirects=False
                )
            )
            
            security_headers = [
                'Content-Security-Policy',
                'X-Content-Type-Options',
                'X-Frame-Options',
                'X-XSS-Protection',
                'Strict-Transport-Security',
                'Referrer-Policy',
                'Permissions-Policy',
                'X-Permitted-Cross-Domain-Policies'
            ]
            
            headers_status = {}
            missing_headers = []
            
            for header in security_headers:
                if header.lower() in [h.lower() for h in response.headers]:
                    headers_status[header] = response.headers.get(header)
                else:
                    missing_headers.append(header)
            
            return {
                "status": "success",
                "response_code": response.status_code,
                "present_headers": headers_status,
                "missing_headers": missing_headers,
                "server": response.headers.get('Server', 'Unknown'),
                "powered_by": response.headers.get('X-Powered-By', 'Unknown')
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def _check_common_files(self) -> Dict[str, Any]:
        """Check for common sensitive files"""
        common_files = [
            '/robots.txt',
            '/.htaccess',
            '/web.config',
            '/wp-config.php',
            '/.env',
            '/config.php',
            '/admin',
            '/administrator',
            '/backup',
            '/test',
            '/.git',
            '/.svn',
            '/sitemap.xml'
        ]
        
        findings = []
        
        try:
            loop = asyncio.get_event_loop()
            
            for file_path in common_files:
                try:
                    url = f"{self.target.rstrip('/')}{file_path}"
                    
                    response = await loop.run_in_executor(
                        None,
                        lambda: requests.get(
                            url,
                            timeout=5,
                            headers={'User-Agent': self.user_agent},
                            verify=False,
                            allow_redirects=False
                        )
                    )
                    
                    if response.status_code == 200:
                        findings.append({
                            "file": file_path,
                            "status_code": response.status_code,
                            "size": len(response.content),
                            "content_type": response.headers.get('Content-Type', 'unknown')
                        })
                    elif response.status_code == 403:
                        findings.append({
                            "file": file_path,
                            "status_code": response.status_code,
                            "note": "Forbidden - file might exist"
                        })
                        
                except requests.RequestException:
                    continue  # Skip files that cause request errors
            
            return {
                "status": "success",
                "files_found": findings,
                "total_found": len(findings)
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def _check_server_info(self) -> Dict[str, Any]:
        """Gather server information"""
        try:
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    self.target,
                    timeout=self.timeout,
                    headers={'User-Agent': self.user_agent},
                    verify=False
                )
            )
            
            return {
                "status": "success",
                "server": response.headers.get('Server', 'Unknown'),
                "powered_by": response.headers.get('X-Powered-By', 'Unknown'),
                "content_type": response.headers.get('Content-Type', 'Unknown'),
                "content_length": response.headers.get('Content-Length', 'Unknown'),
                "last_modified": response.headers.get('Last-Modified', 'Unknown'),
                "etag": response.headers.get('ETag', 'Unknown'),
                "response_time": response.elapsed.total_seconds(),
                "final_url": response.url
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def _check_cors_policy(self) -> Dict[str, Any]:
        """Check CORS configuration"""
        try:
            loop = asyncio.get_event_loop()
            
            # Test with a potentially dangerous origin
            test_origin = "https://evil.com"
            
            response = await loop.run_in_executor(
                None,
                lambda: requests.options(
                    self.target,
                    headers={
                        'Origin': test_origin,
                        'User-Agent': self.user_agent
                    },
                    timeout=self.timeout,
                    verify=False
                )
            )
            
            cors_headers = {
                'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
                'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
                'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials')
            }
            
            # Check for dangerous configurations
            issues = []
            
            if cors_headers['Access-Control-Allow-Origin'] == '*':
                issues.append("Wildcard (*) origin allowed")
            
            if cors_headers['Access-Control-Allow-Origin'] == test_origin:
                issues.append("Reflects any origin")
            
            if cors_headers['Access-Control-Allow-Credentials'] == 'true':
                issues.append("Credentials allowed with CORS")
            
            return {
                "status": "success",
                "headers": cors_headers,
                "potential_issues": issues
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}