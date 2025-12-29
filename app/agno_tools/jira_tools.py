"""
Agno tool functions for Jira operations.

Simple functions that wrap existing Jira functions for Agno.
"""

import logging
from typing import Optional
import asyncio
from app.tools.jira import (
    get_jira_issues,
    get_single_issue,
    get_projects,
    get_boards,
    get_board_issues,
    find_user_by_name,
    create_issue,
    update_issue
)

logger = logging.getLogger(__name__)


async def get_jira_issues_tool(jql: str = "assignee=currentUser()") -> dict:
    """Search Jira issues using JQL (Jira Query Language). Examples: 'assignee=currentUser()', 'project=KAN AND status=Open'"""
    try:
        issues = await get_jira_issues(jql)
        return {
            "success": True,
            "count": len(issues),
            "issues": [issue.model_dump() for issue in issues]
        }
    except Exception as e:
        logger.error(f"Error getting Jira issues: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_jira_issue_tool(issue_key: str) -> dict:
    """Get full details of a Jira issue by its key (e.g., 'KAN-2', 'PROJ-123'). Returns issue details including status, assignee, due_time, labels, etc."""
    try:
        issue = await get_single_issue(issue_key)
        return {"success": True, "issue": issue.model_dump()}
    except Exception as e:
        logger.error(f"Error getting Jira issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_jira_projects_tool() -> dict:
    """List all Jira projects accessible to the user. Returns project id, key, name, and type."""
    try:
        projects = await get_projects()
        return {
            "success": True,
            "count": len(projects),
            "projects": [p.model_dump() for p in projects]
        }
    except Exception as e:
        logger.error(f"Error getting Jira projects: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_jira_boards_tool() -> dict:
    """List all Jira boards (Scrum/Kanban). Returns board id, name, type, and project key."""
    try:
        boards = await get_boards()
        return {
            "success": True,
            "count": len(boards),
            "boards": [b.model_dump() for b in boards]
        }
    except Exception as e:
        logger.error(f"Error getting Jira boards: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_jira_board_issues_tool(board_id: int) -> dict:
    """Get all issues from a Jira board by board ID. Extract board ID from phrases like 'board 1', 'board ID 5', etc."""
    try:
        issues = await get_board_issues(board_id)
        return {
            "success": True,
            "count": len(issues),
            "issues": [issue.model_dump() for issue in issues]
        }
    except Exception as e:
        logger.error(f"Error getting board issues: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def find_jira_user_tool(name: str) -> dict:
    """Find a Jira user by their display name or email address. Returns user accountId, displayName, and emailAddress. Use this before assigning issues to users."""
    try:
        user = await find_user_by_name(name)
        if user:
            return {"success": True, "user": user}
        else:
            return {"success": False, "error": f"User '{name}' not found"}
    except Exception as e:
        logger.error(f"Error finding Jira user: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def create_jira_issue_tool(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    due_time: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[list[str]] = None
) -> dict:
    """Create a new Jira issue. Requires project_key (e.g., 'KAN') and summary (title). Optional: issue_type (default: 'Task'), description, assignee (display name or email), due_time (ISO format), priority, labels."""
    try:
        issue = await create_issue(
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
            description=description,
            assignee=assignee,
            due_time=due_time,
            priority=priority,
            labels=labels
        )
        return {"success": True, "issue": issue.model_dump()}
    except Exception as e:
        logger.error(f"Error creating Jira issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def update_jira_issue_tool(
    issue_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    due_time: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    labels: Optional[list[str]] = None
) -> dict:
    """Update a Jira issue. Requires issue_key (e.g., 'KAN-2'). Optional: summary, description, assignee (display name or email), due_time (ISO format), priority, status, labels. Use find_jira_user first to get assignee details if needed."""
    try:
        issue = await update_issue(
            issue_key=issue_key,
            summary=summary,
            description=description,
            assignee=assignee,
            due_time=due_time,
            priority=priority,
            status=status,
            labels=labels
        )
        return {"success": True, "issue": issue.model_dump()}
    except Exception as e:
        logger.error(f"Error updating Jira issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
