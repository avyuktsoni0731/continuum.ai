"""
Agno-based agent for continuum.ai

This agent uses Agno framework for more scalable and adaptable task execution.
Handles Jira and GitHub operations with reasoning capabilities.
"""

import os
import logging
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

AGNO_AVAILABLE = False
AGNO_ERROR = None

# Try importing Agno components step by step to identify the issue
try:
    logger.info("Attempting to import agno.agent...")
    from agno.agent import Agent
    logger.info("Successfully imported agno.agent")
    
    logger.info("Attempting to import agno.models.google...")
    from agno.models.google import Gemini
    logger.info("Successfully imported agno.models.google")
    
    logger.info("Attempting to import Jira tools...")
    from app.agno_tools.jira_tools import (
        get_jira_issues_tool,
        get_jira_issue_tool,
        get_jira_projects_tool,
        get_jira_boards_tool,
        get_jira_board_issues_tool,
        find_jira_user_tool,
        create_jira_issue_tool,
        update_jira_issue_tool
    )
    logger.info("Successfully imported all Jira tools")
    
    logger.info("Attempting to import GitHub tools...")
    from app.agno_tools.github_tools import (
        get_github_pulls_tool,
        get_github_pull_tool,
        get_github_pr_context_tool,
        get_github_pr_checks_tool,
        get_github_pr_reviews_tool,
        get_github_commits_tool,
        get_github_repo_tool,
        create_github_pr_tool,
        update_github_pr_tool,
        update_github_pr_assignees_tool,
        update_github_pr_labels_tool,
        request_github_pr_review_tool
    )
    logger.info("Successfully imported all GitHub tools")
    AGNO_AVAILABLE = True
except ImportError as e:
    AGNO_ERROR = f"Import error: {str(e)}"
    logger.error(f"Agno import failed: {e}", exc_info=True)
except Exception as e:
    AGNO_ERROR = f"Unexpected error: {str(e)}"
    logger.error(f"Agno initialization error: {e}", exc_info=True)


