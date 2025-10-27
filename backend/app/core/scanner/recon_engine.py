"""
Reconnaissance Engine - OSINT and information gathering module
"""
import asyncio
import dns.resolver
import socket
import ssl
import subprocess
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import aiohttp
from urllib.parse import urlparse

from app.core.scanner.base_scanner import BaseScanner
from app.config import settings

logger = logging.getLogger(__name__)

class ReconEngine(BaseScanner):
    """
    Advanced reconnaissance engine for gathering intelligence about targets
    """
    
    def __init__(self, target: str):
        super().__init__(target)
        self.domain = self._extract_domain(target)
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 10
        
    def _extract_domain(self, target: str) -> str:
        """Extract clean domain from target"""
        # Remove protocol if present
        if '://' in target:
            target = target.split('://')[1]
        # Remove path if present
        if '/' in target:
            target = target.split('/')[0]
        # Remove port if present
        if ':' in target:
            target = target.split(':')[0]
        return target
        
    async def scan(self) -> Dict[str, Any]:
        """
        Main scan method (implements BaseScanner abstract method)
        """
        return await self.gather_intel()
    
    async def gather_intel(self) -> Dict[str, Any]:
        """
        Gather comprehensive intelligence about the target
        """
        logger.info(f"[RECON] Starting reconnaissance for {self.target}")
        
        results = {
            "target": self.target,
            "domain": self.domain,
            "timestamp": datetime.now().isoformat(),
            "dns": {},
            "subdomains": [],
            "whois": {},
            "ssl_info": {},
            "technologies": [],
            "emails": [],
            "social_media": [],
            "cloud_resources": [],
            "shodan_info": {}
        }
        
        # Run all recon tasks concurrently
        tasks = [
            self._gather_dns_records(),
            self._enumerate_subdomains(),
            self._get_whois_info(),
            self._get_ssl_certificate(),
            self._detect_technologies(),
            self._find_emails(),
            self._check_cloud_resources(),
            self._shodan_search() if settings.shodan_api_key else self._async_none()
        ]
        
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(gathered):
            if isinstance(result, Exception):
                logger.error(f"[RECON] Task {i} failed: {str(result)}")
                continue
                
            if i == 0 and result:  # DNS records
                results["dns"] = result
            elif i == 1 and result:  # Subdomains
                results["subdomains"] = result
            elif i == 2 and result:  # WHOIS
                results["whois"] = result
            elif i == 3 and result:  # SSL
                results["ssl_info"] = result
            elif i == 4 and result:  # Technologies
                results["technologies"] = result
            elif i == 5 and result:  # Emails
                results["emails"] = result
            elif i == 6 and result:  # Cloud resources
                results["cloud_resources"] = result
            elif i == 7 and result:  # Shodan
                results["shodan_info"] = result
                
        # Analyze findings for intelligence value
        results["intelligence_summary"] = self._analyze_intelligence(results)
        
        logger.info(f"[RECON] Reconnaissance completed for {self.target}")
        return results
        
    async def _gather_dns_records(self) -> Dict[str, Any]:
        """Gather all DNS records for the domain"""
        dns_records = {
            "A": [],
            "AAAA": [],
            "MX": [],
            "NS": [],
            "TXT": [],
            "CNAME": [],
            "SOA": None
        }
        
        record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]
        
        for record_type in record_types:
            try:
                answers = self.resolver.resolve(self.domain, record_type)
                for rdata in answers:
                    if record_type == "MX":
                        dns_records[record_type].append({
                            "priority": rdata.preference,
                            "host": str(rdata.exchange)
                        })
                    elif record_type == "SOA":
                        dns_records[record_type] = {
                            "mname": str(rdata.mname),
                            "rname": str(rdata.rname),
                            "serial": rdata.serial,
                            "refresh": rdata.refresh,
                            "retry": rdata.retry,
                            "expire": rdata.expire,
                            "minimum": rdata.minimum
                        }
                    else:
                        dns_records[record_type].append(str(rdata))
            except Exception as e:
                logger.debug(f"[RECON] No {record_type} records found: {str(e)}")
                
        return dns_records
        
    async def _enumerate_subdomains(self) -> List[str]:
        """Enumerate subdomains using multiple techniques"""
        subdomains = set()
        
        # Common subdomain wordlist
        common_subdomains = [
            "www", "mail", "ftp", "admin", "api", "app", "dev", "test", "staging",
            "blog", "shop", "store", "forum", "help", "support", "docs", "portal",
            "secure", "vpn", "remote", "cloud", "git", "jenkins", "gitlab",
            "m", "mobile", "wap", "beta", "demo", "qa", "uat", "cdn", "static",
            "assets", "images", "img", "media", "upload", "downloads", "files"
        ]
        
        # Check common subdomains
        tasks = []
        for subdomain in common_subdomains:
            full_domain = f"{subdomain}.{self.domain}"
            tasks.append(self._check_subdomain(full_domain))
            
        results = await asyncio.gather(*tasks)
        for domain, exists in results:
            if exists:
                subdomains.add(domain)
                
        # Try certificate transparency logs (passive)
        ct_subdomains = await self._query_certificate_transparency()
        subdomains.update(ct_subdomains)
        
        # DNS zone transfer attempt (usually fails but worth trying)
        zone_transfer = await self._attempt_zone_transfer()
        if zone_transfer:
            subdomains.update(zone_transfer)
            
        return list(subdomains)
        
    async def _check_subdomain(self, domain: str) -> tuple:
        """Check if a subdomain exists"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, socket.gethostbyname, domain
            )
            return (domain, True)
        except:
            return (domain, False)
            
    async def _query_certificate_transparency(self) -> List[str]:
        """Query certificate transparency logs for subdomains"""
        subdomains = set()
        
        try:
            # Query crt.sh for certificate transparency
            async with aiohttp.ClientSession() as session:
                url = f"https://crt.sh/?q=%.{self.domain}&output=json"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        for entry in data:
                            name = entry.get("name_value", "")
                            if name and "*" not in name:
                                # Extract all domains from the certificate
                                for domain in name.split('\n'):
                                    if domain and domain.endswith(self.domain):
                                        subdomains.add(domain)
        except Exception as e:
            logger.debug(f"[RECON] Certificate transparency query failed: {str(e)}")
            
        return list(subdomains)
        
    async def _attempt_zone_transfer(self) -> List[str]:
        """Attempt DNS zone transfer (AXFR)"""
        subdomains = []
        
        try:
            # Get NS records
            ns_records = self.resolver.resolve(self.domain, 'NS')
            
            for ns in ns_records:
                try:
                    # Attempt zone transfer
                    zone = dns.zone.from_xfr(
                        dns.query.xfr(str(ns), self.domain, timeout=5)
                    )
                    
                    for name, node in zone.nodes.items():
                        subdomain = str(name) + '.' + self.domain
                        if subdomain != self.domain:
                            subdomains.append(subdomain)
                            
                    logger.info(f"[RECON] Zone transfer successful from {ns}")
                    break  # If successful, no need to try other NS
                    
                except Exception:
                    continue  # Zone transfer failed, try next NS
                    
        except Exception as e:
            logger.debug(f"[RECON] Zone transfer attempt failed: {str(e)}")
            
        return subdomains
        
    async def _get_whois_info(self) -> Dict[str, Any]:
        """Get WHOIS information for the domain"""
        whois_info = {}
        
        try:
            # Run whois command
            result = subprocess.run(
                ["whois", self.domain],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                whois_text = result.stdout
                
                # Parse common WHOIS fields
                patterns = {
                    "registrar": r"Registrar:\s*(.+)",
                    "creation_date": r"Creation Date:\s*(.+)",
                    "expiration_date": r"Expir\w+ Date:\s*(.+)",
                    "updated_date": r"Updated Date:\s*(.+)",
                    "registrant": r"Registrant\s+(?:Name|Organization):\s*(.+)",
                    "registrant_email": r"Registrant Email:\s*(.+)",
                    "name_servers": r"Name Server:\s*(.+)"
                }
                
                for field, pattern in patterns.items():
                    matches = re.findall(pattern, whois_text, re.IGNORECASE)
                    if matches:
                        if field == "name_servers":
                            whois_info[field] = matches
                        else:
                            whois_info[field] = matches[0].strip()
                            
                # Store raw WHOIS for detailed analysis
                whois_info["raw"] = whois_text[:5000]  # Limit size
                
        except Exception as e:
            logger.error(f"[RECON] WHOIS lookup failed: {str(e)}")
            
        return whois_info
        
    async def _get_ssl_certificate(self) -> Dict[str, Any]:
        """Get SSL certificate information"""
        ssl_info = {}
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect and get certificate
            with socket.create_connection((self.domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Extract certificate information
                    ssl_info = {
                        "subject": dict(x[0] for x in cert.get('subject', [])),
                        "issuer": dict(x[0] for x in cert.get('issuer', [])),
                        "version": cert.get('version'),
                        "serial_number": cert.get('serialNumber'),
                        "not_before": cert.get('notBefore'),
                        "not_after": cert.get('notAfter'),
                        "signature_algorithm": cert.get('signatureAlgorithm'),
                        "san": []
                    }
                    
                    # Extract Subject Alternative Names
                    for ext in cert.get('subjectAltName', []):
                        if ext[0] == 'DNS':
                            ssl_info["san"].append(ext[1])
                            
                    # Check certificate validity
                    from datetime import datetime
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    ssl_info["days_until_expiry"] = (not_after - datetime.now()).days
                    ssl_info["is_expired"] = ssl_info["days_until_expiry"] < 0
                    
        except Exception as e:
            logger.error(f"[RECON] SSL certificate check failed: {str(e)}")
            ssl_info["error"] = str(e)
            
        return ssl_info
        
    async def _detect_technologies(self) -> List[Dict[str, Any]]:
        """Detect technologies used by the target"""
        technologies = []
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://{self.domain}" if not self.domain.startswith('http') else self.domain
                
                async with session.get(url, timeout=10, ssl=False) as response:
                    headers = dict(response.headers)
                    html = await response.text()
                    
                    # Detect from headers
                    if 'Server' in headers:
                        technologies.append({
                            "category": "Web Server",
                            "name": headers['Server'],
                            "confidence": "high"
                        })
                        
                    if 'X-Powered-By' in headers:
                        technologies.append({
                            "category": "Framework",
                            "name": headers['X-Powered-By'],
                            "confidence": "high"
                        })
                        
                    # Detect from HTML patterns
                    tech_patterns = {
                        "WordPress": r"wp-content|wordpress",
                        "Drupal": r"drupal|sites/default",
                        "Joomla": r"joomla|/components/com_",
                        "React": r"react|_react",
                        "Angular": r"ng-app|angular",
                        "Vue.js": r"vue\.js|v-if|v-for",
                        "jQuery": r"jquery|jQuery",
                        "Bootstrap": r"bootstrap\.css|bootstrap\.js",
                        "Cloudflare": r"cloudflare|cf-ray"
                    }
                    
                    for tech, pattern in tech_patterns.items():
                        if re.search(pattern, html, re.IGNORECASE):
                            technologies.append({
                                "category": "Technology",
                                "name": tech,
                                "confidence": "medium"
                            })
                            
        except Exception as e:
            logger.error(f"[RECON] Technology detection failed: {str(e)}")
            
        return technologies
        
    async def _find_emails(self) -> List[str]:
        """Find email addresses associated with the domain"""
        emails = set()
        
        # Extract from DNS TXT records (SPF, DMARC, etc.)
        try:
            txt_records = self.resolver.resolve(self.domain, 'TXT')
            for record in txt_records:
                text = str(record)
                # Find email patterns
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                found_emails = re.findall(email_pattern, text)
                emails.update(found_emails)
        except:
            pass
            
        # Check common email patterns
        common_emails = [
            f"admin@{self.domain}",
            f"info@{self.domain}",
            f"contact@{self.domain}",
            f"support@{self.domain}",
            f"webmaster@{self.domain}",
            f"postmaster@{self.domain}",
            f"abuse@{self.domain}",
            f"security@{self.domain}"
        ]
        
        # Note: In production, you might want to verify these
        # For now, we just note them as potential emails
        
        return list(emails)
        
    async def _check_cloud_resources(self) -> List[Dict[str, Any]]:
        """Check for cloud resources (S3 buckets, Azure blobs, etc.)"""
        cloud_resources = []
        
        # Check for S3 buckets
        s3_patterns = [
            f"{self.domain.replace('.', '-')}",
            f"{self.domain.replace('.', '')}",
            f"{self.domain.split('.')[0]}",
            f"www-{self.domain.replace('.', '-')}",
            f"assets-{self.domain.replace('.', '-')}",
            f"backup-{self.domain.replace('.', '-')}"
        ]
        
        for pattern in s3_patterns:
            # Check if S3 bucket exists (would need actual implementation)
            bucket_url = f"https://{pattern}.s3.amazonaws.com"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(bucket_url, timeout=5) as response:
                        if response.status in [200, 403]:  # 403 means exists but no access
                            cloud_resources.append({
                                "type": "AWS S3",
                                "resource": pattern,
                                "url": bucket_url,
                                "accessible": response.status == 200
                            })
            except:
                pass
                
        return cloud_resources
        
    async def _shodan_search(self) -> Dict[str, Any]:
        """Search Shodan for information about the target"""
        if not settings.shodan_api_key:
            return {}
            
        shodan_info = {}
        
        try:
            import shodan
            api = shodan.Shodan(settings.shodan_api_key)
            
            # Search for the IP/domain
            results = await asyncio.get_event_loop().run_in_executor(
                None, api.host, socket.gethostbyname(self.domain)
            )
            
            shodan_info = {
                "ip": results.get("ip_str"),
                "organization": results.get("org"),
                "operating_system": results.get("os"),
                "ports": results.get("ports", []),
                "vulnerabilities": results.get("vulns", []),
                "services": []
            }
            
            # Extract service information
            for service in results.get("data", []):
                shodan_info["services"].append({
                    "port": service.get("port"),
                    "service": service.get("product"),
                    "version": service.get("version"),
                    "banner": service.get("data", "")[:200]  # Limit banner size
                })
                
        except Exception as e:
            logger.error(f"[RECON] Shodan search failed: {str(e)}")
            
        return shodan_info
        
    async def _async_none(self) -> None:
        """Async function that returns None"""
        return None
        
    def _analyze_intelligence(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze gathered intelligence for actionable insights"""
        analysis = {
            "attack_surface": [],
            "potential_vulnerabilities": [],
            "security_posture": "unknown",
            "recommendations": []
        }
        
        # Analyze attack surface
        if results.get("subdomains"):
            analysis["attack_surface"].append(f"Found {len(results['subdomains'])} subdomains")
            
        if results.get("dns", {}).get("MX"):
            analysis["attack_surface"].append("Email services exposed")
            
        if results.get("cloud_resources"):
            analysis["attack_surface"].append(f"Found {len(results['cloud_resources'])} cloud resources")
            
        # Check for potential vulnerabilities
        ssl_info = results.get("ssl_info", {})
        if ssl_info.get("days_until_expiry", 100) < 30:
            analysis["potential_vulnerabilities"].append("SSL certificate expiring soon")
            
        if ssl_info.get("is_expired"):
            analysis["potential_vulnerabilities"].append("SSL certificate is expired")
            
        # Assess security posture
        if len(analysis["potential_vulnerabilities"]) > 3:
            analysis["security_posture"] = "poor"
        elif len(analysis["potential_vulnerabilities"]) > 1:
            analysis["security_posture"] = "moderate"
        else:
            analysis["security_posture"] = "good"
            
        # Generate recommendations
        if results.get("subdomains"):
            analysis["recommendations"].append("Review all subdomains for unnecessary exposure")
            
        if not ssl_info:
            analysis["recommendations"].append("Implement SSL/TLS encryption")
            
        return analysis