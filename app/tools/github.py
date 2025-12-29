import httpx
import os
from pydantic import BaseModel
from fastapi import HTTPException


class GitHubPR(BaseModel):
    """Represents a GitHub Pull Request."""
    number: int
    title: str
    state: str  # open, closed
    draft: bool
    user: str
    created_at: str
    updated_at: str
    html_url: str


class GitHubPRDetail(GitHubPR):
    """Extended PR with CI, approval, and size info."""
    # Size metrics
    additions: int
    deletions: int
    changed_files: int
    pr_size: str  # small, medium, large
    
    # Review status
    mergeable: bool | None
    merged: bool
    
    # Branch info
    head_branch: str
    base_branch: str
    
    # Body/description
    body: str | None


class GitHubCheckStatus(BaseModel):
    """CI/CD check status for a PR."""
    total_count: int
    conclusion: str | None  # success, failure, pending, null
    checks: list[dict]


class GitHubReview(BaseModel):
    """A PR review."""
    user: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, PENDING
    submitted_at: str | None


class GitHubCommit(BaseModel):
    """A commit."""
    sha: str
    message: str
    author: str
    date: str
    html_url: str


class GitHubRepo(BaseModel):
    """A GitHub repository."""
    name: str
    full_name: str
    description: str | None
    html_url: str
    default_branch: str
    open_issues_count: int


