from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="continuum.ai",
    description="Context-aware AI productivity agent",
    version="0.1.0"
)


@app.get("/")
async def root():
    """API root - shows available endpoints."""
    return {
        "service": "continuum.ai",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "jira_projects": "/tools/jira/projects",
            "jira_boards": "/tools/jira/boards",
            "jira_board_issues": "/tools/jira/boards/{board_id}/issues",
            "jira_issues": "/tools/jira/issues",
            "jira_issue": "/tools/jira/issue/{issue_key}"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "continuum.ai"}


@app.get("/tools/jira/projects")
async def list_jira_projects():
    """List all accessible Jira projects."""
    from app.tools.jira import get_projects
    return await get_projects()


@app.get("/tools/jira/boards")
async def list_jira_boards():
    """List all accessible Jira boards."""
    from app.tools.jira import get_boards
    return await get_boards()


@app.get("/tools/jira/fields")
async def list_jira_fields(search: str | None = None):
    """List all Jira fields. Use ?search=due to filter by name."""
    from app.tools.jira import get_fields
    return await get_fields(search)


@app.get("/tools/jira/boards/{board_id}/issues")
async def get_board_issues(board_id: int):
    """Get all issues from a specific Jira board."""
    from app.tools.jira import get_board_issues as fetch_board_issues
    return await fetch_board_issues(board_id)


@app.get("/tools/jira/issues")
async def get_jira_issues(jql: str = "ORDER BY created DESC"):
    """Fetch Jira issues using JQL query."""
    from app.tools.jira import get_jira_issues as fetch_issues
    return await fetch_issues(jql)


@app.get("/tools/jira/issue/{issue_key}")
async def get_jira_issue(issue_key: str):
    """Fetch a single Jira issue by key."""
    from app.tools.jira import get_single_issue
    return await get_single_issue(issue_key)