"""
Context mismatch detector.

Detects when planned work can't be done due to:
- User in meeting
- Task overdue
- Calendar conflicts
- Priority changes
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from app.triggers.models import TriggerEvent, ContextMismatch, ScheduledTask

logger = logging.getLogger(__name__)


async def detect_context_mismatch(event: TriggerEvent) -> Optional[ContextMismatch]:
    """
    Detect if there's a context mismatch for a scheduled task.
    
    Returns ContextMismatch if mismatch detected, None otherwise.
    """
    event_data = event.event_data
    task_type = event_data.get("task_type")
    task_key = event_data.get("task_key")
    user_id = event_data.get("user_id")
    scheduled_time_str = event_data.get("scheduled_time")
    
    if not scheduled_time_str:
        return None
    
    try:
        scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
    
    # Create task object
    task = ScheduledTask(
        task_id=event_data.get("task_id", ""),
        task_type=task_type,
        task_key=task_key,
        scheduled_time=scheduled_time,
        user_id=user_id,
        metadata=event_data.get("metadata", {})
    )
    
    # Check 1: Is user in a meeting at scheduled time?
    in_meeting = await _check_user_in_meeting(user_id, scheduled_time)
    if in_meeting:
        return ContextMismatch(
            task=task,
            reason="user_in_meeting",
            detected_at=datetime.now(),
            severity="high"
        )
    
    # Check 2: Is task overdue?
    now = datetime.now()
    if scheduled_time < now - timedelta(hours=1):
        return ContextMismatch(
            task=task,
            reason="task_overdue",
            detected_at=now,
            severity="high"
        )
    
    # Check 3: Is there a calendar conflict?
    conflict = await _check_calendar_conflict(user_id, scheduled_time)
    if conflict:
        return ContextMismatch(
            task=task,
            reason="calendar_conflict",
            detected_at=now,
            severity="medium"
        )
    
    # Check 4: Has task priority changed?
    priority_change = await _check_priority_change(task)
    if priority_change:
        return ContextMismatch(
            task=task,
            reason="priority_changed",
            detected_at=now,
            severity="medium"
        )
    
    return None


async def _check_user_in_meeting(user_id: str, time: datetime) -> bool:
    """Check if user is in a meeting at the given time."""
    try:
        from app.tools.calendar import get_events
        from datetime import timedelta
        
        # Check events around the scheduled time (±30 minutes)
        start = (time - timedelta(minutes=30)).isoformat() + 'Z'
        end = (time + timedelta(minutes=30)).isoformat() + 'Z'
        
        events = await get_events(
            start_date=start,
            end_date=end,
            calendar_id="primary"  # TODO: Get user's calendar ID
        )
        
        # Check if any event overlaps with scheduled time
        for event in events:
            event_start = event.get('start') or event.get('start_time', '')
            event_end = event.get('end') or event.get('end_time', '')
            
            if event_start and event_end:
                try:
                    start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                    
                    if start_dt <= time <= end_dt:
                        logger.info(f"User in meeting: {event.get('summary')} at {time}")
                        return True
                except (ValueError, AttributeError):
                    pass
        
        return False
        
    except Exception as e:
        logger.warning(f"Could not check user meetings: {e}")
        return False


async def _check_calendar_conflict(user_id: str, time: datetime) -> bool:
    """Check if there's a calendar conflict."""
    # Similar to _check_user_in_meeting but checks broader window
    return await _check_user_in_meeting(user_id, time)


async def _check_priority_change(task: ScheduledTask) -> bool:
    """Check if task priority has changed significantly."""
    try:
        if task.task_type == "pr_review":
            # Check if PR priority increased (e.g., urgent label added)
            pr_number = task.metadata.get("pr_number")
            if pr_number:
                from app.tools.github import get_pr_context
                pr_context = await get_pr_context(pr_number)
                pr_data = pr_context.get("pr", {})
                labels = pr_data.get("labels", [])
                
                urgent_labels = ["urgent", "critical", "hotfix", "p0", "p1"]
                if any(urgent in label.lower() for label in labels for urgent in urgent_labels):
                    logger.info(f"PR {pr_number} has urgent label")
                    return True
        
        elif task.task_type == "issue_work":
            # Check if issue priority increased
            issue_key = task.metadata.get("issue_key")
            if issue_key:
                from app.tools.jira import get_single_issue
                issue = await get_single_issue(issue_key)
                priority = issue.priority
                
                if priority and priority.lower() in ["highest", "high"]:
                    logger.info(f"Issue {issue_key} has high priority")
                    return True
        
        return False
        
    except Exception as e:
        logger.warning(f"Could not check priority change: {e}")
        return False

