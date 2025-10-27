import os
import tempfile
from datetime import datetime
from typing import Dict, List, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, red, orange, yellow, green
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

class PHANTOMReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Setup custom styles for the report"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=HexColor('#8B5CF6'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        
        # Executive summary style
        self.styles.add(ParagraphStyle(
            name='ExecutiveSummary',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=12
        ))
        
        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=HexColor('#1F2937'),
            spaceBefore=20,
            spaceAfter=10
        ))
        
        # Subsection heading
        self.styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=HexColor('#374151'),
            spaceBefore=15,
            spaceAfter=8
        ))
        
        # Risk styles
        for risk, color in [('Critical', '#DC2626'), ('High', '#EA580C'), 
                           ('Medium', '#D97706'), ('Low', '#16A34A')]:
            self.styles.add(ParagraphStyle(
                name=f'Risk{risk}',
                parent=self.styles['Normal'],
                textColor=HexColor(color),
                fontSize=10,
                alignment=TA_CENTER
            ))

    def generate_report(self, scan_data: Dict[str, Any]) -> str:
        """Generate PDF security report"""
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_path = temp_file.name
        temp_file.close()
        
        # Create document
        doc = SimpleDocTemplate(
            temp_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Build content
        story = []
        story.extend(self._build_cover_page(scan_data))
        story.append(PageBreak())
        story.extend(self._build_executive_summary(scan_data))
        story.append(PageBreak())
        story.extend(self._build_vulnerability_overview(scan_data))
        story.append(PageBreak())
        story.extend(self._build_detailed_findings(scan_data))
        story.append(PageBreak())
        story.extend(self._build_recommendations(scan_data))
        story.append(PageBreak())
        story.extend(self._build_technical_appendix(scan_data))
        
        # Build PDF
        doc.build(story)
        
        return temp_path

    def _build_cover_page(self, scan_data: Dict[str, Any]) -> List:
        """Build report cover page"""
        elements = []
        
        # Title
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("PHANTOM Security AI", self.styles['CustomTitle']))
        elements.append(Paragraph("Vulnerability Assessment Report", self.styles['Title']))
        
        elements.append(Spacer(1, 1*inch))
        
        # Target information
        target = scan_data.get('target', 'Unknown')
        scan_date = datetime.now().strftime('%B %d, %Y')
        
        info_data = [
            ['Target:', target],
            ['Scan Date:', scan_date],
            ['Report Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
            ['Scan Type:', 'Comprehensive Security Assessment'],
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 2*inch))
        
        # Risk score summary
        ai_analysis = scan_data.get('ai_analysis', {})
        risk_score = ai_analysis.get('risk_score', 0)
        risk_level = self._get_risk_level(risk_score)
        
        risk_color = self._get_risk_color(risk_level)
        
        elements.append(Paragraph("Overall Risk Assessment", self.styles['SectionHeading']))
        
        risk_data = [
            ['Risk Score:', f'{risk_score}/100'],
            ['Risk Level:', risk_level],
            ['Vulnerabilities Found:', scan_data.get('vulnerability_count', 0)],
        ]
        
        risk_table = Table(risk_data, colWidths=[2*inch, 2*inch])
        risk_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TEXTCOLOR', (1, 1), (1, 1), HexColor(risk_color)),
            ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(risk_table)
        
        return elements

    def _build_executive_summary(self, scan_data: Dict[str, Any]) -> List:
        """Build executive summary section"""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['CustomTitle']))
        
        ai_analysis = scan_data.get('ai_analysis', {})
        executive_summary = ai_analysis.get('executive_summary', 
                                          'Security assessment completed. Detailed analysis requires AI integration.')
        
        elements.append(Paragraph(executive_summary, self.styles['ExecutiveSummary']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Key metrics
        elements.append(Paragraph("Key Findings", self.styles['SectionHeading']))
        
        vulnerability_summary = scan_data.get('vulnerability_summary', {})
        metrics_data = [
            ['Total Vulnerabilities:', str(vulnerability_summary.get('total_vulnerabilities', 0))],
            ['Open Ports:', str(vulnerability_summary.get('open_ports', 0))],
            ['Missing Security Headers:', str(vulnerability_summary.get('missing_security_headers', 0))],
            ['SSL Issues:', 'Yes' if vulnerability_summary.get('ssl_issues', 0) > 0 else 'No'],
        ]
        
        metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#E5E7EB')),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F3F4F6')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(metrics_table)
        
        return elements

    def _build_vulnerability_overview(self, scan_data: Dict[str, Any]) -> List:
        """Build vulnerability overview section"""
        elements = []
        
        elements.append(Paragraph("Vulnerability Overview", self.styles['CustomTitle']))
        
        # Severity breakdown
        vulnerability_summary = scan_data.get('vulnerability_summary', {})
        severity_breakdown = vulnerability_summary.get('severity_breakdown', {})
        
        if any(severity_breakdown.values()):
            elements.append(Paragraph("Vulnerabilities by Severity", self.styles['SectionHeading']))
            
            severity_data = [['Severity', 'Count', 'Priority']]
            
            for severity, count in [('critical', 'Critical'), ('high', 'High'), 
                                  ('medium', 'Medium'), ('low', 'Low')]:
                vuln_count = severity_breakdown.get(severity, 0)
                priority = 'Immediate' if severity == 'critical' else 'High' if severity == 'high' else 'Medium' if severity == 'medium' else 'Low'
                
                severity_data.append([count, str(vuln_count), priority])
            
            severity_table = Table(severity_data, colWidths=[1.5*inch, 1*inch, 1.5*inch])
            severity_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#E5E7EB')),
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F3F4F6')),
                ('BACKGROUND', (0, 1), (-1, 1), HexColor('#FEE2E2')),  # Critical - red
                ('BACKGROUND', (0, 2), (-1, 2), HexColor('#FED7AA')),  # High - orange
                ('BACKGROUND', (0, 3), (-1, 3), HexColor('#FEF3C7')),  # Medium - yellow
                ('BACKGROUND', (0, 4), (-1, 4), HexColor('#D1FAE5')),  # Low - green
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            elements.append(severity_table)
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Business impact
        ai_analysis = scan_data.get('ai_analysis', {})
        business_impact = ai_analysis.get('business_impact', 
                                        'Business impact assessment requires detailed analysis.')
        
        elements.append(Paragraph("Business Impact Assessment", self.styles['SectionHeading']))
        elements.append(Paragraph(business_impact, self.styles['Normal']))
        
        return elements

    def _build_detailed_findings(self, scan_data: Dict[str, Any]) -> List:
        """Build detailed findings section"""
        elements = []
        
        elements.append(Paragraph("Detailed Security Findings", self.styles['CustomTitle']))
        
        ai_analysis = scan_data.get('ai_analysis', {})
        critical_findings = ai_analysis.get('critical_findings', [])
        
        if critical_findings:
            for i, finding in enumerate(critical_findings[:10]):  # Limit to top 10
                elements.append(Paragraph(f"Finding #{i+1}: {finding.get('title', 'Unknown')}", 
                                        self.styles['SectionHeading']))
                
                # Finding details table
                finding_data = [
                    ['Severity:', finding.get('severity', 'Unknown')],
                    ['Description:', finding.get('description', 'No description')],
                    ['Business Impact:', finding.get('business_impact', 'Impact assessment pending')],
                    ['Remediation:', finding.get('remediation', 'Remediation steps pending')]
                ]
                
                finding_table = Table(finding_data, colWidths=[1.5*inch, 4*inch])
                finding_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, HexColor('#E5E7EB')),
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F3F4F6')),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                
                elements.append(finding_table)
                elements.append(Spacer(1, 0.2*inch))
        else:
            elements.append(Paragraph("No critical findings available. Raw scan data analysis required.", 
                                    self.styles['Normal']))
        
        return elements

    def _build_recommendations(self, scan_data: Dict[str, Any]) -> List:
        """Build recommendations section"""
        elements = []
        
        elements.append(Paragraph("Security Recommendations", self.styles['CustomTitle']))
        
        ai_analysis = scan_data.get('ai_analysis', {})
        recommendations = ai_analysis.get('recommendations', [
            'Conduct detailed security analysis',
            'Implement security best practices',
            'Regular security assessments recommended'
        ])
        
        elements.append(Paragraph("Priority Actions", self.styles['SectionHeading']))
        
        for i, recommendation in enumerate(recommendations[:10]):
            elements.append(Paragraph(f"{i+1}. {recommendation}", self.styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Timeline
        timeline = ai_analysis.get('timeline_for_remediation', 
                                 'Immediate action recommended for critical issues. Complete assessment within 30 days.')
        
        elements.append(Paragraph("Recommended Timeline", self.styles['SectionHeading']))
        elements.append(Paragraph(timeline, self.styles['Normal']))
        
        return elements

    def _build_technical_appendix(self, scan_data: Dict[str, Any]) -> List:
        """Build technical appendix"""
        elements = []
        
        elements.append(Paragraph("Technical Appendix", self.styles['CustomTitle']))
        
        # Scan methodology
        elements.append(Paragraph("Scan Methodology", self.styles['SectionHeading']))
        methodology_text = """
        This security assessment was conducted using PHANTOM Security AI, which combines:
        
        • Network port scanning using Nmap
        • Web application security testing
        • Vulnerability detection using Nuclei templates
        • DNS reconnaissance and subdomain enumeration
        • AI-powered analysis using GPT-4 for threat assessment
        
        The scan was performed in a non-intrusive manner to minimize impact on target systems.
        """
        elements.append(Paragraph(methodology_text, self.styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Technical details
        elements.append(Paragraph("Scan Details", self.styles['SectionHeading']))
        
        scan_stats = []
        
        # Port scan results
        port_scan = scan_data.get('port_scan', {})
        if port_scan and 'ports' in port_scan:
            scan_stats.append(f"Open ports discovered: {len(port_scan['ports'])}")
        
        # Web scan results
        web_scan = scan_data.get('web_scan', {})
        if web_scan:
            scan_stats.append("Web application security assessment completed")
        
        # Vulnerability scan
        nuclei_scan = scan_data.get('nuclei_scan', {})
        if nuclei_scan and 'vulnerabilities' in nuclei_scan:
            scan_stats.append(f"Vulnerability templates executed: {len(nuclei_scan['vulnerabilities'])}")
        
        for stat in scan_stats:
            elements.append(Paragraph(f"• {stat}", self.styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Disclaimer
        elements.append(Paragraph("Disclaimer", self.styles['SectionHeading']))
        disclaimer_text = """
        This security assessment represents a point-in-time analysis based on the scan results. 
        Security vulnerabilities may change over time due to system updates, configuration changes, 
        or newly discovered threats. Regular security assessments are recommended to maintain 
        an accurate security posture.
        
        PHANTOM Security AI provides automated analysis but human expertise should validate 
        critical findings before taking remediation actions.
        """
        elements.append(Paragraph(disclaimer_text, self.styles['Normal']))
        
        return elements

    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level from risk score"""
        if risk_score >= 76:
            return "Critical"
        elif risk_score >= 51:
            return "High"
        elif risk_score >= 26:
            return "Medium"
        else:
            return "Low"

    def _get_risk_color(self, risk_level: str) -> str:
        """Get color for risk level"""
        colors = {
            "Critical": "#DC2626",
            "High": "#EA580C", 
            "Medium": "#D97706",
            "Low": "#16A34A"
        }
        return colors.get(risk_level, "#6B7280")

def generate_pdf_report(scan: Any) -> str:
    """Generate PDF report for a scan"""
    generator = PHANTOMReportGenerator()
    
    # Prepare scan data
    scan_data = {
        'target': scan.target,
        'scan_results': scan.scan_results or {},
        'ai_analysis': scan.ai_analysis or {},
        'vulnerability_count': scan.vulnerability_count or 0,
        'vulnerability_summary': scan.scan_results.get('vulnerability_summary', {}) if scan.scan_results else {}
    }
    
    return generator.generate_report(scan_data)