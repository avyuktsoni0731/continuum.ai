"""Data models for trigger system."""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class TriggerType(str, Enum):
    """Types of triggers."""
    SCHEDULED = "scheduled"  # Periodic check
    WEBHOOK = "webhook"  # External event (GitHub/Jira)
    CONTEXT_MISMATCH = "context_mismatch"  # Detected conflict


class ScheduledTask(BaseModel):
    """A scheduled task to monitor."""
    task_id: str
    task_type: str  # "pr_review", "issue_work", "meeting_prep"
    task_key: str  # PR number, issue key, etc.
    scheduled_time: datetime
    user_id: str
    metadata: Dict[str, Any] = {}


class ContextMismatch(BaseModel):
    """Detected context mismatch."""
    task: ScheduledTask
    reason: str  # "user_in_meeting", "task_overdue", "conflict"
    detected_at: datetime
    severity: str  # "high", "medium", "low"


class TriggerEvent(BaseModel):
    """A trigger event that needs processing."""
    trigger_type: TriggerType
    event_data: Dict[str, Any]
    timestamp: datetime
    source: str  # "github", "jira", "scheduler", "detector"

