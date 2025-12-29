"""
continuum.ai MCP Server

Exposes Jira and GitHub tools via Model Context Protocol (MCP).
"""

import sys
import os
from pathlib import Path

# Add project root to path so 'app' module can be found
# Handle both direct execution and module execution
try:
    # Try to get project root from this file's location
    if __file__:
        project_root = Path(__file__).resolve().parent.parent
    else:
        # Fallback: assume we're in the project root
        project_root = Path.cwd()
except:
    # Ultimate fallback
    project_root = Path.cwd()

# Ensure project root is in path
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try loading from current directory as fallback
    load_dotenv()

# Create MCP server
mcp = FastMCP(
    name="continuum.ai",
    instructions="""
    You are continuum.ai, a context-aware AI productivity agent.
    
    You help users manage their work across Jira, GitHub, and Calendar by:
    - Fetching task information from Jira boards
    - Tracking PR status and reviews on GitHub
    - Checking calendar availability and free time slots
    - Providing context for decision-making when users are unavailable
    
    Use the available tools to gather context about tasks, code changes, and user availability.
    """
)


# =============================================================================
# Jira Tools
# =============================================================================

@mcp.tool
async def get_jira_projects() -> list[dict]:
    """
    List all accessible Jira projects.
    
    Returns a list of projects with id, key, name, and project_type.
    """
    from app.tools.jira import get_projects
    projects = await get_projects()
    return [p.model_dump() for p in projects]


@mcp.tool
async def get_jira_boards() -> list[dict]:
    """
    List all accessible Jira boards (Scrum/Kanban).
    
    Returns a list of boards with id, name, board_type, and project_key.
    """
    from app.tools.jira import get_boards
    boards = await get_boards()
    return [b.model_dump() for b in boards]


@mcp.tool
async def get_jira_board_issues(board_id: int) -> list[dict]:
    """
    Get all issues from a specific Jira board with full details.
    
    Args:
        board_id: The ID of the Jira board
        
    Returns:
        List of issues with key, summary, status, priority, assignee,
        description, issue_type, labels, components, created, updated, due_time.
    """
    from app.tools.jira import get_board_issues
    issues = await get_board_issues(board_id)
    return [i.model_dump() for i in issues]


@mcp.tool
async def get_jira_issues(jql: str = "ORDER BY created DESC") -> list[dict]:
    """
    Fetch Jira issues using JQL (Jira Query Language).
    
    Args:
        jql: JQL query string. Examples:
             - "assignee=currentUser()"
             - "project=PROJ AND status!=Done"
             - "priority=High ORDER BY created DESC"
             
    Returns:
        List of issues matching the query.
    """
    from app.tools.jira import get_jira_issues as fetch_issues
    issues = await fetch_issues(jql)
    return [i.model_dump() for i in issues]


@mcp.tool
async def get_jira_issue(issue_key: str) -> dict:
    """
    Fetch a single Jira issue by its key.
    
    Args:
        issue_key: The issue key (e.g., "PROJ-123")
        
    Returns:
        Full issue details including labels, components, timestamps.
    """
    from app.tools.jira import get_single_issue
    issue = await get_single_issue(issue_key)
    return issue.model_dump()


@mcp.tool
async def get_jira_fields(search: str | None = None) -> list[dict]:
    """
    List all Jira fields. Useful for finding custom field IDs.
    
    Args:
        search: Optional filter to search field names (case-insensitive)
        
    Returns:
        List of fields with id, name, field_type, and is_custom.
    """
    from app.tools.jira import get_fields
    fields = await get_fields(search)
    return [f.model_dump() for f in fields]


@mcp.tool
async def create_jira_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str | None = None,
    assignee: str | None = None,
    due_time: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None
) -> dict:
    """
    Create a new Jira issue.
    
    Args:
        project_key: Project key (e.g., "KAN")
        summary: Issue title/summary
        issue_type: Issue type (default: "Task")
        description: Issue description
        assignee: Assignee display name or email (will be looked up)
        due_time: Due date/time in ISO format (e.g., "2026-01-02T14:00:00Z")
        priority: Priority name (e.g., "High", "Medium", "Low")
        labels: List of label names
    
    Returns:
        Created Jira issue details
    """
    from app.tools.jira import create_issue
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
    return issue.model_dump()


@mcp.tool
async def update_jira_issue(
    issue_key: str,
    summary: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
    due_time: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    labels: list[str] | None = None
) -> dict:
    """
    Update an existing Jira issue.
    
    Args:
        issue_key: Issue key (e.g., "KAN-123")
        summary: New summary/title (optional)
        description: New description (optional)
        assignee: New assignee display name or email (optional, will be looked up)
        due_time: New due date/time in ISO format (optional)
        priority: New priority name (optional)
        status: New status name (optional - requires transition)
        labels: New labels list (optional)
    
    Returns:
        Updated Jira issue details
    """
    from app.tools.jira import update_issue
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
    return issue.model_dump()


@mcp.tool
async def find_jira_user(name: str) -> dict | None:
    """
    Find Jira user by display name or email.
    
    Args:
        name: User's display name or email
    
    Returns:
        User dict with accountId, displayName, emailAddress, or None if not found
    """
    from app.tools.jira import find_user_by_name
    user = await find_user_by_name(name)
    return user


