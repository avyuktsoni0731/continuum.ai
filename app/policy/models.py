"""Data models for policy engine."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel


class Action(str, Enum):
    """Possible actions the agent can take."""
    EXECUTE = "execute"  # User available, execute directly
    DELEGATE = "delegate"  # User unavailable, delegate to teammate
    SUMMARIZE = "summarize"  # Low criticality, summarize for later
    RESCHEDULE = "reschedule"  # Can't do now, reschedule
    AUTOMATE = "automate"  # Safe to automate (with guardrails)
    NOTIFY = "notify"  # Just notify user/team


class DecisionTrace(BaseModel):
    """Trace of decision-making process for explainability."""
    action: Action
    criticality_score: float
    automation_feasibility_score: float
    user_available: bool
    reasoning: str
    factors: Dict[str, Any]
    selected_teammate: Optional[str] = None
    guardrail_checks: Optional[Dict[str, bool]] = None


class TaskContext(BaseModel):
    """Context about a task (PR, Jira issue, etc.)"""
    # Task identification
    task_type: str  # "pr", "jira_issue", "calendar_event"
    task_id: str  # PR number, issue key, event ID
    
    # Task details
    title: str
    priority: Optional[str] = None
    status: Optional[str] = None
    
    # Criticality factors
    size: Optional[str] = None  # "small", "medium", "large" for PRs
    age_days: Optional[float] = None
    due_date: Optional[str] = None
    labels: list[str] = []
    
    # Automation feasibility factors
    ci_passed: Optional[bool] = None
    approvals: Optional[int] = None
    has_blockers: Optional[bool] = None
    is_mergeable: Optional[bool] = None
    
    # Additional context
    assignee: Optional[str] = None
    metadata: Dict[str, Any] = {}

