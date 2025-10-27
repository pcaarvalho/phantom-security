#!/usr/bin/env python3
"""
PHANTOM Security AI - Main Entry Point
Direct command-line interface for running security scans
"""
import asyncio
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.scanner.orchestrator import PhantomBrain
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'phantom_scan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)

class PhantomCLI:
    """Command-line interface for PHANTOM Security Scanner"""
    
    def __init__(self):
        self.brain = PhantomBrain()
        
    async def run_scan(self, target: str, options: dict) -> dict:
        """Run a complete security scan"""
        scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║              PHANTOM SECURITY AI - RED TEAM ENGINE           ║
║                     Autonomous Vulnerability Scanner          ║
╚═══════════════════════════════════════════════════════════════╝

[*] Target: {target}
[*] Scan ID: {scan_id}
[*] Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
[*] Mode: {options.get('mode', 'comprehensive')}
        """)
        
        try:
            # Execute scan
            results = await self.brain.execute_full_scan(target, scan_id, options)
            
            # Print summary
            self._print_summary(results)
            
            # Save results
            if options.get('output'):
                self._save_results(results, options['output'])
                
            return results
            
        except Exception as e:
            logger.error(f"Scan failed: {str(e)}")
            print(f"\n[!] Scan failed: {str(e)}")
            return {"error": str(e)}
            
    def _print_summary(self, results: dict):
        """Print scan summary to console"""
        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                        SCAN COMPLETE                          ║
╚═══════════════════════════════════════════════════════════════╝

[+] Target: {results.get('target')}
[+] Duration: {results.get('duration_seconds', 0):.2f} seconds
[+] Risk Score: {results.get('risk_score', 0)}/100
[+] Vulnerabilities Found: {results.get('vulnerability_count', 0)}

═══ SUMMARY ═══
""")
        
        summary = results.get('summary', {})
        if summary:
            print(f"  • Open Ports: {summary.get('open_ports', 0)}")
            print(f"  • Critical Vulnerabilities: {summary.get('critical_vulnerabilities', 0)}")
            print(f"  • High Vulnerabilities: {summary.get('high_vulnerabilities', 0)}")
            print(f"  • Services Detected: {summary.get('services_detected', 0)}")
            print(f"  • Subdomains Found: {summary.get('subdomains_found', 0)}")
            print(f"  • Missing Security Headers: {summary.get('security_headers_missing', 0)}")
            
        # Print critical findings
        critical_findings = results.get('critical_findings', [])
        if critical_findings:
            print(f"\n═══ CRITICAL FINDINGS ═══")
            for i, finding in enumerate(critical_findings[:5], 1):
                print(f"\n  [{i}] {finding.get('template_name', 'Unknown')}")
                print(f"      Severity: {finding.get('severity', 'Unknown')}")
                print(f"      Location: {finding.get('matched_at', 'Unknown')}")
                if finding.get('description'):
                    print(f"      Description: {finding['description'][:100]}...")
                    
        # Print AI analysis if available
        ai_analysis = results.get('phases', {}).get('ai_analysis', {}).get('data', {})
        if ai_analysis and ai_analysis.get('executive_summary'):
            print(f"\n═══ AI ANALYSIS ═══")
            print(f"\n{ai_analysis['executive_summary']}")
            
        print(f"\n[+] Full results saved to output file (if specified)")
        print(f"[+] Log file: phantom_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
    def _save_results(self, results: dict, output_path: str):
        """Save scan results to file"""
        try:
            # Determine format from extension
            path = Path(output_path)
            
            if path.suffix == '.json':
                with open(output_path, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
            else:
                # Default to JSON with .json extension
                if not path.suffix:
                    output_path += '.json'
                with open(output_path, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                    
            print(f"\n[+] Results saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")
            print(f"\n[!] Failed to save results: {str(e)}")
            
    async def quick_scan(self, target: str) -> dict:
        """Run a quick scan (ports + basic vulns only)"""
        options = {
            'mode': 'quick',
            'skip_recon': True,
            'skip_exploits': True
        }
        return await self.run_scan(target, options)
        
    async def recon_only(self, target: str) -> dict:
        """Run reconnaissance only"""
        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                    RECONNAISSANCE MODE                        ║
╚═══════════════════════════════════════════════════════════════╝

[*] Target: {target}
[*] Gathering intelligence...
        """)
        
        from app.core.scanner.recon_engine import ReconEngine
        recon = ReconEngine(target)
        results = await recon.gather_intel()
        
        print(f"\n[+] Reconnaissance complete!")
        print(f"[+] Subdomains found: {len(results.get('subdomains', []))}")
        print(f"[+] Technologies detected: {len(results.get('technologies', []))}")
        
        if results.get('subdomains'):
            print(f"\n═══ SUBDOMAINS ═══")
            for subdomain in results['subdomains'][:10]:
                print(f"  • {subdomain}")
                
        return results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='PHANTOM Security AI - Autonomous Vulnerability Scanner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py example.com                    # Basic scan
  python run.py example.com -o report.json     # Save results to file
  python run.py example.com --quick            # Quick scan (faster)
  python run.py example.com --recon            # Reconnaissance only
  python run.py 192.168.1.1 --ports 1-1000    # Scan specific ports

DISCLAIMER: Only scan targets you own or have permission to test.
        """
    )
    
    parser.add_argument('target', help='Target domain or IP address')
    parser.add_argument('-o', '--output', help='Output file for results (JSON)')
    parser.add_argument('--quick', action='store_true', help='Quick scan mode (faster)')
    parser.add_argument('--recon', action='store_true', help='Reconnaissance only')
    parser.add_argument('--ports', help='Port range to scan (e.g., 1-1000)')
    parser.add_argument('--no-ai', action='store_true', help='Skip AI analysis')
    parser.add_argument('--no-exploits', action='store_true', help='Skip exploit generation')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Validate target
    if not args.target:
        print("[!] Error: Target is required")
        sys.exit(1)
        
    # Build options
    options = {
        'output': args.output,
        'port_range': args.ports,
        'skip_ai': args.no_ai,
        'skip_exploits': args.no_exploits
    }
    
    # Create CLI instance
    cli = PhantomCLI()
    
    # Run appropriate scan
    try:
        if args.recon:
            results = asyncio.run(cli.recon_only(args.target))
        elif args.quick:
            results = asyncio.run(cli.quick_scan(args.target))
        else:
            results = asyncio.run(cli.run_scan(args.target, options))
            
        # Save results if output specified
        if args.output and results:
            cli._save_results(results, args.output)
            
    except KeyboardInterrupt:
        print("\n\n[!] Scan interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Fatal error: {str(e)}")
        logger.exception("Fatal error occurred")
        sys.exit(1)
        
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║           PHANTOM Security AI - Scan Complete                 ║
║      Remember: Use findings responsibly and ethically         ║
╚═══════════════════════════════════════════════════════════════╝
    """)

if __name__ == "__main__":
    main()