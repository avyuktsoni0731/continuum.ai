import httpx
import os
from pydantic import BaseModel
from fastapi import HTTPException


class JiraIssue(BaseModel):
    """Represents a Jira issue."""
    key: str
    summary: str
    status: str
    priority: str | None = None
    assignee: str | None = None
    description: str | None = None
    issue_type: str | None = None


class JiraIssueDetail(JiraIssue):
    """Extended Jira issue with more details."""
    labels: list[str] = []
    components: list[str] = []
    created: str | None = None
    updated: str | None = None
    due_time: str | None = None


class JiraProject(BaseModel):
    """Represents a Jira project."""
    id: str
    key: str
    name: str
    project_type: str | None = None


class JiraBoard(BaseModel):
    """Represents a Jira board."""
    id: int
    name: str
    board_type: str
    project_key: str | None = None


class JiraField(BaseModel):
    """Represents a Jira field."""
    id: str
    name: str
    field_type: str | None = None
    is_custom: bool = False


def _get_jira_auth() -> httpx.BasicAuth:
    """Get Jira authentication credentials."""
    user = os.getenv("JIRA_API_USER")
    token = os.getenv("JIRA_API_TOKEN")
    if not user or not token:
        raise HTTPException(
            status_code=500,
            detail="Jira credentials not configured. Set JIRA_API_USER and JIRA_API_TOKEN."
        )
    return httpx.BasicAuth(user, token)


def _get_jira_base_url() -> str:
    """Get Jira base URL."""
    url = os.getenv("JIRA_BASE_URL")
    if not url:
        raise HTTPException(
            status_code=500,
            detail="Jira base URL not configured. Set JIRA_BASE_URL."
        )
    return url.rstrip("/")


def _extract_description(description_field) -> str | None:
    """Extract plain text from Jira v3 ADF description format."""
    if description_field is None:
        return None
    if isinstance(description_field, str):
        return description_field
    # Jira v3 uses Atlassian Document Format (ADF)
    if isinstance(description_field, dict) and "content" in description_field:
        texts = []
        for block in description_field.get("content", []):
            for item in block.get("content", []):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
        return " ".join(texts) if texts else None
    return str(description_field)


async def get_jira_issues(jql: str = "assignee=currentUser()") -> list[JiraIssue]:
    """Fetch issues from Jira using JQL query (v3 API)."""
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Jira v3 uses POST with JQL in body
            response = await client.post(
                f"{base_url}/rest/api/3/search/jql",
                auth=auth,
                json={"jql": jql, "maxResults": 50}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Jira API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Jira: {str(e)}"
            )
        
        data = response.json()
        issues = data.get("issues", [])
        
        return [
            JiraIssue(
                key=issue["key"],
                summary=issue["fields"]["summary"],
                status=issue["fields"]["status"]["name"],
                priority=(issue["fields"].get("priority") or {}).get("name"),
                assignee=(issue["fields"].get("assignee") or {}).get("displayName"),
                description=_extract_description(issue["fields"].get("description")),
                issue_type=(issue["fields"].get("issuetype") or {}).get("name")
            )
            for issue in issues
        ]


async def get_single_issue(issue_key: str) -> JiraIssueDetail:
    """Fetch a single Jira issue by its key (v3 API)."""
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{base_url}/rest/api/3/issue/{issue_key}",
                auth=auth
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Issue {issue_key} not found"
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Jira API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Jira: {str(e)}"
            )
        
        issue = response.json()
        fields = issue["fields"]
        
        return JiraIssueDetail(
            key=issue["key"],
            summary=fields["summary"],
            status=fields["status"]["name"],
            priority=(fields.get("priority") or {}).get("name"),
            assignee=(fields.get("assignee") or {}).get("displayName"),
            description=_extract_description(fields.get("description")),
            issue_type=(fields.get("issuetype") or {}).get("name"),
            labels=fields.get("labels", []),
            components=[c["name"] for c in fields.get("components", [])],
            created=fields.get("created"),
            updated=fields.get("updated"),
            due_time=fields.get("customfield_10039")
        )


async def get_projects() -> list[JiraProject]:
    """Fetch all accessible Jira projects."""
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{base_url}/rest/api/3/project",
                auth=auth
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Jira API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Jira: {str(e)}"
            )
        
        projects = response.json()
        return [
            JiraProject(
                id=project["id"],
                key=project["key"],
                name=project["name"],
                project_type=project.get("projectTypeKey")
            )
            for project in projects
        ]


async def get_boards() -> list[JiraBoard]:
    """Fetch all accessible Jira boards (Agile API)."""
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{base_url}/rest/agile/1.0/board",
                auth=auth
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Jira API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Jira: {str(e)}"
            )
        
        data = response.json()
        boards = data.get("values", [])
        return [
            JiraBoard(
                id=board["id"],
                name=board["name"],
                board_type=board.get("type", "unknown"),
                project_key=board.get("location", {}).get("projectKey")
            )
            for board in boards
        ]


async def get_fields(search: str | None = None) -> list[JiraField]:
    """Fetch all Jira fields. Optionally filter by name."""
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{base_url}/rest/api/3/field",
                auth=auth
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Jira API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Jira: {str(e)}"
            )
        
        fields = response.json()
        result = [
            JiraField(
                id=field["id"],
                name=field["name"],
                field_type=field.get("schema", {}).get("type"),
                is_custom=field.get("custom", False)
            )
            for field in fields
        ]
        
        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            result = [f for f in result if search_lower in f.name.lower()]
        
        return result


async def get_board_issues(board_id: int) -> list[JiraIssueDetail]:
    """Fetch all issues from a specific Jira board with full details."""
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{base_url}/rest/agile/1.0/board/{board_id}/issue",
                auth=auth,
                params={"maxResults": 50}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Board {board_id} not found"
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Jira API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Jira: {str(e)}"
            )
        
        data = response.json()
        issues = data.get("issues", [])
        
        return [
            JiraIssueDetail(
                key=issue["key"],
                summary=issue["fields"]["summary"],
                status=issue["fields"]["status"]["name"],
                priority=(issue["fields"].get("priority") or {}).get("name"),
                assignee=(issue["fields"].get("assignee") or {}).get("displayName"),
                description=_extract_description(issue["fields"].get("description")),
                issue_type=(issue["fields"].get("issuetype") or {}).get("name"),
                labels=issue["fields"].get("labels", []),
                components=[c["name"] for c in issue["fields"].get("components", [])],
                created=issue["fields"].get("created"),
                updated=issue["fields"].get("updated"),
                due_time=issue["fields"].get("customfield_10039")
            )
            for issue in issues
        ]