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
            # Use standard search endpoint which is more reliable
            response = await client.post(
                f"{base_url}/rest/api/3/search",
                auth=auth,
                json={
                    "jql": jql,
                    "maxResults": 50,
                    "fields": ["key", "summary", "status", "priority", "assignee", "description", "issuetype"]
                }
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
        # Standard search endpoint returns issues in "issues" array
        issues = data.get("issues", [])
        
        result = []
        for issue in issues:
            try:
                # Standard structure: issue has "key" and "fields"
                issue_key = issue.get("key")
                if not issue_key:
                    continue
                
                fields = issue.get("fields", {})
                
                result.append(JiraIssue(
                    key=issue_key,
                    summary=fields.get("summary", "No summary"),
                    status=fields.get("status", {}).get("name", "Unknown") if isinstance(fields.get("status"), dict) else str(fields.get("status", "Unknown")),
                    priority=(fields.get("priority") or {}).get("name") if isinstance(fields.get("priority"), dict) else fields.get("priority"),
                    assignee=(fields.get("assignee") or {}).get("displayName") if isinstance(fields.get("assignee"), dict) else fields.get("assignee"),
                    description=_extract_description(fields.get("description")),
                    issue_type=(fields.get("issuetype") or {}).get("name") if isinstance(fields.get("issuetype"), dict) else fields.get("issuetype")
                ))
            except Exception as e:
                # Log and skip malformed issues
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Skipping malformed issue: {issue}, error: {e}")
                continue
        
        return result


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


async def find_user_by_name(name: str) -> dict | None:
    """
    Find Jira user by display name or email.
    
    Args:
        name: User's display name or email
    
    Returns:
        User dict with accountId, displayName, emailAddress, or None if not found
    """
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Search for users
            response = await client.get(
                f"{base_url}/rest/api/3/user/search",
                auth=auth,
                params={"query": name, "maxResults": 10}
            )
            response.raise_for_status()
            users = response.json()
            
            # Try to find exact match by display name or email
            name_lower = name.lower()
            for user in users:
                display_name = (user.get("displayName") or "").lower()
                email = (user.get("emailAddress") or "").lower()
                if name_lower in display_name or name_lower in email:
                    return {
                        "accountId": user.get("accountId"),
                        "displayName": user.get("displayName"),
                        "emailAddress": user.get("emailAddress")
                    }
            
            # Return first result if no exact match
            if users:
                return {
                    "accountId": users[0].get("accountId"),
                    "displayName": users[0].get("displayName"),
                    "emailAddress": users[0].get("emailAddress")
                }
            
            return None
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Jira API error: {e.response.text}"
            )


async def create_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str | None = None,
    assignee: str | None = None,
    due_time: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None
) -> JiraIssueDetail:
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
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    # Build issue fields
    fields = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type}
    }
    
    # Add description if provided
    if description:
        # Convert plain text to ADF format for Jira v3
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": description
                        }
                    ]
                }
            ]
        }
    
    # Look up assignee if provided
    if assignee:
        user = await find_user_by_name(assignee)
        if user and user.get("accountId"):
            fields["assignee"] = {"accountId": user["accountId"]}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"User '{assignee}' not found in Jira"
            )
    
    # Add due_time (custom field customfield_10039)
    if due_time:
        fields["customfield_10039"] = due_time
    
    # Add priority if provided
    if priority:
        fields["priority"] = {"name": priority}
    
    # Add labels if provided
    if labels:
        fields["labels"] = labels
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{base_url}/rest/api/3/issue",
                auth=auth,
                json={"fields": fields}
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
        
        created_issue = response.json()
        issue_key = created_issue["key"]
        
        # Fetch full issue details
        return await get_single_issue(issue_key)


async def update_issue(
    issue_key: str,
    summary: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
    due_time: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    labels: list[str] | None = None
) -> JiraIssueDetail:
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
    auth = _get_jira_auth()
    base_url = _get_jira_base_url()
    
    # Build update fields
    fields = {}
    
    if summary:
        fields["summary"] = summary
    
    if description:
        # Convert plain text to ADF format
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": description
                        }
                    ]
                }
            ]
        }
    
    # Look up assignee if provided
    if assignee:
        user = await find_user_by_name(assignee)
        if user and user.get("accountId"):
            fields["assignee"] = {"accountId": user["accountId"]}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"User '{assignee}' not found in Jira"
            )
    
    # Add due_time (custom field customfield_10039)
    if due_time:
        fields["customfield_10039"] = due_time
    
    # Add priority if provided
    if priority:
        fields["priority"] = {"name": priority}
    
    # Add labels if provided
    if labels:
        fields["labels"] = labels
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Update issue fields
            if fields:
                response = await client.put(
                    f"{base_url}/rest/api/3/issue/{issue_key}",
                    auth=auth,
                    json={"fields": fields}
                )
                response.raise_for_status()
            
            # Handle status transition if provided
            if status:
                # First, get available transitions
                transitions_response = await client.get(
                    f"{base_url}/rest/api/3/issue/{issue_key}/transitions",
                    auth=auth
                )
                transitions_response.raise_for_status()
                transitions = transitions_response.json().get("transitions", [])
                
                # Find matching transition
                transition_id = None
                for transition in transitions:
                    if transition["to"]["name"].lower() == status.lower():
                        transition_id = transition["id"]
                        break
                
                if transition_id:
                    await client.post(
                        f"{base_url}/rest/api/3/issue/{issue_key}/transitions",
                        auth=auth,
                        json={"transition": {"id": transition_id}}
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Status transition to '{status}' not available. Available: {[t['to']['name'] for t in transitions]}"
                    )
            
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
        
        # Fetch updated issue details
        return await get_single_issue(issue_key)