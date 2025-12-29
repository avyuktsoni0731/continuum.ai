"""Data models for workflow orchestration."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel


class WorkflowType(str, Enum):
    """Types of workflows."""
    REASSIGN_ISSUE = "reassign_issue"
    CREATE_ISSUE = "create_issue"
    CREATE_ISSUE_WITH_PR = "create_issue_with_pr"


class WorkflowStep(BaseModel):
    """A single step in a workflow."""
    step_number: int
    tool_name: str
    params: Dict[str, Any]
    depends_on: list[int] = []  # Step numbers this step depends on
    description: str = ""


class WorkflowResult(BaseModel):
    """Result of workflow execution."""
    workflow_type: WorkflowType
    success: bool
    steps_executed: list[Dict[str, Any]]
    final_result: Dict[str, Any] | None = None
    error: str | None = None

