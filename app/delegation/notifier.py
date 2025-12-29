"""
Slack notification system for delegation.

Sends smart, contextual notifications to selected teammates.
"""

import os
import logging
from typing import Optional
import httpx
from app.delegation.models import Teammate, DelegationNotification

logger = logging.getLogger(__name__)


def _get_slack_headers() -> dict:
    """Get Slack API headers."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not configured")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


async def notify_teammate(notification: DelegationNotification) -> bool:
    """
    Notify a teammate via Slack about a delegated task.
    
    Args:
        notification: Delegation notification details
    
    Returns:
        True if notification sent successfully
    """
    teammate = notification.teammate
    
    # Determine notification channel
    # Try DM first, fallback to channel mention
    channel = None
    if teammate.slack_user_id:
        # For DM, use user ID as channel
        channel = teammate.slack_user_id
    else:
        logger.warning(f"No Slack user ID for {teammate.username}, cannot send DM")
        return False
    
    # Build message
    message = _build_delegation_message(notification)
    
    # Send to Slack
    try:
        headers = _get_slack_headers()
        
        payload = {
            "channel": channel,
            "text": message,
            "blocks": _build_slack_blocks(notification)  # Rich formatting
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
                return False
            
            logger.info(f"Delegation notification sent to {teammate.username}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to send delegation notification: {e}", exc_info=True)
        return False


def _build_delegation_message(notification: DelegationNotification) -> str:
    """Build plain text delegation message."""
    teammate = notification.teammate
    urgency_emoji = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🟢"
    }.get(notification.urgency, "⚪")
    
    lines = [
        f"{urgency_emoji} *Task Delegation*",
        f"",
        f"*Task:* {notification.task_type.upper()} {notification.task_id}",
        f"*Title:* {notification.task_title}",
        f"*Action Requested:* {notification.action_requested}",
        f"*Urgency:* {notification.urgency.upper()}",
    ]
    
    if notification.suggested_deadline:
        lines.append(f"*Suggested Deadline:* {notification.suggested_deadline}")
    
    lines.append(f"")
    lines.append(f"*Context:*")
    
    # Add relevant context
    context = notification.context
    if context.get("criticality_score"):
        lines.append(f"• Criticality Score: {context['criticality_score']:.1f}")
    if context.get("reasoning"):
        lines.append(f"• Why: {context['reasoning']}")
    if context.get("url"):
        lines.append(f"• Link: {context['url']}")
    
    return "\n".join(lines)


def _build_slack_blocks(notification: DelegationNotification) -> list[dict]:
    """Build Slack Block Kit blocks for rich formatting."""
    teammate = notification.teammate
    urgency_color = {
        "high": "#ff0000",
        "medium": "#ffaa00",
        "low": "#00ff00"
    }.get(notification.urgency, "#cccccc")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 Task Delegation: {notification.task_id}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{notification.task_title}*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Action:*\n{notification.action_requested}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Urgency:*\n{notification.urgency.upper()}"
                }
            ]
        }
    ]
    
    # Add context if available
    context = notification.context
    if context.get("criticality_score") or context.get("reasoning"):
        context_text = []
        if context.get("criticality_score"):
            context_text.append(f"*Criticality:* {context['criticality_score']:.1f}")
        if context.get("reasoning"):
            context_text.append(f"*Why:* {context['reasoning']}")
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(context_text)
            }
        })
    
    # Add link if available
    if context.get("url"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{context['url']}|View Task>"
            }
        })
    
    # Add divider
    blocks.append({"type": "divider"})
    
    return blocks


async def notify_team_channel(
    notification: DelegationNotification,
    channel_id: str
) -> bool:
    """
    Notify team in a channel (alternative to DM).
    
    Useful for transparency or when DM fails.
    """
    teammate = notification.teammate
    
    message = (
        f"📋 *Task Delegation*\n"
        f"*Assigned to:* <@{teammate.slack_user_id}>\n"
        f"*Task:* {notification.task_type.upper()} {notification.task_id}\n"
        f"*Title:* {notification.task_title}\n"
        f"*Action:* {notification.action_requested}\n"
        f"*Urgency:* {notification.urgency.upper()}"
    )
    
    try:
        headers = _get_slack_headers()
        
        payload = {
            "channel": channel_id,
            "text": message,
            "blocks": _build_slack_blocks(notification)
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
                logger.error(f"Slack API error: {result.get('error')}")
                return False
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to notify team channel: {e}", exc_info=True)
        return False