class AgnoAgent:
    """Agno-based agent for handling Jira and GitHub operations with reasoning."""
    
    def __init__(self):
        """Initialize Agno agent with Jira and GitHub tools."""
        if not AGNO_AVAILABLE:
            error_msg = "Agno framework not available."
            if AGNO_ERROR:
                error_msg += f" Error: {AGNO_ERROR}"
            error_msg += " Run: pip install agno (in your virtual environment)"
            raise ImportError(error_msg)
        
        project_id = os.getenv("GCP_PROJECT_ID", "continuum-ai-482615")
        location = os.getenv("GCP_LOCATION", "global")
        
        # Initialize Gemini model for Agno (via VertexAI)
        model = Gemini(
            id="gemini-3-pro-preview",
            vertexai=True,
            project_id=project_id,
            location=location
        )
        
        # Create agent with Jira and GitHub tools (as functions)
        self.agent = Agent(
            model=model,
            tools=[
                # Jira tools
                get_jira_issues_tool,
                get_jira_issue_tool,
                get_jira_projects_tool,
                get_jira_boards_tool,
                get_jira_board_issues_tool,
                find_jira_user_tool,
                create_jira_issue_tool,
                update_jira_issue_tool,
                # GitHub tools
                get_github_pulls_tool,
                get_github_pull_tool,
                get_github_pr_context_tool,
                get_github_pr_checks_tool,
                get_github_pr_reviews_tool,
                get_github_commits_tool,
                get_github_repo_tool,
                create_github_pr_tool,
                update_github_pr_tool,
                update_github_pr_assignees_tool,
                update_github_pr_labels_tool,
                request_github_pr_review_tool
            ],
            markdown=True,
            instructions="""You are continuum.ai, a context-aware AI productivity agent for Jira and GitHub task management.

CRITICAL: Use Slack formatting, NOT Markdown:
- Use *single asterisk* for bold (NOT **double asterisks**)
- Use _underscore_ for italic
- Use `backticks` for code/IDs
- Use emojis for status indicators
- NEVER use ** for bold - Slack doesn't support it

When responding to users in Slack:
- Structure responses clearly with headers and sections
- For lists of items, use bullet points with clear labels
- For tables, use pipe-delimited format with headers
- Always confirm actions taken (e.g., "✅ Successfully assigned KAN-2 to Shashank")
- Include relevant details (issue keys, assignees, due dates) in a clear, scannable format
- Group related information together
- Be concise but informative

Examples of CORRECT Slack formatting:
- "✅ *Task Updated*\n• Issue: `KAN-2`\n• Assigned to: *Shashank Chauhan*\n• Due: January 4th, 2026 at 3:30 PM"
- "📋 *Jira Boards*\n| ID | Name | Type | Project |\n|:---|:---|:---|:---|\n| 1 | KAN board | simple | KAN |"
- "🔍 *Search Results*\nFound 3 issues:\n• `KAN-2`: Fix login bug (Status: In Progress)\n• `KAN-3`: Update docs (Status: To Do)"
- "🔀 *Pull Requests*\n• PR #42: *Fix authentication bug* - Status: Open - CI: ✅ Passing - Reviews: 2 approvals"
- "✅ *PR Updated*\n• PR #42\n• Title: *New Title*\n• Description updated\n• Labels: `bug`, `urgent`"

REMEMBER: Use *single asterisk* for bold, never **double asterisks**. Always format responses for Slack readability."""
        )
        
        logger.info("Agno agent initialized successfully with Jira and GitHub tools")
    
    async def run(self, message: str) -> str:
        """
        Process a user message and return response.
        
        Args:
            message: User's natural language message
            
        Returns:
            Formatted response string
        """
        try:
            # Use async version of agent.run() since our tools are async
            response = await self.agent.arun(message)
            
            # Extract response text - Agno returns RunOutput object
            if hasattr(response, 'content'):
                # RunOutput.content is the main response
                return response.content
            elif hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'response'):
                # Some Agno versions use response attribute
                if hasattr(response.response, 'text'):
                    return response.response.text
                return str(response.response)
            elif isinstance(response, str):
                return response
            else:
                # Fallback: convert to string
                return str(response)
                
        except Exception as e:
            logger.error(f"Agno agent error: {e}", exc_info=True)
            raise


def is_jira_request(message: str) -> bool:
    """
    Determine if a message is a Jira-related request.
    
    Args:
        message: User message
        
    Returns:
        True if message appears to be Jira-related
    """
    message_lower = message.lower()
    
    # Jira keywords
    jira_keywords = [
        "jira", "issue", "task", "board", "project",
        "assign", "reassign", "create issue", "update issue",
        "kan-", "proj-", "bug-", "story-", "epic-"
    ]
    
    # Check for Jira issue key pattern (e.g., KAN-2, PROJ-123)
    import re
    if re.search(r'[A-Z]+-\d+', message, re.IGNORECASE):
        return True
    
    # Check for keywords
    if any(keyword in message_lower for keyword in jira_keywords):
        return True
    
    return False


def is_github_request(message: str) -> bool:
    """
    Determine if a message is a GitHub-related request.
    
    Args:
        message: User message
        
    Returns:
        True if message appears to be GitHub-related
    """
    message_lower = message.lower()
    
    # GitHub keywords
    github_keywords = [
        "github", "pr", "pull request", "pull-request", "pullrequest",
        "merge", "review", "approve", "ci", "checks", "status",
        "assign", "label", "commit", "branch", "repo", "repository"
    ]
    
    # Check for PR number pattern (e.g., "PR #42", "pull request 10", "#5")
    import re
    if re.search(r'(?:pr|pull\s*request|#)\s*#?\d+', message_lower):
        return True
    
    # Check for keywords
    if any(keyword in message_lower for keyword in github_keywords):
        return True
    
    return False
