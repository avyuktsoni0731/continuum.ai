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
    - pull_request.assigned
    - pull_request.review_requested
    """
    event_type = payload.get("action")
    pr_data = payload.get("pull_request", {})
    
    if not pr_data:
        return False
    
    pr_number = pr_data.get("number")
    if not pr_number:
        return False
    
    logger.info(f"GitHub webhook: {event_type} for PR #{pr_number}")
    
    # Extract change details based on event type
    change_details = _extract_github_change_details(payload, event_type)
    
    # Create trigger event with rich context
    trigger_event = TriggerEvent(
        trigger_type=TriggerType.WEBHOOK,
        event_data={
            "source": "github",
            "event_type": event_type,
            "task_type": "pr_review",
            "task_key": str(pr_number),
            "task_id": f"pr_{pr_number}",
            "user_id": pr_data.get("user", {}).get("login", ""),
            "change_details": change_details,  # What changed
            "metadata": {
                "pr_number": pr_number,
                "pr_title": pr_data.get("title", ""),
                "pr_state": pr_data.get("state", ""),
                "pr_draft": pr_data.get("draft", False),
                "pr_author": pr_data.get("user", {}).get("login", ""),
                "pr_url": pr_data.get("html_url", ""),
                "pr_body": pr_data.get("body", ""),
                "pr_labels": [label.get("name", "") for label in pr_data.get("labels", [])],
                "pr_assignees": [assignee.get("login", "") for assignee in pr_data.get("assignees", [])],
                "pr_reviewers": [reviewer.get("login", "") for reviewer in pr_data.get("requested_reviewers", [])],
                "pr_changed_files": pr_data.get("changed_files", 0),
                "pr_additions": pr_data.get("additions", 0),
                "pr_deletions": pr_data.get("deletions", 0),
                "pr_data": pr_data
            }
        },
        timestamp=datetime.now(),
        source="github"
    )
    
    # Process trigger
    await process_trigger(trigger_event)
    
    return True


def _extract_github_change_details(payload: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Extract what changed in the GitHub event."""
    change_details = {
        "action": event_type,
        "changed_by": payload.get("sender", {}).get("login", "unknown"),
        "timestamp": payload.get("pull_request", {}).get("updated_at", "")
    }
    
    if event_type == "assigned":
        assignee = payload.get("assignee", {})
        change_details["what_changed"] = "assignee"
        change_details["new_value"] = assignee.get("login", "")
        change_details["description"] = f"Assigned to {assignee.get('login', 'unknown')}"
    
    elif event_type == "unassigned":
        assignee = payload.get("assignee", {})
        change_details["what_changed"] = "assignee"
        change_details["old_value"] = assignee.get("login", "")
        change_details["description"] = f"Unassigned from {assignee.get('login', 'unknown')}"
    
    elif event_type == "review_requested":
        reviewer = payload.get("requested_reviewer", {})
        change_details["what_changed"] = "review_requested"
        change_details["new_value"] = reviewer.get("login", "")
        change_details["description"] = f"Review requested from {reviewer.get('login', 'unknown')}"
    
    elif event_type == "labeled":
        label = payload.get("label", {})
        change_details["what_changed"] = "label"
        change_details["new_value"] = label.get("name", "")
        change_details["description"] = f"Label '{label.get('name', 'unknown')}' added"
    
    elif event_type == "synchronize":
        change_details["what_changed"] = "code_updated"
        change_details["description"] = "PR code updated (new commits pushed)"
    
    elif event_type == "opened":
        change_details["what_changed"] = "pr_opened"
        change_details["description"] = "New pull request opened"
    
    elif event_type == "closed":
        pr_data = payload.get("pull_request", {})
        merged = pr_data.get("merged", False)
        change_details["what_changed"] = "pr_closed"
        change_details["description"] = "Merged" if merged else "Closed without merging"
    
    else:
        change_details["what_changed"] = event_type
        change_details["description"] = f"PR {event_type}"
    
    return change_details


