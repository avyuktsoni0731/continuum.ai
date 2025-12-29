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

    logger.info("Attempting to import agno.db.mongo.mongo...")
    # Import the correct MongoDb class (implements BaseDb)
    from agno.db.mongo.mongo import MongoDb
    logger.info("Successfully imported agno.db.mongo.mongo")
    
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
    
    logger.info("Attempting to import Calendar tools...")
    from app.agno_tools.calendar_tools import (
        list_calendars_tool,
        get_calendar_events_tool,
        get_calendar_availability_tool,
        get_today_events_tool,
        get_this_week_availability_tool,
        create_calendar_event_tool
    )
    logger.info("Successfully imported all Calendar tools")
    AGNO_AVAILABLE = True
except ImportError as e:
    AGNO_ERROR = f"Import error: {str(e)}"
    logger.error(f"Agno import failed: {e}", exc_info=True)
except Exception as e:
    AGNO_ERROR = f"Unexpected error: {str(e)}"
    logger.error(f"Agno initialization error: {e}", exc_info=True)


class AgnoAgent:
    """Agno-based agent for handling Jira, GitHub, and Calendar operations with reasoning."""
    
    def __init__(self):
        """Initialize Agno agent with Jira, GitHub, and Calendar tools."""
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
        
        # Initialize MongoDB Storage
        mongo_url = os.getenv("MONGODB_URL")
        db = None
        if mongo_url:
            try:
                # Initialize MongoDb for both sessions and memories
                db = MongoDb(
                    db_url=mongo_url,
                    db_name="continuum", 
                    session_collection="sessions",
                    memory_collection="agent_memory"
                )
                logger.info("MongoDB storage initialized")
            except Exception as e:
                logger.error(f"Failed to initialize MongoDB storage: {e}")
        else:
            logger.warning("MONGODB_URL not set, memory persistence disabled")

        # Create agent with Jira, GitHub, and Calendar tools (as functions)
        self.agent = Agent(
            model=model,
            db=db,  # Use 'db' parameter for BaseDb implementation
            add_history_to_context=True,
            # Enabling memory as requested
            enable_user_memories=True, 
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
                request_github_pr_review_tool,
                # Calendar tools
                list_calendars_tool,
                get_calendar_events_tool,
                get_calendar_availability_tool,
                get_today_events_tool,
                get_this_week_availability_tool,
                create_calendar_event_tool
            ],
            markdown=True,
            instructions="""You are continuum.ai, a context-aware AI productivity agent for Jira, GitHub, and Calendar task management.

CRITICAL: Use Slack formatting, NOT Markdown:
- Use *single asterisk* for bold (NOT **double asterisks**)
- Use _underscore_ for italic
- Use `backticks` for code/IDs
- Use emojis for status indicators
- NEVER use ** for bold - Slack doesn't support it

MULTI-TOOL ORCHESTRATION:
You can execute multiple tools in sequence to complete complex workflows. For example:
- "Check avyukt's availability, assign PR #2 to him, create a Jira issue with him assigned, and add it to his calendar"
- Break down the request into steps: 1) Check availability, 2) Assign PR, 3) Create Jira issue, 4) Create calendar event
- Use results from previous tools to inform next steps (e.g., use free time slots to schedule calendar events)
- Link related items (e.g., include PR URL in Jira issue description, mention Jira issue in calendar event)

IMPORTANT FOR GITHUB OPERATIONS:
- When owner/repo are not specified in the user's request, use the default repository from GITHUB_OWNER and GITHUB_REPO environment variables
- Do NOT guess or infer repository names from context unless explicitly mentioned
- If a PR operation fails, clearly state which repository you tried (e.g., "PR #2 not found in owner/repo")
- For assign operations, you can use update_github_pr_assignees_tool with just the PR number if the default repo is configured

IMPORTANT FOR CALENDAR OPERATIONS:
- When checking availability for a specific person, use their email as calendar_id (for service accounts) or "primary" (for OAuth)
- When creating events, use ISO format dates (e.g., '2026-01-01T10:00:00Z')
- For multi-step workflows involving calendar, check availability first, then create events in free slots
- Include relevant context in event descriptions (e.g., PR numbers, Jira issue keys)

When responding to users in Slack:
- Structure responses clearly with headers and sections
- For lists of items, use bullet points with clear labels
- For tables, use pipe-delimited format with headers
- Always confirm actions taken (e.g., "✅ Successfully assigned KAN-2 to Shashank")
- Include relevant details (issue keys, assignees, due dates, PR numbers, repos) in a clear, scannable format
- Group related information together
- Be concise but informative

Examples of CORRECT Slack formatting:
- "✅ *Task Updated*\n• Issue: `KAN-2`\n• Assigned to: *Shashank Chauhan*\n• Due: January 4th, 2026 at 3:30 PM"
- "📋 *Jira Boards*\n| ID | Name | Type | Project |\n|:---|:---|:---|:---|\n| 1 | KAN board | simple | KAN |"
- "🔍 *Search Results*\nFound 3 issues:\n• `KAN-2`: Fix login bug (Status: In Progress)\n• `KAN-3`: Update docs (Status: To Do)"
- "🔀 *Pull Requests*\n• PR #42: *Fix authentication bug* - Status: Open - CI: ✅ Passing - Reviews: 2 approvals"
- "✅ *PR Updated*\n• PR #42\n• Title: *New Title*\n• Description updated\n• Labels: `bug`, `urgent`"
- "✅ *Assignee Added*\n• PR #2\n• Assigned to: *avyuktsoni0731*"

REMEMBER: Use *single asterisk* for bold, never **double asterisks**. Always format responses for Slack readability."""
        )
        
        logger.info("Agno agent initialized successfully with Jira, GitHub, and Calendar tools")
    
    async def run(self, message: str, user_id: str = None) -> str:
        """
        Process a user message and return response.
        
        Args:
            message: User's natural language message
            user_id: Slack user ID for context retention
            
        Returns:
            Formatted response string
        """
        try:
            # Use async version of agent.run() since our tools are async
            # Pass user_id to session_id (if provided) to give each user their own persistent memory
            session_id = user_id if user_id else "default_session"
            
            logger.info(f"Running Agno agent for user: {user_id} (session: {session_id})")
            
            response = await self.agent.arun(message, session_id=session_id)
            
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


