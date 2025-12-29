"""
Trigger event processor.

Processes trigger events by:
1. Applying policy engine
2. Executing actions (delegate/reschedule/notify)
3. Sending Slack notifications
"""

import logging
from typing import Optional
from app.triggers.models import TriggerEvent, ContextMismatch
from app.policy.scoring import (
    extract_task_context_from_pr,
    extract_task_context_from_jira
)
from app.policy.decision import decide_action
from app.delegation.selector import select_teammate
from app.delegation.notifier import notify_teammate, DelegationNotification

logger = logging.getLogger(__name__)


async def process_trigger(event: TriggerEvent, mismatch: Optional[ContextMismatch] = None):
    """
    Process a trigger event.
    
    Args:
        event: The trigger event
        mismatch: Context mismatch if detected
    """
    logger.info(f"Processing trigger: {event.trigger_type} for {event.event_data.get('task_key')}")
    
    try:
        # Get task context
        task_context = await _get_task_context(event)
        
        if not task_context:
            logger.warning(f"Could not get task context for {event.event_data.get('task_key')}")
            return
        
        # Check user availability
        user_available = await _check_user_availability(event.event_data.get("user_id"))
        
        # Apply policy engine
        decision = decide_action(task_context, user_available, automation_enabled=False)
        
        logger.info(f"Policy decision: {decision.action.value} (CS: {decision.criticality_score:.1f})")
        
        # Execute action based on decision
        if decision.action.value == "delegate":
            await _execute_delegation(task_context, decision, event)
        elif decision.action.value == "reschedule":
            await _execute_reschedule(task_context, decision, event, mismatch)
        elif decision.action.value == "summarize":
            await _execute_summarize(task_context, decision, event)
        elif decision.action.value == "notify":
            await _execute_notify(task_context, decision, event, mismatch)
        else:
            logger.info(f"Action {decision.action.value} - no execution needed")
            
    except Exception as e:
        logger.error(f"Error processing trigger: {e}", exc_info=True)


async def _get_task_context(event: TriggerEvent):
    """Get task context from event data."""
    event_data = event.event_data
    task_type = event_data.get("task_type")
    task_key = event_data.get("task_key")
    
    try:
        if task_type == "pr_review":
            pr_number = int(task_key)
            from app.tools.github import get_pr_context
            pr_data = await get_pr_context(pr_number)
            return extract_task_context_from_pr(pr_data)
        
        elif task_type == "issue_work":
            from app.tools.jira import get_single_issue
            issue = await get_single_issue(task_key)
            return extract_task_context_from_jira(issue.model_dump())
        
    except Exception as e:
        logger.error(f"Error getting task context: {e}", exc_info=True)
    
    return None


async def _check_user_availability(user_id: str) -> bool:
    """Check if user is available."""
    try:
        from app.tools.calendar import get_today_events
        from datetime import datetime
        
        events = await get_today_events()
        now = datetime.now()
        
        for event in events:
            start = event.get('start') or event.get('start_time', '')
            end = event.get('end') or event.get('end_time', '')
            
            if start and end:
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    
                    if start_dt <= now <= end_dt:
                        return False
                except (ValueError, AttributeError):
                    pass
        
        return True
        
    except Exception as e:
        logger.warning(f"Could not check availability: {e}")
        return True  # Default to available


async def _execute_delegation(task_context, decision, event: TriggerEvent):
    """Execute delegation action."""
    try:
        # Select teammate
        teammate_score = await select_teammate(task_context)
        
        if not teammate_score:
            logger.warning("No teammate available for delegation")
            await _execute_notify(task_context, decision, event, None)
            return
        
        # Create notification
        teammate = teammate_score.teammate
        task_type = task_context.task_type
        
        if task_type == "pr":
            action_requested = "review and approve"
            urgency = "high" if decision.criticality_score > 70 else "medium"
        else:
            action_requested = "review and update"
            urgency = "high" if decision.criticality_score > 70 else "medium"
        
        context = {
            "criticality_score": decision.criticality_score,
            "reasoning": decision.reasoning,
        }
        
        # Add URL
        if task_type == "pr":
            context["url"] = f"https://github.com/{task_context.metadata.get('pr_data', {}).get('pr', {}).get('html_url', '')}"
        else:
            context["url"] = f"https://continuum-ai.atlassian.net/browse/{task_context.task_id}"
        
        notification = DelegationNotification(
            teammate=teammate,
            task_type=task_type,
            task_id=task_context.task_id,
            task_title=task_context.title,
            action_requested=action_requested,
            context=context,
            urgency=urgency
        )
        
        # Send notification
        success = await notify_teammate(notification)
        
        if success:
            logger.info(f"Delegated {task_context.task_id} to {teammate.username}")
        else:
            logger.error(f"Failed to delegate {task_context.task_id}")
            
    except Exception as e:
        logger.error(f"Delegation execution failed: {e}", exc_info=True)


