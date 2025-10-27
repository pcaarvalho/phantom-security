"""
Notification system for PHANTOM Security AI
"""

from .service import NotificationService
from .channels import EmailChannel, WebhookChannel

__all__ = ['NotificationService', 'EmailChannel', 'WebhookChannel']