def is_calendar_request(message: str) -> bool:
    """
    Determine if a message is a Calendar-related request.
    
    Args:
        message: User message
        
    Returns:
        True if message appears to be Calendar-related
    """
    message_lower = message.lower()
    
    # Calendar keywords
    calendar_keywords = [
        "calendar", "availability", "free", "schedule", "meeting",
        "event", "appointment", "busy", "slot", "time slot"
    ]
    
    # Check for keywords
    if any(keyword in message_lower for keyword in calendar_keywords):
        return True
    
    return False


def is_memory_request(message: str) -> bool:
    """
    Determine if a message is a memory/context-related request.
    
    Args:
        message: User message
        
    Returns:
        True if message appears to be memory-related
    """
    message_lower = message.lower()
    
    # Memory/Context keywords
    memory_keywords = [
        "remember", "forget", "recall", "memorize",
        "i am", "my name is", "my role", "my skill",
        "who am i", "what do you know", "context",
        "save this", "note that", "update my"
    ]
    
    # Check for keywords
    if any(keyword in message_lower for keyword in memory_keywords):
        return True
    
    return False


def should_use_agno(message: str) -> bool:
    """
    Determine if a message should be handled by Agno agent.
    
    Agno handles: Jira, GitHub, Calendar, and multi-tool orchestration.
    
    Args:
        message: User message
        
    Returns:
        True if message should be routed to Agno
    """
    return (
        is_jira_request(message) or 
        is_github_request(message) or 
        is_calendar_request(message) or 
        is_memory_request(message)
    )
