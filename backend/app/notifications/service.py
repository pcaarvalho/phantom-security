"""
Main notification service for managing alerts and notifications
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from .channels import NotificationChannel, EmailChannel, WebhookChannel
from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing and sending notifications"""
    
    def __init__(self):
        self.channels: List[NotificationChannel] = []
        self._initialize_channels()
        
    def _initialize_channels(self):
        """Initialize notification channels from configuration"""
        # Initialize email channel if configured
        if hasattr(settings, 'smtp_host') and settings.smtp_host:
            try:
                email_channel = EmailChannel(
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    username=settings.smtp_username,
                    password=settings.smtp_password,
                    from_email=settings.smtp_from_email
                )
                self.channels.append(email_channel)
                logger.info("Email notification channel initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize email channel: {e}")
        
        # Initialize Slack webhook if configured
        if hasattr(settings, 'slack_webhook_url') and settings.slack_webhook_url:
            try:
                slack_channel = WebhookChannel(
                    webhook_url=settings.slack_webhook_url,
                    channel_type="slack"
                )
                self.channels.append(slack_channel)
                logger.info("Slack notification channel initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Slack channel: {e}")
        
        # Initialize Discord webhook if configured
        if hasattr(settings, 'discord_webhook_url') and settings.discord_webhook_url:
            try:
                discord_channel = WebhookChannel(
                    webhook_url=settings.discord_webhook_url,
                    channel_type="discord"
                )
                self.channels.append(discord_channel)
                logger.info("Discord notification channel initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Discord channel: {e}")
    
    async def send_notification(
        self,
        title: str,
        body: str,
        severity: str = "info",
        details: Optional[Dict[str, Any]] = None,
        to_emails: Optional[List[str]] = None
    ) -> bool:
        """Send notification to all configured channels"""
        message = {
            "title": title,
            "body": body,
            "severity": severity,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if to_emails:
            message["to"] = to_emails
        
        # Send to all channels
        results = await asyncio.gather(
            *[channel.send(message) for channel in self.channels],
            return_exceptions=True
        )
        
        # Log results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Channel {i} failed: {result}")
            elif not result:
                logger.warning(f"Channel {i} returned False")
        
        return any(r for r in results if r is True)
    
    async def notify_scan_started(self, scan_id: str, target: str):
        """Notify that a scan has started"""
        await self.send_notification(
            title="🚀 Security Scan Started",
            body=f"PHANTOM Security AI has started scanning {target}",
            severity="info",
            details={
                "Scan ID": scan_id,
                "Target": target,
                "Started At": datetime.utcnow().isoformat()
            }
        )
    
    async def notify_critical_vulnerability(
        self,
        scan_id: str,
        target: str,
        vulnerability: Dict[str, Any]
    ):
        """Notify about a critical vulnerability"""
        await self.send_notification(
            title="🚨 Critical Vulnerability Found",
            body=f"Critical security vulnerability detected in {target}",
            severity="critical",
            details={
                "Scan ID": scan_id,
                "Target": target,
                "Vulnerability": vulnerability.get("name", "Unknown"),
                "Severity": vulnerability.get("severity", "Critical"),
                "Description": vulnerability.get("description", ""),
                "CVE": vulnerability.get("cve", "N/A")
            }
        )
    
    async def notify_scan_completed(
        self,
        scan_id: str,
        target: str,
        risk_score: int,
        vulnerabilities_count: int,
        critical_count: int
    ):
        """Notify that a scan has completed"""
        severity = "info"
        if risk_score >= 80:
            severity = "critical"
        elif risk_score >= 60:
            severity = "high"
        elif risk_score >= 40:
            severity = "medium"
        
        emoji = "✅" if risk_score < 40 else "⚠️" if risk_score < 70 else "🚨"
        
        await self.send_notification(
            title=f"{emoji} Security Scan Completed",
            body=f"Scan of {target} completed with risk score: {risk_score}/100",
            severity=severity,
            details={
                "Scan ID": scan_id,
                "Target": target,
                "Risk Score": f"{risk_score}/100",
                "Total Vulnerabilities": vulnerabilities_count,
                "Critical Issues": critical_count,
                "Completed At": datetime.utcnow().isoformat()
            }
        )
    
    async def notify_scan_failed(self, scan_id: str, target: str, error: str):
        """Notify that a scan has failed"""
        await self.send_notification(
            title="❌ Security Scan Failed",
            body=f"Scan of {target} failed with error",
            severity="high",
            details={
                "Scan ID": scan_id,
                "Target": target,
                "Error": error,
                "Failed At": datetime.utcnow().isoformat()
            }
        )
    
    async def send_daily_summary(self, summary: Dict[str, Any]):
        """Send daily security summary"""
        await self.send_notification(
            title="📊 Daily Security Summary",
            body=f"Your daily PHANTOM Security report is ready",
            severity="info",
            details={
                "Total Scans": summary.get("total_scans", 0),
                "Vulnerabilities Found": summary.get("vulnerabilities_found", 0),
                "Critical Issues": summary.get("critical_issues", 0),
                "Average Risk Score": summary.get("avg_risk_score", 0),
                "Date": datetime.utcnow().date().isoformat()
            }
        )


# Global notification service instance
notification_service = NotificationService()