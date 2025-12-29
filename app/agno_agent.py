"""
Agno-based agent for continuum.ai

This agent uses Agno framework for more scalable and adaptable task execution.
Currently handles Jira operations with reasoning capabilities.
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
    AGNO_AVAILABLE = True
except ImportError as e:
    AGNO_ERROR = f"Import error: {str(e)}"
    logger.error(f"Agno import failed: {e}", exc_info=True)
except Exception as e:
    AGNO_ERROR = f"Unexpected error: {str(e)}"
    logger.error(f"Agno initialization error: {e}", exc_info=True)


class AgnoAgent:
    """Agno-based agent for handling Jira operations with reasoning."""
    
    def __init__(self):
        """Initialize Agno agent with Jira tools."""
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
        
        # Create agent with Jira tools (as functions)
        self.agent = Agent(
            model=model,
            tools=[
                get_jira_issues_tool,
                get_jira_issue_tool,
                get_jira_projects_tool,
                get_jira_boards_tool,
                get_jira_board_issues_tool,
                find_jira_user_tool,
                create_jira_issue_tool,
                update_jira_issue_tool
            ],
            markdown=True
        )
        
        logger.info("Agno agent initialized successfully with Jira tools")
    
    async def run(self, message: str) -> str:
        """
        Process a user message and return response.
        
        Args:
            message: User's natural language message
            
        Returns:
            Formatted response string
        """
        try:
            # Agno's run method is synchronous, but we're in async context
            import asyncio
            
            # Run Agno agent in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.agent.run(message)
            )
            
            # Extract response text
            if hasattr(response, 'content'):
                return response.content
            elif isinstance(response, str):
                return response
            else:
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
