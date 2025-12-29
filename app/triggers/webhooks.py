"""
Webhook handlers for GitHub and Jira events.

Receives events from external services and triggers processing.
"""

import logging
from datetime import datetime
from typing import Dict, Any
from app.triggers.models import TriggerEvent, TriggerType
from app.triggers.processor import process_trigger

logger = logging.getLogger(__name__)


async def handle_github_webhook(payload: Dict[str, Any]) -> bool:
    """
    Handle GitHub webhook events.
    
    Supported events:
    - pull_request.opened
    - pull_request.synchronize (updated)
    - pull_request.labeled (priority change)
    """
    event_type = payload.get("action")
    pr_data = payload.get("pull_request", {})
    
    if not pr_data:
        return False
    
    pr_number = pr_data.get("number")
    if not pr_number:
        return False
    
    logger.info(f"GitHub webhook: {event_type} for PR #{pr_number}")
    
    # Create trigger event
    trigger_event = TriggerEvent(
        trigger_type=TriggerType.WEBHOOK,
        event_data={
            "source": "github",
            "event_type": event_type,
            "task_type": "pr_review",
            "task_key": str(pr_number),
            "task_id": f"pr_{pr_number}",
            "user_id": pr_data.get("user", {}).get("login", ""),
            "metadata": {
                "pr_number": pr_number,
                "pr_data": pr_data
            }
        },
        timestamp=datetime.now(),
        source="github"
    )
    
    # Process trigger
    await process_trigger(trigger_event)
    
    return True


async def handle_jira_webhook(payload: Dict[str, Any]) -> bool:
    """
    Handle Jira webhook events.
    
    Supported events:
    - jira:issue_created
    - jira:issue_updated (priority, due date changes)
    - jira:issue_assigned
    """
    webhook_event = payload.get("webhookEvent", "")
    issue = payload.get("issue", {})
    
    if not issue:
        return False
    
    issue_key = issue.get("key")
    if not issue_key:
        return False
    
    logger.info(f"Jira webhook: {webhook_event} for {issue_key}")
    
    # Create trigger event
    trigger_event = TriggerEvent(
        trigger_type=TriggerType.WEBHOOK,
        event_data={
            "source": "jira",
            "event_type": webhook_event,
            "task_type": "issue_work",
            "task_key": issue_key,
            "task_id": issue_key,
            "user_id": issue.get("fields", {}).get("assignee", {}).get("accountId", ""),
            "metadata": {
                "issue_key": issue_key,
                "issue_data": issue
            }
        },
        timestamp=datetime.now(),
        source="jira"
    )
    
    # Process trigger
    await process_trigger(trigger_event)
    
    return True

