"""
Configuration for teammate data.

In production, this should fetch from:
- GitHub API (contributors, code owners)
- Jira API (project members, assignees)
- Slack API (team members)
- Database/config file
"""

from typing import List
from app.delegation.models import Teammate


# TODO: Replace with actual data fetching
TEAMMATES_CONFIG = [
    {
        "username": "Shashank Chauhan",
        "github_username": "DevInIndia",
        "slack_user_id": "U0A6A9944CR",  # Replace with actual Slack user ID
        "email": "shashankchauhan2518@gmail.com",
        "timezone": "Asia/Kolkata",
        "components": ["frontend", "UI/UX"],  # Jira components they own
        "file_patterns": ["src/", "components/"]  # Code ownership patterns
    },
    {
        "username": "soniavyukt",
        "github_username": "avyuktsoni0731",
        "slack_user_id": "U0A6A995F2M",  # Replace with actual Slack user ID
        "email": "soniavyukt@gmail.com",
        "timezone": "Asia/Kolkata",
        "components": ["frontend", "backend", "devops", "UI/UX"],
        "file_patterns": ["frontend/", "backend/", "devops/", "components/"]
    },
]


async def load_teammates_from_config() -> List[Teammate]:
    """Load teammates from configuration."""
    teammates = []
    
    for config in TEAMMATES_CONFIG:
        teammates.append(Teammate(
            username=config["username"],
            github_username=config.get("github_username"),
            slack_user_id=config.get("slack_user_id"),
            email=config.get("email"),
            timezone=config.get("timezone"),
            workload_score=0.0,  # Will be calculated dynamically
        ))
    
    return teammates


async def load_teammates_from_github(owner: str, repo: str) -> List[Teammate]:
    """
    Load teammates from GitHub contributors.
    
    TODO: Implement GitHub API call to get contributors
    """
    # Placeholder - would fetch from GitHub API
    return []


async def load_teammates_from_jira(project_key: str) -> List[Teammate]:
    """
    Load teammates from Jira project members.
    
    TODO: Implement Jira API call to get project members
    """
    # Placeholder - would fetch from Jira API
    return []

