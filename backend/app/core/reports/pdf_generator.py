"""
Professional PDF Report Generator for PHANTOM Security AI
"""
import io
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import tempfile
import base64

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white, red, orange, yellow, green
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

class PhantomPDFReport:
    """
    Professional security report generator for PHANTOM Security AI
    """
    
    # Corporate colors
    PHANTOM_DARK = HexColor('#1a1a2e')
    PHANTOM_PURPLE = HexColor('#16213e') 
    PHANTOM_BLUE = HexColor('#0f3460')
    PHANTOM_ACCENT = HexColor('#e94560')
    PHANTOM_TEXT = HexColor('#f5f5f5')
    
    # Risk colors
    RISK_CRITICAL = HexColor('#dc2626')
    RISK_HIGH = HexColor('#ea580c')
    RISK_MEDIUM = HexColor('#d97706')
    RISK_LOW = HexColor('#16a34a')
    RISK_INFO = HexColor('#6b7280')

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='PhantomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=self.PHANTOM_ACCENT,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Heading styles
        self.styles.add(ParagraphStyle(
            name='PhantomHeading1',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceBefore=20,
            spaceAfter=12,
            textColor=self.PHANTOM_PURPLE,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='PhantomHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=8,
            textColor=self.PHANTOM_BLUE,
            fontName='Helvetica-Bold'
        ))
        
        # Custom body styles
        self.styles.add(ParagraphStyle(
            name='PhantomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            textColor=black,
            fontName='Helvetica'
        ))
        
        self.styles.add(ParagraphStyle(
            name='PhantomCode',
            parent=self.styles['Code'],
            fontSize=9,
            textColor=self.PHANTOM_DARK,
            backColor=HexColor('#f8f9fa'),
            borderColor=HexColor('#dee2e6'),
            borderWidth=1,
            leftIndent=10,
            rightIndent=10,
            spaceBefore=5,
            spaceAfter=5,
        ))

    def generate_report(self, scan_data: Dict[str, Any], output_path: str = None) -> bytes:
        """
        Generate comprehensive PDF security report
        """
        # Create PDF buffer
        if output_path:
            buffer = open(output_path, 'wb')
        else:
            buffer = io.BytesIO()
            
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Build story (content)
        story = []
        
        # Cover page
        story.extend(self._build_cover_page(scan_data))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._build_executive_summary(scan_data))
        story.append(PageBreak())
        
        # Scan overview
        story.extend(self._build_scan_overview(scan_data))
        story.append(PageBreak())
        
        # Vulnerability details
        if scan_data.get('vulnerabilities'):
            story.extend(self._build_vulnerability_details(scan_data))
            story.append(PageBreak())
        
        # Risk analysis
        story.extend(self._build_risk_analysis(scan_data))
        story.append(PageBreak())
        
        # Recommendations
        story.extend(self._build_recommendations(scan_data))
        story.append(PageBreak())
        
        # Technical details
        story.extend(self._build_technical_details(scan_data))
        
        # Appendices
        story.append(PageBreak())
        story.extend(self._build_appendices(scan_data))
        
        # Build PDF
        doc.build(story)
        
        if output_path:
            buffer.close()
            with open(output_path, 'rb') as f:
                return f.read()
        else:
            pdf_data = buffer.getvalue()
            buffer.close()
            return pdf_data

    def _build_cover_page(self, scan_data: Dict[str, Any]) -> List:
        """Build professional cover page"""
        story = []
        
        # Title
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph("PHANTOM SECURITY AI", self.styles['PhantomTitle']))
        story.append(Paragraph("Vulnerability Assessment Report", self.styles['Heading1']))
        story.append(Spacer(1, inch))
        
        # Target info
        target = scan_data.get('target', 'Unknown Target')
        story.append(Paragraph(f"<b>Target:</b> {target}", self.styles['PhantomBody']))
        
        scan_date = scan_data.get('completed_at') or scan_data.get('created_at', datetime.now().isoformat())
        if isinstance(scan_date, str):
            try:
                scan_date = datetime.fromisoformat(scan_date.replace('Z', '+00:00'))
            except:
                scan_date = datetime.now()
        
        story.append(Paragraph(f"<b>Scan Date:</b> {scan_date.strftime('%B %d, %Y')}", self.styles['PhantomBody']))
        story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", self.styles['PhantomBody']))
        
        story.append(Spacer(1, inch))
        
        # Risk score display
        risk_score = scan_data.get('risk_score', 0)
        risk_level = self._get_risk_level(risk_score)
        risk_color = self._get_risk_color(risk_score)
        
        # Create risk score table
        risk_data = [
            ['Overall Risk Score', f'{risk_score}/100'],
            ['Risk Level', risk_level],
            ['Vulnerabilities Found', str(scan_data.get('vulnerability_count', 0))]
        ]
        
        risk_table = Table(risk_data, colWidths=[3*inch, 2*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.PHANTOM_PURPLE),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(risk_table)
        story.append(Spacer(1, inch))
        
        # Classification
        story.append(Paragraph("<b>CONFIDENTIAL</b>", 
                             ParagraphStyle('Classification', 
                                          parent=self.styles['PhantomBody'],
                                          alignment=TA_CENTER,
                                          fontSize=16,
                                          textColor=self.PHANTOM_ACCENT)))
        
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("This report contains sensitive security information and should be treated as confidential.", 
                             self.styles['PhantomBody']))
        
        return story

    def _build_executive_summary(self, scan_data: Dict[str, Any]) -> List:
        """Build executive summary section"""
        story = []
        
        story.append(Paragraph("Executive Summary", self.styles['PhantomHeading1']))
        
        # AI Analysis summary
        ai_analysis = scan_data.get('ai_analysis', {})
        executive_summary = ai_analysis.get('executive_summary', '')
        
        if executive_summary:
            story.append(Paragraph(executive_summary, self.styles['PhantomBody']))
        else:
            # Generate basic summary
            target = scan_data.get('target', 'the target system')
            vuln_count = scan_data.get('vulnerability_count', 0)
            risk_score = scan_data.get('risk_score', 0)
            
            summary = f"""
            PHANTOM Security AI conducted a comprehensive vulnerability assessment of {target}. 
            The scan identified {vuln_count} vulnerabilities with an overall risk score of {risk_score}/100.
            
            {self._generate_risk_statement(risk_score, vuln_count)}
            """
            story.append(Paragraph(summary, self.styles['PhantomBody']))
        
        story.append(Spacer(1, 12))
        
        # Key findings
        story.append(Paragraph("Key Findings", self.styles['PhantomHeading2']))
        
        # Critical findings
        critical_findings = scan_data.get('critical_findings', [])
        if critical_findings:
            story.append(Paragraph("Critical Issues:", self.styles['PhantomBody']))
            for i, finding in enumerate(critical_findings[:5], 1):
                finding_text = f"• {finding.get('template_name', 'Security Issue')}"
                if finding.get('severity'):
                    finding_text += f" ({finding['severity']})"
                story.append(Paragraph(finding_text, self.styles['PhantomBody']))
        
        return story

    def _build_scan_overview(self, scan_data: Dict[str, Any]) -> List:
        """Build scan overview section"""
        story = []
        
        story.append(Paragraph("Scan Overview", self.styles['PhantomHeading1']))
        
        # Scan details table
        scan_info = [
            ['Target', scan_data.get('target', 'N/A')],
            ['Scan Type', scan_data.get('scan_type', 'Comprehensive')],
            ['Scan Duration', f"{scan_data.get('duration_seconds', 0):.1f} seconds"],
            ['Started', self._format_datetime(scan_data.get('started_at'))],
            ['Completed', self._format_datetime(scan_data.get('completed_at'))],
        ]
        
        scan_table = Table(scan_info, colWidths=[2*inch, 4*inch])
        scan_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), HexColor('#f8f9fa')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(scan_table)
        story.append(Spacer(1, 12))
        
        # Summary statistics
        story.append(Paragraph("Scan Results Summary", self.styles['PhantomHeading2']))
        
        summary_data = scan_data.get('summary', {})
        phases = scan_data.get('phases', {})
        
        # Create summary statistics
        stats_data = [
            ['Metric', 'Count', 'Details'],
            ['Total Vulnerabilities', str(scan_data.get('vulnerability_count', 0)), ''],
            ['Risk Score', f"{scan_data.get('risk_score', 0)}/100", self._get_risk_level(scan_data.get('risk_score', 0))],
            ['Critical Issues', str(summary_data.get('critical_count', 0)), 'Immediate attention required'],
            ['High Priority Issues', str(summary_data.get('high_count', 0)), 'Address within 24-48 hours'],
            ['Scan Phases Completed', str(len(phases)), 'Comprehensive analysis performed']
        ]
        
        stats_table = Table(stats_data, colWidths=[2.5*inch, 1*inch, 2.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.PHANTOM_PURPLE),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALTERNATEBACKGROUNDCOLOR', (0, 1), (-1, -1), HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(stats_table)
        
        return story

    def _build_vulnerability_details(self, scan_data: Dict[str, Any]) -> List:
        """Build detailed vulnerability section"""
        story = []
        
        story.append(Paragraph("Vulnerability Details", self.styles['PhantomHeading1']))
        
        vulnerabilities = scan_data.get('vulnerabilities', [])
        if not vulnerabilities:
            story.append(Paragraph("No vulnerabilities were identified during the scan.", 
                                 self.styles['PhantomBody']))
            return story
        
        # Group by severity
        severity_groups = {}
        for vuln in vulnerabilities:
            severity = vuln.get('severity', 'UNKNOWN').upper()
            if severity not in severity_groups:
                severity_groups[severity] = []
            severity_groups[severity].append(vuln)
        
        # Process each severity level
        severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
        
        for severity in severity_order:
            if severity not in severity_groups:
                continue
                
            vulns = severity_groups[severity]
            story.append(Paragraph(f"{severity.capitalize()} Vulnerabilities ({len(vulns)})", 
                                 self.styles['PhantomHeading2']))
            
            for i, vuln in enumerate(vulns[:10], 1):  # Limit to top 10 per severity
                story.extend(self._format_vulnerability(vuln, i))
                story.append(Spacer(1, 8))
        
        return story

    def _format_vulnerability(self, vuln: Dict[str, Any], index: int) -> List:
        """Format a single vulnerability entry"""
        story = []
        
        # Vulnerability header
        title = vuln.get('template_name', f'Vulnerability #{index}')
        severity = vuln.get('severity', 'UNKNOWN')
        
        header_text = f"<b>{index}. {title}</b> [{severity}]"
        story.append(Paragraph(header_text, self.styles['PhantomBody']))
        
        # Details table
        details = [
            ['Location', vuln.get('matched_at', 'N/A')],
            ['Description', vuln.get('description', 'No description available')[:200] + '...'],
            ['CVE ID', ', '.join(vuln.get('cve_id', [])) or 'N/A'],
            ['Impact', vuln.get('impact', 'Under assessment')]
        ]
        
        details_table = Table(details, colWidths=[1.5*inch, 4.5*inch])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), HexColor('#f8f9fa')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(details_table)
        
        # Remediation
        if vuln.get('remediation'):
            story.append(Paragraph("<b>Remediation:</b>", self.styles['PhantomBody']))
            story.append(Paragraph(vuln['remediation'][:300] + '...', self.styles['PhantomCode']))
        
        return story

    def _build_risk_analysis(self, scan_data: Dict[str, Any]) -> List:
        """Build risk analysis section"""
        story = []
        
        story.append(Paragraph("Risk Analysis", self.styles['PhantomHeading1']))
        
        risk_score = scan_data.get('risk_score', 0)
        
        # Risk assessment
        story.append(Paragraph("Overall Risk Assessment", self.styles['PhantomHeading2']))
        
        risk_text = self._generate_detailed_risk_analysis(scan_data)
        story.append(Paragraph(risk_text, self.styles['PhantomBody']))
        
        story.append(Spacer(1, 12))
        
        # Risk breakdown
        story.append(Paragraph("Risk Breakdown", self.styles['PhantomHeading2']))
        
        # Create risk matrix
        vulnerabilities = scan_data.get('vulnerabilities', [])
        risk_counts = self._calculate_risk_distribution(vulnerabilities)
        
        risk_data = [
            ['Risk Level', 'Count', 'Percentage', 'Action Required'],
            ['Critical', str(risk_counts.get('CRITICAL', 0)), 
             f"{(risk_counts.get('CRITICAL', 0)/max(len(vulnerabilities), 1)*100):.1f}%", 
             'Immediate action required'],
            ['High', str(risk_counts.get('HIGH', 0)), 
             f"{(risk_counts.get('HIGH', 0)/max(len(vulnerabilities), 1)*100):.1f}%", 
             'Address within 24-48 hours'],
            ['Medium', str(risk_counts.get('MEDIUM', 0)), 
             f"{(risk_counts.get('MEDIUM', 0)/max(len(vulnerabilities), 1)*100):.1f}%", 
             'Address within 1 week'],
            ['Low', str(risk_counts.get('LOW', 0)), 
             f"{(risk_counts.get('LOW', 0)/max(len(vulnerabilities), 1)*100):.1f}%", 
             'Address as time permits']
        ]
        
        risk_table = Table(risk_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 2*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.PHANTOM_PURPLE),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALTERNATEBACKGROUNDCOLOR', (0, 1), (-1, -1), HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(risk_table)
        
        return story

    def _build_recommendations(self, scan_data: Dict[str, Any]) -> List:
        """Build recommendations section"""
        story = []
        
        story.append(Paragraph("Recommendations", self.styles['PhantomHeading1']))
        
        ai_analysis = scan_data.get('ai_analysis', {})
        recommendations = ai_analysis.get('recommendations', [])
        
        if not recommendations:
            recommendations = self._generate_default_recommendations(scan_data)
        
        story.append(Paragraph("Priority Recommendations", self.styles['PhantomHeading2']))
        
        for i, rec in enumerate(recommendations[:10], 1):
            rec_text = f"<b>{i}.</b> {rec}"
            story.append(Paragraph(rec_text, self.styles['PhantomBody']))
            story.append(Spacer(1, 6))
        
        story.append(Spacer(1, 12))
        
        # Implementation timeline
        story.append(Paragraph("Suggested Implementation Timeline", self.styles['PhantomHeading2']))
        
        timeline_data = [
            ['Priority', 'Timeframe', 'Actions'],
            ['Immediate (0-24 hours)', 'Critical', 'Address critical vulnerabilities, patch exposed services'],
            ['Short-term (1-7 days)', 'High', 'Implement security controls, update configurations'],
            ['Medium-term (1-4 weeks)', 'Medium', 'Deploy monitoring, review access controls'],
            ['Long-term (1-3 months)', 'Low/Info', 'Security awareness training, policy updates']
        ]
        
        timeline_table = Table(timeline_data, colWidths=[2*inch, 1.5*inch, 2.5*inch])
        timeline_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.PHANTOM_PURPLE),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALTERNATEBACKGROUNDCOLOR', (0, 1), (-1, -1), HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(timeline_table)
        
        return story

    def _build_technical_details(self, scan_data: Dict[str, Any]) -> List:
        """Build technical details section"""
        story = []
        
        story.append(Paragraph("Technical Details", self.styles['PhantomHeading1']))
        
        # Scan phases
        phases = scan_data.get('phases', {})
        if phases:
            story.append(Paragraph("Scan Phases Executed", self.styles['PhantomHeading2']))
            
            for phase_name, phase_data in phases.items():
                phase_title = phase_name.replace('_', ' ').title()
                story.append(Paragraph(f"<b>{phase_title}</b>", self.styles['PhantomBody']))
                
                phase_info = phase_data.get('data', {})
                if isinstance(phase_info, dict):
                    # Display key metrics from the phase
                    for key, value in list(phase_info.items())[:5]:  # Limit display
                        if isinstance(value, (str, int, float)):
                            story.append(Paragraph(f"  • {key}: {value}", self.styles['PhantomBody']))
                
                story.append(Spacer(1, 6))
        
        return story

    def _build_appendices(self, scan_data: Dict[str, Any]) -> List:
        """Build appendices section"""
        story = []
        
        story.append(Paragraph("Appendices", self.styles['PhantomHeading1']))
        
        # Methodology
        story.append(Paragraph("A. Methodology", self.styles['PhantomHeading2']))
        methodology_text = """
        PHANTOM Security AI employs a multi-phase approach to vulnerability assessment:
        
        1. Reconnaissance: Passive information gathering about the target
        2. Port Scanning: Active discovery of open services and ports  
        3. Web Application Testing: Analysis of web-specific vulnerabilities
        4. Vulnerability Detection: Comprehensive vulnerability scanning using Nuclei templates
        5. AI Analysis: Intelligent threat analysis and risk scoring using GPT-4
        6. Exploit Generation: Creation of proof-of-concept exploits for validation
        """
        story.append(Paragraph(methodology_text, self.styles['PhantomBody']))
        
        story.append(Spacer(1, 12))
        
        # Disclaimer
        story.append(Paragraph("B. Disclaimer", self.styles['PhantomHeading2']))
        disclaimer_text = """
        This security assessment was conducted using automated tools and AI analysis. While comprehensive,
        it may not identify all possible vulnerabilities. Manual verification is recommended for critical
        systems. This report is intended for the exclusive use of the organization that commissioned it.
        
        PHANTOM Security AI is designed for defensive security purposes only. Any findings should be
        addressed through proper security controls and remediation procedures.
        """
        story.append(Paragraph(disclaimer_text, self.styles['PhantomBody']))
        
        return story

    # Helper methods
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level from score"""
        if risk_score >= 80:
            return "CRITICAL"
        elif risk_score >= 60:
            return "HIGH"
        elif risk_score >= 40:
            return "MEDIUM"
        elif risk_score >= 20:
            return "LOW"
        else:
            return "MINIMAL"

    def _get_risk_color(self, risk_score: int) -> HexColor:
        """Get color for risk score"""
        if risk_score >= 80:
            return self.RISK_CRITICAL
        elif risk_score >= 60:
            return self.RISK_HIGH
        elif risk_score >= 40:
            return self.RISK_MEDIUM
        elif risk_score >= 20:
            return self.RISK_LOW
        else:
            return self.RISK_INFO

    def _format_datetime(self, dt_str: str) -> str:
        """Format datetime string"""
        if not dt_str:
            return "N/A"
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return dt_str

    def _generate_risk_statement(self, risk_score: int, vuln_count: int) -> str:
        """Generate risk statement based on score and vulnerabilities"""
        if risk_score >= 80:
            return f"The assessment reveals critical security concerns that require immediate attention. With {vuln_count} vulnerabilities identified, urgent remediation is essential."
        elif risk_score >= 60:
            return f"The target exhibits high-risk security issues with {vuln_count} vulnerabilities discovered. Prompt action is recommended within 24-48 hours."
        elif risk_score >= 40:
            return f"Moderate security risks were identified with {vuln_count} vulnerabilities found. These should be addressed within the next week."
        elif risk_score >= 20:
            return f"Low-level security issues were discovered with {vuln_count} vulnerabilities. These can be addressed as time permits."
        else:
            return f"The security posture appears strong with minimal issues identified ({vuln_count} findings)."

    def _generate_detailed_risk_analysis(self, scan_data: Dict[str, Any]) -> str:
        """Generate detailed risk analysis"""
        risk_score = scan_data.get('risk_score', 0)
        vulnerabilities = scan_data.get('vulnerabilities', [])
        
        critical_count = len([v for v in vulnerabilities if v.get('severity') == 'CRITICAL'])
        high_count = len([v for v in vulnerabilities if v.get('severity') == 'HIGH'])
        
        analysis = f"The overall risk score of {risk_score}/100 is derived from comprehensive analysis of {len(vulnerabilities)} identified security issues. "
        
        if critical_count > 0:
            analysis += f"Of particular concern are {critical_count} critical vulnerabilities that could lead to complete system compromise. "
        
        if high_count > 0:
            analysis += f"Additionally, {high_count} high-severity issues present significant security risks. "
        
        analysis += "This assessment recommends prioritizing remediation efforts based on severity and potential impact to business operations."
        
        return analysis

    def _calculate_risk_distribution(self, vulnerabilities: List[Dict]) -> Dict[str, int]:
        """Calculate distribution of vulnerabilities by risk level"""
        distribution = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'INFO': 0}
        
        for vuln in vulnerabilities:
            severity = vuln.get('severity', 'INFO').upper()
            if severity in distribution:
                distribution[severity] += 1
        
        return distribution

    def _generate_default_recommendations(self, scan_data: Dict[str, Any]) -> List[str]:
        """Generate default recommendations when AI analysis is not available"""
        recommendations = [
            "Implement a comprehensive patch management program to address identified vulnerabilities",
            "Deploy a Web Application Firewall (WAF) to protect against common web attacks",
            "Conduct regular security awareness training for all personnel",
            "Implement network segmentation to limit the impact of potential breaches",
            "Establish continuous security monitoring and incident response procedures",
            "Review and strengthen access controls and authentication mechanisms",
            "Conduct penetration testing at least annually to validate security controls",
            "Implement automated vulnerability scanning on a regular schedule",
            "Develop and test incident response and business continuity plans",
            "Review and update security policies and procedures regularly"
        ]
        
        return recommendations


class ReportGenerator:
    """
    Main interface for generating security reports
    """
    
    def __init__(self):
        self.pdf_generator = PhantomPDFReport()
        
    async def generate_pdf_report(self, scan_data: Dict[str, Any], output_path: str = None) -> bytes:
        """
        Generate PDF report from scan data
        """
        try:
            logger.info(f"Generating PDF report for scan {scan_data.get('target', 'unknown')}")
            
            # Process scan data for report
            report_data = self._prepare_report_data(scan_data)
            
            # Generate PDF
            pdf_data = self.pdf_generator.generate_report(report_data, output_path)
            
            logger.info("PDF report generated successfully")
            return pdf_data
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            raise Exception(f"Report generation failed: {str(e)}")
    
    def _prepare_report_data(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare and normalize scan data for report generation
        """
        # Extract scan results if nested
        if 'scan_results' in scan_data and isinstance(scan_data['scan_results'], dict):
            # Merge scan_results into main data
            results = scan_data['scan_results']
            report_data = {**scan_data, **results}
        else:
            report_data = scan_data.copy()
        
        # Extract vulnerabilities from phases if needed
        if 'vulnerabilities' not in report_data:
            phases = report_data.get('phases', {})
            vulnerabilities = []
            
            # Check vulnerability scan phase
            if 'vulnerability_scan' in phases:
                vuln_data = phases['vulnerability_scan'].get('data', {})
                vulnerabilities.extend(vuln_data.get('vulnerabilities', []))
            
            report_data['vulnerabilities'] = vulnerabilities
        
        # Extract critical findings
        if 'critical_findings' not in report_data:
            vulnerabilities = report_data.get('vulnerabilities', [])
            critical_findings = [
                v for v in vulnerabilities 
                if v.get('severity', '').upper() in ['CRITICAL', 'HIGH']
            ]
            report_data['critical_findings'] = critical_findings[:10]
        
        return report_data