def _get_github_headers() -> dict:
    """Get GitHub API headers with authentication."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="GitHub token not configured. Set GITHUB_TOKEN in .env"
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


def _get_default_repo() -> tuple[str, str]:
    """Get default owner/repo from environment."""
    owner = os.getenv("GITHUB_OWNER")
    repo = os.getenv("GITHUB_REPO")
    if not owner or not repo:
        raise HTTPException(
            status_code=500,
            detail="GitHub owner/repo not configured. Set GITHUB_OWNER and GITHUB_REPO in .env"
        )
    return owner, repo


def _calculate_pr_size(additions: int, deletions: int, changed_files: int) -> str:
    """Calculate PR size category."""
    total_changes = additions + deletions
    if total_changes <= 50 and changed_files <= 5:
        return "small"
    elif total_changes <= 200 and changed_files <= 10:
        return "medium"
    else:
        return "large"


async def get_repo(owner: str | None = None, repo: str | None = None) -> GitHubRepo:
    """Get repository information."""
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    headers = _get_github_headers()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Repository {owner}/{repo} not found")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Failed to connect to GitHub: {str(e)}")
        
        data = response.json()
        return GitHubRepo(
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description"),
            html_url=data["html_url"],
            default_branch=data["default_branch"],
            open_issues_count=data["open_issues_count"]
        )


async def get_pull_requests(
    owner: str | None = None,
    repo: str | None = None,
    state: str = "open"
) -> list[GitHubPR]:
    """Get pull requests for a repository."""
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    headers = _get_github_headers()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers=headers,
                params={"state": state, "per_page": 30}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Failed to connect to GitHub: {str(e)}")
        
        prs = response.json()
        return [
            GitHubPR(
                number=pr["number"],
                title=pr["title"],
                state=pr["state"],
                draft=pr.get("draft", False),
                user=pr["user"]["login"],
                created_at=pr["created_at"],
                updated_at=pr["updated_at"],
                html_url=pr["html_url"]
            )
            for pr in prs
        ]


async def get_pull_request(
    pr_number: int,
    owner: str | None = None,
    repo: str | None = None
) -> GitHubPRDetail:
    """Get detailed information about a specific PR."""
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    headers = _get_github_headers()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"PR #{pr_number} not found")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Failed to connect to GitHub: {str(e)}")
        
        pr = response.json()
        
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)
        changed_files = pr.get("changed_files", 0)
        
        return GitHubPRDetail(
            number=pr["number"],
            title=pr["title"],
            state=pr["state"],
            draft=pr.get("draft", False),
            user=pr["user"]["login"],
            created_at=pr["created_at"],
            updated_at=pr["updated_at"],
            html_url=pr["html_url"],
            additions=additions,
            deletions=deletions,
            changed_files=changed_files,
            pr_size=_calculate_pr_size(additions, deletions, changed_files),
            mergeable=pr.get("mergeable"),
            merged=pr.get("merged", False),
            head_branch=pr["head"]["ref"],
            base_branch=pr["base"]["ref"],
            body=pr.get("body")
        )


async def get_pr_checks(
    pr_number: int,
    owner: str | None = None,
    repo: str | None = None
) -> GitHubCheckStatus:
    """Get CI/CD check status for a PR."""
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    headers = _get_github_headers()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First get the PR to find the head SHA
        try:
            pr_response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers
            )
            pr_response.raise_for_status()
            pr_data = pr_response.json()
            head_sha = pr_data["head"]["sha"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"PR #{pr_number} not found")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        
        # Get check runs for the commit
        try:
            checks_response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
                headers=headers
            )
            checks_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Failed to connect to GitHub: {str(e)}")
        
        data = checks_response.json()
        check_runs = data.get("check_runs", [])
        
        # Determine overall conclusion
        if not check_runs:
            overall = None
        elif all(c.get("conclusion") == "success" for c in check_runs):
            overall = "success"
        elif any(c.get("conclusion") == "failure" for c in check_runs):
            overall = "failure"
        elif any(c.get("status") == "in_progress" for c in check_runs):
            overall = "pending"
        else:
            overall = "unknown"
        
        return GitHubCheckStatus(
            total_count=data.get("total_count", 0),
            conclusion=overall,
            checks=[
                {
                    "name": c["name"],
                    "status": c["status"],
                    "conclusion": c.get("conclusion")
                }
                for c in check_runs
            ]
        )


async def get_pr_reviews(
    pr_number: int,
    owner: str | None = None,
    repo: str | None = None
) -> list[GitHubReview]:
    """Get reviews for a PR."""
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    headers = _get_github_headers()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"PR #{pr_number} not found")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Failed to connect to GitHub: {str(e)}")
        
        reviews = response.json()
        return [
            GitHubReview(
                user=review["user"]["login"],
                state=review["state"],
                submitted_at=review.get("submitted_at")
            )
            for review in reviews
        ]


async def get_recent_commits(
    owner: str | None = None,
    repo: str | None = None,
    author: str | None = None,
    per_page: int = 10
) -> list[GitHubCommit]:
    """Get recent commits, optionally filtered by author."""
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    headers = _get_github_headers()
    params = {"per_page": per_page}
    if author:
        params["author"] = author
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                headers=headers,
                params=params
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Failed to connect to GitHub: {str(e)}")
        
        commits = response.json()
        return [
            GitHubCommit(
                sha=commit["sha"][:7],
                message=commit["commit"]["message"].split("\n")[0],  # First line only
                author=commit["commit"]["author"]["name"],
                date=commit["commit"]["author"]["date"],
                html_url=commit["html_url"]
            )
            for commit in commits
        ]


async def get_pr_context(
    pr_number: int,
    owner: str | None = None,
    repo: str | None = None
) -> dict:
    """
    Get comprehensive PR context for agent decision-making.
    Combines PR details, checks, and reviews into a single response.
    """
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    # Fetch all data in parallel
    pr_detail = await get_pull_request(pr_number, owner, repo)
    checks = await get_pr_checks(pr_number, owner, repo)
    reviews = await get_pr_reviews(pr_number, owner, repo)
    
    # Count approvals
    approvals = sum(1 for r in reviews if r.state == "APPROVED")
    changes_requested = any(r.state == "CHANGES_REQUESTED" for r in reviews)
    
    return {
        "pr": pr_detail.model_dump(),
        "ci_status": checks.conclusion or "none",
        "checks": checks.model_dump(),
        "reviews": [r.model_dump() for r in reviews],
        "approval_count": approvals,
        "changes_requested": changes_requested,
        # Agent-friendly summary
        "context_summary": {
            "pr_size": pr_detail.pr_size,
            "ci_passed": checks.conclusion == "success",
            "is_mergeable": pr_detail.mergeable and not pr_detail.draft,
            "approvals": approvals,
            "has_blockers": changes_requested or checks.conclusion == "failure"
        }
    }


async def create_pull_request(
    title: str,
    body: str | None = None,
    head: str | None = None,
    base: str = "main",
    owner: str | None = None,
    repo: str | None = None
) -> GitHubPRDetail:
    """
    Create a new pull request.
    
    Args:
        title: PR title
        body: PR description/body
        head: Source branch (required - must exist)
        base: Target branch (default: "main")
        owner: Repository owner (default: from env)
        repo: Repository name (default: from env)
    
    Returns:
        Created PR details
    """
    headers = _get_github_headers()
    if not owner or not repo:
        owner, repo = _get_default_repo()
    
    # Head branch is required
    if not head:
        raise HTTPException(
            status_code=400,
            detail="head branch is required. Create a branch first or specify existing branch."
        )
    
    payload = {
        "title": title,
        "head": head,
        "base": base
    }
    
    if body:
        payload["body"] = body
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to GitHub: {str(e)}"
            )
        
        pr_data = response.json()
        pr_number = pr_data["number"]
        
        # Fetch full PR details
        return await get_pull_request(pr_number, owner, repo)