# =============================================================================
# GitHub Tools
# =============================================================================

@mcp.tool
async def get_github_repo() -> dict:
    """
    Get information about the configured GitHub repository.
    
    Returns:
        Repository details including name, description, default_branch,
        and open_issues_count.
    """
    from app.tools.github import get_repo
    repo = await get_repo()
    return repo.model_dump()


@mcp.tool
async def get_github_pulls(state: str = "open") -> list[dict]:
    """
    List pull requests from the configured repository.
    
    Args:
        state: Filter by PR state - "open", "closed", or "all"
        
    Returns:
        List of PRs with number, title, state, draft status, user, and timestamps.
    """
    from app.tools.github import get_pull_requests
    prs = await get_pull_requests(state=state)
    return [pr.model_dump() for pr in prs]


@mcp.tool
async def get_github_pull(pr_number: int) -> dict:
    """
    Get detailed information about a specific pull request.
    
    Args:
        pr_number: The PR number
        
    Returns:
        Full PR details including additions, deletions, changed_files,
        pr_size (small/medium/large), mergeable status, and branch info.
    """
    from app.tools.github import get_pull_request
    pr = await get_pull_request(pr_number)
    return pr.model_dump()


@mcp.tool
async def get_github_pr_checks(pr_number: int) -> dict:
    """
    Get CI/CD check status for a pull request.
    
    Args:
        pr_number: The PR number
        
    Returns:
        Check status with total_count, overall conclusion 
        (success/failure/pending), and individual check details.
    """
    from app.tools.github import get_pr_checks
    checks = await get_pr_checks(pr_number)
    return checks.model_dump()


@mcp.tool
async def get_github_pr_reviews(pr_number: int) -> list[dict]:
    """
    Get reviews for a pull request.
    
    Args:
        pr_number: The PR number
        
    Returns:
        List of reviews with user, state (APPROVED/CHANGES_REQUESTED/COMMENTED),
        and submitted_at timestamp.
    """
    from app.tools.github import get_pr_reviews
    reviews = await get_pr_reviews(pr_number)
    return [r.model_dump() for r in reviews]


@mcp.tool
async def get_github_pr_context(pr_number: int) -> dict:
    """
    Get comprehensive PR context for agent decision-making.
    
    This is the PRIMARY tool for understanding a PR's readiness.
    Combines PR details, CI status, and reviews into a single response.
    
    Args:
        pr_number: The PR number
        
    Returns:
        Complete context including:
        - pr: Full PR details
        - ci_status: Overall CI conclusion
        - checks: All CI check details
        - reviews: All reviews
        - approval_count: Number of approvals
        - changes_requested: Boolean if changes were requested
        - context_summary: Agent-friendly summary with:
          - pr_size
          - ci_passed
          - is_mergeable
          - approvals
          - has_blockers
    """
    from app.tools.github import get_pr_context
    return await get_pr_context(pr_number)


@mcp.tool
async def get_github_commits(author: str | None = None, per_page: int = 10) -> list[dict]:
    """
    Get recent commits from the repository.
    
    Args:
        author: Optional GitHub username to filter commits by author
        per_page: Number of commits to return (default 10, max 100)
        
    Returns:
        List of commits with sha, message, author, date, and html_url.
    """
    from app.tools.github import get_recent_commits
    commits = await get_recent_commits(author=author, per_page=per_page)
    return [c.model_dump() for c in commits]


@mcp.tool
async def create_github_pr(
    title: str,
    body: str | None = None,
    head: str | None = None,
    base: str = "main"
) -> dict:
    """
    Create a new pull request.
    
    Args:
        title: PR title
        body: PR description/body
        head: Source branch (required - must exist)
        base: Target branch (default: "main")
    
    Returns:
        Created PR details
    """
    from app.tools.github import create_pull_request
    pr = await create_pull_request(
        title=title,
        body=body,
        head=head,
        base=base
    )
    return pr.model_dump()


@mcp.tool
async def update_github_pr(
    pr_number: int,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
    base: str | None = None
) -> dict:
    """
    Update an existing pull request.
    
    Args:
        pr_number: PR number
        title: New title (optional)
        body: New description/body (optional)
        state: New state - "open" or "closed" (optional)
        base: New base branch (optional)
    
    Returns:
        Updated PR details
    """
    from app.tools.github import update_pull_request
    pr = await update_pull_request(
        pr_number=pr_number,
        title=title,
        body=body,
        state=state,
        base=base
    )
    return pr.model_dump()


@mcp.tool
async def update_github_pr_assignees(
    pr_number: int,
    assignees: list[str] | None = None,
    remove_assignees: list[str] | None = None
) -> dict:
    """
    Add or remove assignees from a pull request.
    
    Args:
        pr_number: PR number
        assignees: List of GitHub usernames to add as assignees (optional)
        remove_assignees: List of GitHub usernames to remove as assignees (optional)
    
    Returns:
        Updated assignees list with added/removed info
    """
    from app.tools.github import update_pr_assignees
    return await update_pr_assignees(
        pr_number=pr_number,
        assignees=assignees,
        remove_assignees=remove_assignees
    )


