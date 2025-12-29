"""Trigger system for continuum.ai - Proactive context detection and action."""

from app.triggers.scheduler import start_scheduler, stop_scheduler, ScheduledTask
from app.triggers.detector import detect_context_mismatch, ContextMismatch
from app.triggers.webhooks import handle_github_webhook, handle_jira_webhook

__all__ = [
    "start_scheduler",
    "stop_scheduler",
    "ScheduledTask",
    "detect_context_mismatch",
    "ContextMismatch",
    "handle_github_webhook",
    "handle_jira_webhook",
]

