"""
Scoring system for policy engine.

Calculates:
- Criticality Score (CS): How urgent/important is this task?
- Automation Feasibility Score (AFS): How safe is it to automate?
"""

from datetime import datetime, timezone
from typing import Optional
from app.policy.models import TaskContext


def calculate_criticality_score(context: TaskContext) -> float:
    """
    Calculate Criticality Score (CS) from 0-100.
    
    Higher score = more critical/urgent.
    
    Factors:
    - Priority (High/Medium/Low)
    - Due date proximity
    - Task age (older = more critical if not done)
    - Size (larger PRs = more critical)
    - Labels (e.g., "urgent", "blocker")
    - Status (blocked = more critical)
    """
    score = 50.0  # Base score
    
    # Priority factor (0-30 points)
    priority_scores = {
        "highest": 30,
        "high": 25,
        "medium": 15,
        "low": 5,
        "lowest": 0,
    }
    if context.priority:
        priority_lower = context.priority.lower()
        score += priority_scores.get(priority_lower, 10)
    
    # Due date factor (0-25 points)
    if context.due_date:
        try:
            due = datetime.fromisoformat(context.due_date.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            hours_until_due = (due - now).total_seconds() / 3600
            
            if hours_until_due < 0:
                # Overdue - very critical
                score += 25
            elif hours_until_due < 24:
                # Due within 24 hours
                score += 20
            elif hours_until_due < 48:
                # Due within 48 hours
                score += 15
            elif hours_until_due < 168:  # 1 week
                # Due within a week
                score += 10
        except (ValueError, AttributeError):
            pass
    
    # Age factor (0-20 points)
    # Older tasks that aren't done become more critical
    if context.age_days:
        if context.age_days > 7:
            score += 20
        elif context.age_days > 3:
            score += 15
        elif context.age_days > 1:
            score += 10
    
    # Size factor for PRs (0-15 points)
    if context.size:
        size_scores = {
            "large": 15,
            "medium": 10,
            "small": 5,
        }
        score += size_scores.get(context.size.lower(), 5)
    
    # Label factor (0-10 points)
    urgent_labels = ["urgent", "critical", "blocker", "hotfix", "p0", "p1"]
    for label in context.labels:
        if any(urgent in label.lower() for urgent in urgent_labels):
            score += 10
            break
    
    # Status factor (0-10 points)
    if context.status:
        status_lower = context.status.lower()
        if "blocked" in status_lower or "stuck" in status_lower:
            score += 10
        elif "in progress" in status_lower:
            score += 5
    
    # Cap at 100
    return min(score, 100.0)


def calculate_automation_feasibility_score(context: TaskContext) -> float:
    """
    Calculate Automation Feasibility Score (AFS) from 0-100.
    
    Higher score = safer to automate.
    
    Factors:
    - CI status (passed = safer)
    - Approvals (more = safer)
    - Blockers (none = safer)
    - Mergeable status
    - Task type (some are safer than others)
    """
    score = 0.0
    
    # CI status (0-30 points)
    if context.ci_passed is True:
        score += 30
    elif context.ci_passed is False:
        score += 0  # Don't automate if CI failed
    else:
        score += 15  # Unknown CI status
    
    # Approvals (0-25 points)
    if context.approvals is not None:
        if context.approvals >= 2:
            score += 25
        elif context.approvals == 1:
            score += 15
        else:
            score += 5
    
    # Blockers (0-20 points)
    if context.has_blockers is False:
        score += 20
    elif context.has_blockers is True:
        score += 0  # Don't automate if blocked
    else:
        score += 10  # Unknown
    
    # Mergeable status (0-15 points)
    if context.is_mergeable is True:
        score += 15
    elif context.is_mergeable is False:
        score += 0
    else:
        score += 7
    
    # Task type factor (0-10 points)
    # PRs are generally safer to automate than issues
    if context.task_type == "pr":
        score += 10
    elif context.task_type == "jira_issue":
        score += 5  # Issues need more human judgment
    
    # Cap at 100
    return min(score, 100.0)


def extract_task_context_from_pr(pr_data: dict) -> TaskContext:
    """Extract TaskContext from PR data."""
    context_summary = pr_data.get("context_summary", {})
    pr_detail = pr_data.get("pr", {})
    
    # Calculate age
    created = pr_detail.get("created_at")
    age_days = None
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age_days = (now - created_dt).total_seconds() / 86400
        except (ValueError, AttributeError):
            pass
    
    return TaskContext(
        task_type="pr",
        task_id=str(pr_detail.get("number", "")),
        title=pr_detail.get("title", ""),
        status=pr_detail.get("state", ""),
        size=context_summary.get("pr_size"),
        age_days=age_days,
        labels=pr_detail.get("labels", []),
        ci_passed=context_summary.get("ci_passed"),
        approvals=context_summary.get("approvals", 0),
        has_blockers=context_summary.get("has_blockers", False),
        is_mergeable=context_summary.get("is_mergeable", False),
        assignee=pr_detail.get("user", {}).get("login") if isinstance(pr_detail.get("user"), dict) else None,
        metadata={"pr_data": pr_data}
    )


def extract_task_context_from_jira(issue_data: dict) -> TaskContext:
    """Extract TaskContext from Jira issue data."""
    # Handle both dict and Pydantic model
    if hasattr(issue_data, 'model_dump'):
        issue_data = issue_data.model_dump()
    
    # Calculate age
    created = issue_data.get("created")
    age_days = None
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age_days = (now - created_dt).total_seconds() / 86400
        except (ValueError, AttributeError, TypeError):
            pass
    
    # Get due time
    due_time = issue_data.get("due_time")
    
    return TaskContext(
        task_type="jira_issue",
        task_id=issue_data.get("key", ""),
        title=issue_data.get("summary", ""),
        priority=issue_data.get("priority"),
        status=issue_data.get("status"),
        age_days=age_days,
        due_date=due_time,
        labels=issue_data.get("labels", []),
        assignee=issue_data.get("assignee"),
        metadata={"issue_data": issue_data}
    )