async def _execute_reschedule(task_context, decision, event: TriggerEvent, mismatch: Optional[ContextMismatch]):
    """Execute reschedule action."""
    # TODO: Implement rescheduling logic
    # For now, just notify
    logger.info(f"Rescheduling {task_context.task_id} - TODO: Implement")
    await _execute_notify(task_context, decision, event, mismatch)


async def _execute_summarize(task_context, decision, event: TriggerEvent):
    """Execute summarize action."""
    # TODO: Implement summarization
    logger.info(f"Summarizing {task_context.task_id} - TODO: Implement")


async def _execute_notify(task_context, decision, event: TriggerEvent, mismatch: Optional[ContextMismatch]):
    """Execute notify action - send Slack notification."""
    try:
        import os
        import httpx
        
        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            logger.warning("SLACK_BOT_TOKEN not set, cannot send notification")
            return
        
        # Build notification message
        message = _build_notification_message(task_context, decision, mismatch)
        
        # Determine where to send notification
        # Option 1: Use default notification channel from env
        channel = os.getenv("SLACK_NOTIFICATION_CHANNEL")
        
        # Option 2: Try to get user's Slack ID from GitHub username
        if not channel:
            github_username = event.event_data.get("user_id", "")
            # Try to map GitHub username to Slack user ID
            # For now, use a default channel or the first channel the bot is in
            channel = os.getenv("SLACK_DEFAULT_CHANNEL")
            if not channel:
                # Fallback: try to find a channel the bot is in
                # For now, use #general as last resort
                channel = "#general"
                logger.warning(f"No SLACK_NOTIFICATION_CHANNEL or SLACK_DEFAULT_CHANNEL set, using {channel}")
        
        # Send to Slack
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": channel,
            "text": message,
            "blocks": _build_slack_blocks(task_context, decision, mismatch)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("ok"):
                error = result.get("error", "unknown_error")
                logger.error(f"Slack API error: {error}")
                return
            
            logger.info(f"Notification sent to Slack channel {channel}")
            
    except Exception as e:
        logger.error(f"Notification failed: {e}", exc_info=True)


def _build_notification_message(task_context, decision, mismatch: Optional[ContextMismatch]) -> str:
    """Build notification message."""
    lines = [
        f"📋 *Task Update: {task_context.task_id}*",
        f"*{task_context.title}*",
        "",
        f"💡 *Decision:* {decision.action.value.upper()}",
        f"CS: {decision.criticality_score:.1f} | AFS: {decision.automation_feasibility_score:.1f}",
        f"*Why:* {decision.reasoning}",
    ]
    
    if mismatch:
        lines.append("")
        lines.append(f"⚠️ *Context Mismatch Detected:* {mismatch.reason}")
        lines.append(f"Severity: {mismatch.severity.upper()}")
    
    return "\n".join(lines)


def _build_slack_blocks(task_context, decision, mismatch: Optional[ContextMismatch]) -> list[dict]:
    """Build Slack Block Kit blocks for rich formatting."""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 Task Update: {task_context.task_id}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{task_context.title}*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Decision:*\n{decision.action.value.upper()}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Criticality:*\n{decision.criticality_score:.1f}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Why:* {decision.reasoning}"
            }
        }
    ]
    
    if mismatch:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ *Context Mismatch:* {mismatch.reason}\n*Severity:* {mismatch.severity.upper()}"
            }
        })
    
    # Add task URL if available
    if task_context.task_type == "pr":
        pr_url = task_context.metadata.get("pr_data", {}).get("pr", {}).get("html_url")
        if pr_url:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{pr_url}|View PR>"
                }
            })
    elif task_context.task_type == "jira_issue":
        jira_url = f"https://continuum-ai.atlassian.net/browse/{task_context.task_id}"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{jira_url}|View Issue>"
            }
        })
    
    blocks.append({"type": "divider"})
    
    return blocks

