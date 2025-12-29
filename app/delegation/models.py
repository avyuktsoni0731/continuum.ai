"""Data models for delegation engine."""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class Teammate(BaseModel):
    """Represents a teammate."""
    username: str
    email: Optional[str] = None
    slack_user_id: Optional[str] = None
    github_username: Optional[str] = None
    timezone: Optional[str] = None
    workload_score: float = 0.0  # 0-100, higher = more busy
    ownership_score: float = 0.0  # 0-100, higher = more relevant
    availability_score: float = 0.0  # 0-100, higher = more available
    total_score: float = 0.0  # Combined score


class TeammateScore(BaseModel):
    """Scored teammate with reasoning."""
    teammate: Teammate
    total_score: float
    reasoning: str
    factors: Dict[str, Any]


class DelegationNotification(BaseModel):
    """Delegation notification details."""
    teammate: Teammate
    task_type: str  # "pr", "jira_issue"
    task_id: str
    task_title: str
    action_requested: str  # "review", "fix", "approve", etc.
    context: Dict[str, Any]
    urgency: str  # "high", "medium", "low"
    suggested_deadline: Optional[str] = None

