"""
Agno tool functions for GitHub operations.

Simple functions that wrap existing GitHub functions for Agno.
"""

import logging
from typing import Optional
from app.tools.github import (
    get_pull_requests,
    get_pull_request,
    get_pr_context,
    get_pr_checks,
    get_pr_reviews,
    get_recent_commits,
    get_repo,
    create_pull_request,
    update_pull_request,
    update_pr_assignees,
    update_pr_labels,
    request_pr_review
)

logger = logging.getLogger(__name__)


async def get_github_pulls_tool(state: str = "open", owner: Optional[str] = None, repo: Optional[str] = None) -> dict:
    """List pull requests. Use state='open' (default), 'closed', or 'all'."""
    try:
        prs = await get_pull_requests(owner=owner, repo=repo, state=state)
        return {
            "success": True,
            "count": len(prs),
            "pulls": [pr.model_dump() for pr in prs]
        }
    except Exception as e:
        logger.error(f"Error getting GitHub PRs: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_github_pull_tool(pr_number: int, owner: Optional[str] = None, repo: Optional[str] = None) -> dict:
    """Get details of a specific PR by number. Returns PR details including title, state, size, branches, etc."""
    try:
        pr = await get_pull_request(pr_number, owner=owner, repo=repo)
        return {"success": True, "pull": pr.model_dump()}
    except Exception as e:
        logger.error(f"Error getting GitHub PR {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_github_pr_context_tool(pr_number: int, owner: Optional[str] = None, repo: Optional[str] = None) -> dict:
    """Get comprehensive PR context including CI status, reviews, and approvals. Returns full context for decision-making."""
    try:
        context = await get_pr_context(pr_number, owner=owner, repo=repo)
        return {"success": True, **context}
    except Exception as e:
        logger.error(f"Error getting GitHub PR context {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_github_pr_checks_tool(pr_number: int, owner: Optional[str] = None, repo: Optional[str] = None) -> dict:
    """Get CI/CD check status for a PR. Returns check runs and overall conclusion."""
    try:
        checks = await get_pr_checks(pr_number, owner=owner, repo=repo)
        return {"success": True, "checks": checks.model_dump()}
    except Exception as e:
        logger.error(f"Error getting GitHub PR checks {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_github_pr_reviews_tool(pr_number: int, owner: Optional[str] = None, repo: Optional[str] = None) -> dict:
    """Get reviews for a PR. Returns list of reviews with user, state, and timestamp."""
    try:
        reviews = await get_pr_reviews(pr_number, owner=owner, repo=repo)
        return {
            "success": True,
            "count": len(reviews),
            "reviews": [review.model_dump() for review in reviews]
        }
    except Exception as e:
        logger.error(f"Error getting GitHub PR reviews {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_github_commits_tool(
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    author: Optional[str] = None,
    per_page: int = 10
) -> dict:
    """Get recent commits from the repository. Optionally filter by author."""
    try:
        commits = await get_recent_commits(owner=owner, repo=repo, author=author, per_page=per_page)
        return {
            "success": True,
            "count": len(commits),
            "commits": [commit.model_dump() for commit in commits]
        }
    except Exception as e:
        logger.error(f"Error getting GitHub commits: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_github_repo_tool(owner: Optional[str] = None, repo: Optional[str] = None) -> dict:
    """Get information about the GitHub repository. Returns repo details including name, description, default branch, etc."""
    try:
        repo_info = await get_repo(owner=owner, repo=repo)
        return {"success": True, "repo": repo_info.model_dump()}
    except Exception as e:
        logger.error(f"Error getting GitHub repo: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def create_github_pr_tool(
    title: str,
    body: Optional[str] = None,
    head: Optional[str] = None,
    base: str = "main",
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> dict:
    """Create a new pull request. Requires title and head branch. Optionally specify body/description and base branch."""
    try:
        pr = await create_pull_request(
            title=title,
            body=body,
            head=head,
            base=base,
            owner=owner,
            repo=repo
        )
        return {"success": True, "pull": pr.model_dump()}
    except Exception as e:
        logger.error(f"Error creating GitHub PR: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def update_github_pr_tool(
    pr_number: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    description: Optional[str] = None,  # Alias for body
    state: Optional[str] = None,  # 'open' or 'closed'
    base: Optional[str] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> dict:
    """Update an existing PR. Can update title, body/description, state (open/closed), or base branch. Use 'description' parameter as alias for body."""
    try:
        # Use description if provided, otherwise body
        body_to_use = description if description else body
        pr = await update_pull_request(
            pr_number=pr_number,
            title=title,
            body=body_to_use,
            state=state,
            base=base,
            owner=owner,
            repo=repo
        )
        return {"success": True, "pull": pr.model_dump()}
    except Exception as e:
        logger.error(f"Error updating GitHub PR {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def update_github_pr_assignees_tool(
    pr_number: int,
    assignees: Optional[list[str]] = None,
    remove_assignees: Optional[list[str]] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> dict:
    """Add or remove assignees from a PR. Provide list of GitHub usernames to add or remove."""
    try:
        result = await update_pr_assignees(
            pr_number=pr_number,
            assignees=assignees,
            remove_assignees=remove_assignees,
            owner=owner,
            repo=repo
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error updating GitHub PR assignees {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def update_github_pr_labels_tool(
    pr_number: int,
    labels: Optional[list[str]] = None,
    remove_labels: Optional[list[str]] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> dict:
    """Add or remove labels from a PR. Provide list of label names to add or remove."""
    try:
        result = await update_pr_labels(
            pr_number=pr_number,
            labels=labels,
            remove_labels=remove_labels,
            owner=owner,
            repo=repo
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error updating GitHub PR labels {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def request_github_pr_review_tool(
    pr_number: int,
    reviewers: Optional[list[str]] = None,
    team_reviewers: Optional[list[str]] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> dict:
    """Request review from specific users or teams for a PR. Provide list of GitHub usernames or team slugs."""
    try:
        result = await request_pr_review(
            pr_number=pr_number,
            reviewers=reviewers,
            team_reviewers=team_reviewers,
            owner=owner,
            repo=repo
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error requesting GitHub PR review {pr_number}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