@mcp.tool
async def update_github_pr_labels(
    pr_number: int,
    labels: list[str] | None = None,
    remove_labels: list[str] | None = None
) -> dict:
    """
    Add or remove labels from a pull request.
    
    Args:
        pr_number: PR number
        labels: List of label names to add (optional)
        remove_labels: List of label names to remove (optional)
    
    Returns:
        Updated labels list with added/removed info
    """
    from app.tools.github import update_pr_labels
    return await update_pr_labels(
        pr_number=pr_number,
        labels=labels,
        remove_labels=remove_labels
    )


@mcp.tool
async def request_github_pr_review(
    pr_number: int,
    reviewers: list[str] | None = None,
    team_reviewers: list[str] | None = None
) -> dict:
    """
    Request review from specific users or teams for a pull request.
    
    Args:
        pr_number: PR number
        reviewers: List of GitHub usernames to request review from (optional)
        team_reviewers: List of team slugs to request review from (optional)
    
    Returns:
        Review request result with requested reviewers and teams
    """
    from app.tools.github import request_pr_review
    return await request_pr_review(
        pr_number=pr_number,
        reviewers=reviewers,
        team_reviewers=team_reviewers
    )


# =============================================================================
# Calendar Tools
# =============================================================================

@mcp.tool
async def list_calendars() -> list[dict]:
    """
    List all accessible calendars.
    
    Useful for discovering calendar IDs before fetching events.
    
    Returns:
        List of calendars with id, summary, description, and primary flag.
    """
    from app.tools.calendar import list_calendars as fetch_calendars
    return await fetch_calendars()


@mcp.tool
async def get_calendar_events(
    start_date: str | None = None,
    end_date: str | None = None,
    calendar_id: str = "primary"
) -> list[dict]:
    """
    Get calendar events for a date range.
    
    Args:
        start_date: ISO format date string (e.g., "2025-01-15T00:00:00Z"). Default: today
        end_date: ISO format date string. Default: 7 days from start_date
        calendar_id: Calendar ID. 
            - For OAuth: use "primary" for your main calendar
            - For service accounts: use the user's email (e.g., "user@example.com") 
              after they share their calendar with the service account
        
    Returns:
        List of events with id, summary, start, end, description, location, attendees.
    """
    from app.tools.calendar import get_events
    events = await get_events(start_date, end_date, calendar_id)
    return [e.model_dump() for e in events]


@mcp.tool
async def get_today_events(calendar_id: str = "primary") -> list[dict]:
    """
    Get all events scheduled for today.
    
    Args:
        calendar_id: Calendar ID (default: "primary")
        
    Returns:
        List of today's events.
    """
    from app.tools.calendar import get_today_events
    events = await get_today_events(calendar_id)
    return [e.model_dump() for e in events]


@mcp.tool
async def get_calendar_availability(
    start_date: str | None = None,
    end_date: str | None = None,
    calendar_id: str = "primary",
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> dict:
    """
    Get calendar availability including free time slots for scheduling.
    
    This is the PRIMARY tool for checking if user is available.
    
    Args:
        start_date: ISO format date string (default: today)
        end_date: ISO format date string (default: 7 days from start)
        calendar_id: Calendar ID (default: "primary")
        work_hours_start: Start of workday hour (0-23, default: 9)
        work_hours_end: End of workday hour (0-23, default: 17)
        
    Returns:
        Availability object with:
        - events: All calendar events
        - free_slots: Available time slots (>= 15 minutes)
        - busy_hours: Total hours blocked by events
        - free_hours: Total hours available for scheduling
    """
    from app.tools.calendar import get_availability
    availability = await get_availability(
        start_date, end_date, calendar_id, work_hours_start, work_hours_end
    )
    return availability.model_dump()


@mcp.tool
async def get_this_week_availability(
    calendar_id: str = "primary",
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> dict:
    """
    Get availability for the current week (today + 7 days).
    
    Convenience tool that returns free slots where tasks can be scheduled.
    
    Args:
        calendar_id: Calendar ID (default: "primary")
        work_hours_start: Start of workday hour (0-23, default: 9)
        work_hours_end: End of workday hour (0-23, default: 17)
        
    Returns:
        Availability with events and free slots for the week.
    """
    from app.tools.calendar import get_this_week_availability
    availability = await get_this_week_availability(calendar_id, work_hours_start, work_hours_end)
    return availability.model_dump()


# =============================================================================
# Run Server
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run continuum.ai MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport type: stdio (local) or http (network)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (for HTTP transport, default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (for HTTP transport, default: 8000)"
    )
    
    args = parser.parse_args()
    
    if args.transport == "http":
        # Ensure we're in the project root directory
        os.chdir(project_root)
        
        print(f"🚀 Starting continuum.ai MCP Server (HTTP)")
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   Working Directory: {os.getcwd()}")
        print(f"   Access at: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/mcp/")
        print()
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        # STDIO transport (for local MCP clients)
        mcp.run()

