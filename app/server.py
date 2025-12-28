"""
continuum.ai MCP Server

Exposes Jira and GitHub tools via Model Context Protocol (MCP).
"""

import sys
from pathlib import Path

# Add project root to path so 'app' module can be found
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv(project_root / ".env")

# Create MCP server
mcp = FastMCP(
    name="continuum.ai",
    instructions="""
    You are continuum.ai, a context-aware AI productivity agent.
    
    You help users manage their work across Jira and GitHub by:
    - Fetching task information from Jira boards
    - Tracking PR status and reviews on GitHub
    - Providing context for decision-making when users are unavailable
    
    Use the available tools to gather context about tasks and code changes.
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


# =============================================================================
# Run Server
# =============================================================================

if __name__ == "__main__":
    mcp.run()

