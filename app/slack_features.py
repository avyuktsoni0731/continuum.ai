"""
Slack bot productivity features for continuum.ai

Includes:
- Daily standup summaries
- Quick action shortcuts
- PR/Jira change summaries
- Context-aware suggestions
- Team workload dashboard
- Interactive action buttons
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.tools.jira import get_jira_issues, get_single_issue
from app.tools.github import get_pr_context
from app.tools.calendar import get_today_events

logger = logging.getLogger(__name__)


async def get_user_jira_issues(user_email: Optional[str] = None, jql: Optional[str] = None, board_id: Optional[int] = None) -> List[Dict]:
    """Get Jira issues for a user. Defaults to board 1 if no board_id specified."""
    try:
        # If board_id is provided, use board issues
        if board_id is None:
            # Default to board 1
            board_id = 1
        
        try:
            from app.tools.jira import get_board_issues
            issues = await get_board_issues(board_id)
            # Filter by user if needed
            if user_email:
                issues = [i for i in issues if i.assignee and user_email.lower() in i.assignee.lower()]
            return [issue.model_dump() for issue in issues]
        except Exception as board_error:
            logger.warning(f"Failed to get board issues, falling back to JQL: {board_error}")
            # Fallback to JQL query
            if jql:
                query = jql
            elif user_email:
                query = f'assignee = "{user_email}"'
            else:
                query = "assignee=currentUser() AND status != Done AND status != Closed"
            
            issues = await get_jira_issues(query)
            return [issue.model_dump() for issue in issues]
    except Exception as e:
        logger.error(f"Error getting Jira issues: {e}", exc_info=True)
        return []


async def get_user_prs(github_username: Optional[str] = None) -> List[Dict]:
    """Get PRs for a user."""
    try:
        from app.agno_tools.github_tools import get_github_pulls_tool
        prs = await get_github_pulls_tool(state="open")
        if not prs.get("success"):
            return []
        
        all_prs = prs.get("pulls", [])
        if github_username:
            # Filter by author
            user_prs = [pr for pr in all_prs if (pr.get("user") or "").lower() == github_username.lower()]
            return user_prs
        return all_prs
    except Exception as e:
        logger.error(f"Error getting PRs: {e}", exc_info=True)
        return []


async def generate_standup_summary(user_id: str, user_email: Optional[str] = None, github_username: Optional[str] = None) -> str:
    """
    Generate daily standup summary from Jira/GitHub activity.
    
    Args:
        user_id: Slack user ID
        user_email: User's email for Jira lookup
        github_username: User's GitHub username
    
    Returns:
        Formatted standup summary
    """
    try:
        # Get yesterday's date for "yesterday" context
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get Jira issues (defaults to board 1)
        issues = await get_user_jira_issues(user_email, board_id=1)
        
        # Get PRs
        prs = await get_user_prs(github_username)
        
        # Get calendar events for today
        try:
            today_events = await get_today_events()
            events = [e.model_dump() for e in today_events]
        except:
            events = []
        
        # Categorize issues
        completed = [i for i in issues if (i.get("status") or "").lower() in ["done", "closed", "resolved"]]
        in_progress = [i for i in issues if (i.get("status") or "").lower() in ["in progress", "in development"]]
        todo = [i for i in issues if (i.get("status") or "").lower() in ["to do", "open", "backlog"]]
        blocked = [i for i in issues if "block" in (i.get("description") or "").lower() or "block" in (i.get("summary") or "").lower()]
        
        # Format standup
        lines = ["📊 *Daily Standup Summary*\n"]
        
        # Yesterday (completed)
        if completed:
            lines.append("*✅ Completed Yesterday:*")
            for issue in completed[:5]:  # Limit to 5
                lines.append(f"• `{issue.get('key', 'N/A')}`: {issue.get('summary', 'No title')}")
            if len(completed) > 5:
                lines.append(f"  _...and {len(completed) - 5} more_")
            lines.append("")
        
        # Today (in progress)
        if in_progress:
            lines.append("*🔄 Working On Today:*")
            for issue in in_progress[:5]:
                lines.append(f"• `{issue.get('key', 'N/A')}`: {issue.get('summary', 'No title')}")
            if len(in_progress) > 5:
                lines.append(f"  _...and {len(in_progress) - 5} more_")
            lines.append("")
        
        # Blockers
        if blocked:
            lines.append("*🚫 Blockers:*")
            for issue in blocked[:3]:
                lines.append(f"• `{issue.get('key', 'N/A')}`: {issue.get('summary', 'No title')}")
            lines.append("")
        
        # PRs
        if prs:
            lines.append("*🔀 Open Pull Requests:*")
            for pr in prs[:5]:
                state_emoji = "✅" if pr.get("state") == "open" else "⏸️"
                lines.append(f"• {state_emoji} PR #{pr.get('number', 'N/A')}: *{pr.get('title', 'No title')}*")
            if len(prs) > 5:
                lines.append(f"  _...and {len(prs) - 5} more_")
            lines.append("")
        
        # Calendar
        if events:
            lines.append("*📅 Today's Meetings:*")
            for event in events[:5]:
                summary = event.get("summary", "Untitled")
                start = event.get("start", "")
                if start:
                    # Parse time
                    try:
                        if "T" in start:
                            time_part = start.split("T")[1][:5]
                            lines.append(f"• *{summary}* at {time_part}")
                        else:
                            lines.append(f"• *{summary}*")
                    except:
                        lines.append(f"• *{summary}*")
            lines.append("")
        
        # Summary stats
        lines.append(f"*📈 Summary:* {len(completed)} completed | {len(in_progress)} in progress | {len(todo)} todo | {len(prs)} PRs")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error generating standup: {e}", exc_info=True)
        return f"❌ Error generating standup summary: {str(e)}"


async def summarize_pr(pr_number: int) -> str:
    """Generate a summary of PR changes."""
    try:
        pr_context = await get_pr_context(pr_number)
        pr = pr_context.get("pr", {})
        checks = pr_context.get("checks", {})
        reviews = pr_context.get("reviews", [])
        
        lines = [f"📝 *PR #{pr_number} Summary*\n"]
        lines.append(f"*Title:* {pr.get('title', 'N/A')}\n")
        
        # Size
        size = pr.get("pr_size", "unknown")
        lines.append(f"*Size:* {size.upper()}")
        
        # Changes
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)
        files = pr.get("changed_files", 0)
        lines.append(f"*Changes:* +{additions} / -{deletions} lines across {files} files\n")
        
        # CI Status
        ci_status = checks.get("conclusion", "none")
        ci_emoji = "✅" if ci_status == "success" else "❌" if ci_status == "failure" else "⏸️"
        lines.append(f"*CI Status:* {ci_emoji} {ci_status.upper()}\n")
        
        # Reviews
        approvals = sum(1 for r in reviews if r.get("state") == "APPROVED")
        changes_req = sum(1 for r in reviews if r.get("state") == "CHANGES_REQUESTED")
        lines.append(f"*Reviews:* {approvals} approvals, {changes_req} changes requested\n")
        
        # Status
        state = pr.get("state", "unknown")
        mergeable = pr.get("mergeable", False)
        draft = pr.get("draft", False)
        
        if draft:
            lines.append("*Status:* 📝 Draft")
        elif mergeable and approvals > 0 and ci_status == "success":
            lines.append("*Status:* ✅ Ready to merge!")
        elif changes_req > 0:
            lines.append("*Status:* ⚠️ Changes requested")
        else:
            lines.append(f"*Status:* {state.upper()}")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error summarizing PR: {e}", exc_info=True)
        return f"❌ Error summarizing PR #{pr_number}: {str(e)}"


async def summarize_jira_issue(issue_key: str) -> str:
    """Generate a summary of Jira issue changes."""
    try:
        issue = await get_single_issue(issue_key)
        issue_dict = issue.model_dump()
        
        lines = [f"📋 *{issue_key} Summary*\n"]
        lines.append(f"*Title:* {issue_dict.get('summary', 'N/A')}\n")
        
        # Status
        status = issue_dict.get("status", "Unknown")
        priority = issue_dict.get("priority", "None")
        lines.append(f"*Status:* {status} | *Priority:* {priority}\n")
        
        # Assignee
        assignee = issue_dict.get("assignee", "Unassigned")
        lines.append(f"*Assignee:* {assignee}\n")
        
        # Due date
        due_time = issue_dict.get("due_time")
        if due_time:
            lines.append(f"*Due:* {due_time}\n")
        
        # Description
        description = issue_dict.get("description")
        if description:
            # Truncate long descriptions
            desc_preview = description[:200] + "..." if len(description) > 200 else description
            lines.append(f"*Description:* {desc_preview}\n")
        
        # Labels
        labels = issue_dict.get("labels", [])
        if labels:
            lines.append(f"*Labels:* {', '.join(labels)}\n")
        
        # Age
        created = issue_dict.get("created")
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                age_days = (datetime.now(created_dt.tzinfo) - created_dt).days
                lines.append(f"*Age:* {age_days} days")
            except:
                pass
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error summarizing Jira issue: {e}", exc_info=True)
        return f"❌ Error summarizing issue {issue_key}: {str(e)}"


async def get_context_suggestions(user_id: str, user_email: Optional[str] = None, github_username: Optional[str] = None) -> str:
    """Generate context-aware suggestions for the user."""
    try:
        suggestions = []
        
        # Get user's issues (defaults to board 1)
        issues = await get_user_jira_issues(user_email, board_id=1)
        
        # Check for overdue issues
        overdue = []
        for issue in issues:
            due_time = issue.get("due_time")
            if due_time:
                try:
                    due_dt = datetime.fromisoformat(due_time.replace('Z', '+00:00'))
                    if due_dt < datetime.now(due_dt.tzinfo):
                        overdue.append(issue)
                except:
                    pass
        
        if overdue:
            suggestions.append(f"⚠️ *{len(overdue)} overdue task(s)*: {', '.join([i.get('key', 'N/A') for i in overdue[:3]])}")
        
        # Check for high priority issues
        high_priority = [i for i in issues if (i.get("priority") or "").lower() in ["high", "critical", "highest"]]
        if high_priority:
            suggestions.append(f"🔥 *{len(high_priority)} high priority task(s)* need attention")
        
        # Get PRs
        prs = await get_user_prs(github_username)
        
        # Check for PRs ready to merge
        ready_prs = []
        for pr in prs:
            pr_num = pr.get("number")
            if pr_num:
                try:
                    pr_context = await get_pr_context(pr_num)
                    if (pr_context.get("ci_status") == "success" and 
                        pr_context.get("approval_count", 0) > 0 and
                        not pr_context.get("changes_requested", False)):
                        ready_prs.append(pr_num)
                except:
                    pass
        
        if ready_prs:
            suggestions.append(f"✅ *{len(ready_prs)} PR(s) ready to merge*: {', '.join([f'#{p}' for p in ready_prs[:3]])}")
        
        # Check for PRs with failures
        failed_prs = []
        for pr in prs:
            pr_num = pr.get("number")
            if pr_num:
                try:
                    pr_context = await get_pr_context(pr_num)
                    if pr_context.get("ci_status") == "failure":
                        failed_prs.append(pr_num)
                except:
                    pass
        
        if failed_prs:
            suggestions.append(f"❌ *{len(failed_prs)} PR(s) with CI failures*: {', '.join([f'#{p}' for p in failed_prs[:3]])}")
        
        if not suggestions:
            return "✨ *All good!* No urgent items need attention right now."
        
        return "💡 *Suggestions:*\n" + "\n".join(f"• {s}" for s in suggestions)
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}", exc_info=True)
        return f"❌ Error generating suggestions: {str(e)}"


async def get_team_workload() -> str:
    """Generate team workload dashboard."""
    try:
        # Get all open issues
        all_issues = await get_jira_issues("status != Done AND status != Closed")
        
        # Group by assignee
        by_assignee = {}
        for issue in all_issues:
            assignee = issue.assignee or "Unassigned"
            if assignee not in by_assignee:
                by_assignee[assignee] = []
            by_assignee[assignee].append(issue)
        
        lines = ["👥 *Team Workload Dashboard*\n"]
        
        # Sort by workload (most tasks first)
        sorted_assignees = sorted(by_assignee.items(), key=lambda x: len(x[1]), reverse=True)
        
        for assignee, issues in sorted_assignees[:10]:  # Top 10
            count = len(issues)
            # Categorize
            in_progress = sum(1 for i in issues if (i.status or "").lower() in ["in progress", "in development"])
            todo = sum(1 for i in issues if (i.status or "").lower() in ["to do", "open"])
            
            # Workload indicator
            if count > 10:
                indicator = "🔴 Overloaded"
            elif count > 5:
                indicator = "🟡 Busy"
            else:
                indicator = "🟢 Normal"
            
            lines.append(f"*{assignee}*: {indicator} ({count} tasks)")
            lines.append(f"  • {in_progress} in progress, {todo} todo")
        
        # Summary
        total = len(all_issues)
        unassigned = len(by_assignee.get("Unassigned", []))
        lines.append(f"\n*📊 Summary:* {total} total tasks, {unassigned} unassigned")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error getting team workload: {e}", exc_info=True)
        return f"❌ Error generating workload dashboard: {str(e)}"


def create_action_buttons(issue_key: Optional[str] = None, pr_number: Optional[int] = None) -> List[Dict]:
    """Create interactive action buttons using Slack Block Kit."""
    blocks = []
    
    if issue_key:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Mark Done"
                    },
                    "style": "primary",
                    "value": f"mark_done_{issue_key}",
                    "action_id": "mark_done"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📅 Reschedule"
                    },
                    "value": f"reschedule_{issue_key}",
                    "action_id": "reschedule"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "👤 Assign to Me"
                    },
                    "value": f"assign_{issue_key}",
                    "action_id": "assign_to_me"
                }
            ]
        })
    
    if pr_number:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve"
                    },
                    "style": "primary",
                    "value": f"approve_{pr_number}",
                    "action_id": "approve_pr"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "👀 Review"
                    },
                    "value": f"review_{pr_number}",
                    "action_id": "review_pr"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📝 Comment"
                    },
                    "value": f"comment_{pr_number}",
                    "action_id": "comment_pr"
                }
            ]
        })
    
    return blocks

