"""
Notification channels for different alert types
"""

import aiohttp
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
import logging
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    """Base class for notification channels"""
    
    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> bool:
        """Send notification through this channel"""
        pass


class EmailChannel(NotificationChannel):
    """Email notification channel"""
    
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, from_email: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        
    async def send(self, message: Dict[str, Any]) -> bool:
        """Send email notification"""
        try:
            to_emails = message.get("to", [])
            if not to_emails:
                logger.warning("No recipients specified for email")
                return False
            
            # Create email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.get("subject", "PHANTOM Security Alert")
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to_emails)
            
            # Create HTML content
            html_body = self._create_html_body(message)
            msg.attach(MIMEText(html_body, "html"))
            
            # Send email
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email, msg, to_emails)
            
            logger.info(f"Email sent successfully to {to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _send_email(self, msg: MIMEMultipart, to_emails: List[str]):
        """Synchronous email sending"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg, to_addrs=to_emails)
    
    def _create_html_body(self, message: Dict[str, Any]) -> str:
        """Create HTML email body"""
        severity = message.get("severity", "info")
        color_map = {
            "critical": "#DC2626",
            "high": "#EA580C",
            "medium": "#F59E0B",
            "low": "#10B981",
            "info": "#3B82F6"
        }
        color = color_map.get(severity, "#3B82F6")
        
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: {color}; color: white; padding: 20px; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0;">🛡️ PHANTOM Security Alert</h1>
                </div>
                <div style="padding: 20px; background-color: #f9f9f9;">
                    <h2>{message.get('title', 'Security Alert')}</h2>
                    <p style="font-size: 16px; color: #333;">
                        {message.get('body', '')}
                    </p>
                    {self._format_details(message.get('details', {}))}
                </div>
                <div style="padding: 10px; background-color: #333; color: white; text-align: center;">
                    <small>PHANTOM Security AI - Autonomous Vulnerability Detection</small>
                </div>
            </body>
        </html>
        """
    
    def _format_details(self, details: Dict) -> str:
        """Format additional details for email"""
        if not details:
            return ""
        
        html = "<h3>Details:</h3><ul>"
        for key, value in details.items():
            html += f"<li><strong>{key}:</strong> {value}</li>"
        html += "</ul>"
        return html


class WebhookChannel(NotificationChannel):
    """Webhook notification channel (Slack, Discord, etc.)"""
    
    def __init__(self, webhook_url: str, channel_type: str = "slack"):
        self.webhook_url = webhook_url
        self.channel_type = channel_type
        
    async def send(self, message: Dict[str, Any]) -> bool:
        """Send webhook notification"""
        try:
            if self.channel_type == "slack":
                payload = self._format_slack_message(message)
            elif self.channel_type == "discord":
                payload = self._format_discord_message(message)
            else:
                payload = {"text": f"{message.get('title')}: {message.get('body')}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status in [200, 204]:
                        logger.info(f"Webhook notification sent successfully")
                        return True
                    else:
                        logger.error(f"Webhook failed: {response.status} - {await response.text()}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False
    
    def _format_slack_message(self, message: Dict[str, Any]) -> Dict:
        """Format message for Slack"""
        severity = message.get("severity", "info")
        color_map = {
            "critical": "danger",
            "high": "warning",
            "medium": "warning",
            "low": "good",
            "info": "#3B82F6"
        }
        
        return {
            "text": message.get("title", "PHANTOM Security Alert"),
            "attachments": [{
                "color": color_map.get(severity, "#3B82F6"),
                "title": message.get("title"),
                "text": message.get("body"),
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in message.get("details", {}).items()
                ],
                "footer": "PHANTOM Security AI",
                "ts": int(asyncio.get_event_loop().time())
            }]
        }
    
    def _format_discord_message(self, message: Dict[str, Any]) -> Dict:
        """Format message for Discord"""
        severity = message.get("severity", "info")
        color_map = {
            "critical": 0xDC2626,
            "high": 0xEA580C,
            "medium": 0xF59E0B,
            "low": 0x10B981,
            "info": 0x3B82F6
        }
        
        embeds = [{
            "title": message.get("title", "PHANTOM Security Alert"),
            "description": message.get("body"),
            "color": color_map.get(severity, 0x3B82F6),
            "fields": [
                {"name": k, "value": str(v), "inline": True}
                for k, v in message.get("details", {}).items()
            ],
            "footer": {"text": "PHANTOM Security AI"}
        }]
        
        return {"embeds": embeds}