async def handle_jira_webhook(payload: Dict[str, Any]) -> bool:
    """
    Handle Jira webhook events.
    
    Supported events:
    - jira:issue_created
    - jira:issue_updated (priority, due date changes, status changes, assignee changes)
    - jira:issue_assigned
    """
    webhook_event = payload.get("webhookEvent", "")
    issue = payload.get("issue", {})
    changelog = payload.get("changelog", {})
    user = payload.get("user", {})
    
    if not issue:
        logger.warning("Jira webhook: No issue in payload")
        return False
    
    issue_key = issue.get("key")
    if not issue_key:
        logger.warning("Jira webhook: No issue key in payload")
        return False
    
    logger.info(f"Jira webhook received: {webhook_event} for {issue_key}")
    
    # Extract change details from changelog
    change_details = _extract_jira_change_details(webhook_event, changelog, user, issue)
    
    # Log what changes were detected
    if change_details.get("changes"):
        logger.info(f"Detected {len(change_details['changes'])} change(s) for {issue_key}: {change_details.get('what_changed', 'unknown')}")
    else:
        logger.info(f"No changelog items found for {issue_key}, event type: {webhook_event}")
    
    fields = issue.get("fields", {})
    
    # Create trigger event with rich context
    trigger_event = TriggerEvent(
        trigger_type=TriggerType.WEBHOOK,
        event_data={
            "source": "jira",
            "event_type": webhook_event,
            "task_type": "issue_work",
            "task_key": issue_key,
            "task_id": issue_key,
            "user_id": user.get("accountId", "") or fields.get("assignee", {}).get("accountId", ""),
            "change_details": change_details,  # What changed
            "metadata": {
                "issue_key": issue_key,
                "issue_title": fields.get("summary", ""),
                "issue_status": fields.get("status", {}).get("name", ""),
                "issue_priority": fields.get("priority", {}).get("name", ""),
                "issue_type": fields.get("issuetype", {}).get("name", ""),
                "issue_assignee": fields.get("assignee", {}).get("displayName", ""),
                "issue_reporter": fields.get("reporter", {}).get("displayName", ""),
                "issue_description": fields.get("description", ""),
                "issue_labels": fields.get("labels", []),
                "issue_due_time": fields.get("customfield_10039", ""),
                "issue_url": f"https://continuum-ai.atlassian.net/browse/{issue_key}",
                "issue_data": issue
            }
        },
        timestamp=datetime.now(),
        source="jira"
    )
    
    # Process trigger
    await process_trigger(trigger_event)
    
    logger.info(f"Successfully processed Jira webhook for {issue_key}")
    return True


def _extract_jira_change_details(webhook_event: str, changelog: Dict[str, Any], user: Dict[str, Any], issue: Dict[str, Any]) -> Dict[str, Any]:
    """Extract what changed in the Jira event."""
    change_details = {
        "action": webhook_event,
        "changed_by": user.get("displayName", "unknown"),
        "timestamp": issue.get("fields", {}).get("updated", "")
    }
    
    # Parse changelog items to see what changed
    items = changelog.get("items", [])
    changes = []
    
    logger.debug(f"Processing {len(items)} changelog items for event {webhook_event}")
    
    for item in items:
        field = item.get("field", "")
        field_type = item.get("fieldtype", "")
        from_value = item.get("fromString", item.get("from"))
        to_value = item.get("toString", item.get("to"))
        
        logger.debug(f"Processing changelog item: field={field}, from={from_value}, to={to_value}")
        
        if field == "assignee":
            changes.append({
                "field": "assignee",
                "from": from_value or "Unassigned",
                "to": to_value or "Unassigned",
                "description": f"Assigned to {to_value}" if to_value else f"Unassigned from {from_value}"
            })
        elif field == "priority":
            changes.append({
                "field": "priority",
                "from": from_value,
                "to": to_value,
                "description": f"Priority changed from {from_value} to {to_value}"
            })
        elif field == "customfield_10039":  # Due Time
            changes.append({
                "field": "due_time",
                "from": from_value,
                "to": to_value,
                "description": f"Due time changed to {to_value}" if to_value else "Due time removed"
            })
        elif field == "status":
            changes.append({
                "field": "status",
                "from": from_value,
                "to": to_value,
                "description": f"Status changed from {from_value} to {to_value}"
            })
        elif field == "summary":
            changes.append({
                "field": "summary",
                "from": from_value,
                "to": to_value,
                "description": f"Title updated"
            })
        else:
            # Log unknown fields for debugging
            logger.debug(f"Unknown changelog field: {field} (type: {field_type})")
    
    change_details["changes"] = changes
    
    # Build summary description
    if changes:
        change_details["what_changed"] = ", ".join([c["field"] for c in changes])
        change_details["description"] = " | ".join([c["description"] for c in changes])
    else:
        # Handle events without changelog (like issue_created)
        if webhook_event == "jira:issue_created":
            change_details["what_changed"] = "issue_created"
            change_details["description"] = "New issue created"
            # Add a change entry for created events
            changes.append({
                "field": "created",
                "from": None,
                "to": issue.get("fields", {}).get("summary", ""),
                "description": "New issue created"
            })
        elif webhook_event == "jira:issue_assigned":
            assignee = issue.get("fields", {}).get("assignee", {}).get("displayName", "unknown")
            change_details["what_changed"] = "assignee"
            change_details["description"] = f"Assigned to {assignee}"
            changes.append({
                "field": "assignee",
                "from": None,
                "to": assignee,
                "description": f"Assigned to {assignee}"
            })
        else:
            change_details["what_changed"] = webhook_event
            change_details["description"] = f"Issue {webhook_event}"
    
    change_details["changes"] = changes  # Update with any added changes
    
    return change_details

