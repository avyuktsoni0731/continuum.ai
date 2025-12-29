"""
Conversational agent for continuum.ai

Uses Gemini to understand natural language, select MCP tools, and format responses.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from google import genai
except ImportError:
    genai = None


# Tool schemas for the LLM to understand available tools
MCP_TOOLS = [
    {
        "name": "get_jira_boards",
        "description": "List all Jira boards",
        "parameters": {}
    },
    {
        "name": "get_jira_board_issues",
        "description": "Get all issues from a specific Jira board. Requires board_id (integer).",
        "parameters": {"board_id": "integer"}
    },
    {
        "name": "get_jira_issues",
        "description": "Search Jira issues using JQL query. Example: 'assignee=currentUser() AND status!=Done'",
        "parameters": {"jql": "string"}
    },
    {
        "name": "get_jira_issue",
        "description": "Get details of a specific Jira issue by key (e.g., PROJ-123)",
        "parameters": {"issue_key": "string"}
    },
    {
        "name": "get_github_pulls",
        "description": "List pull requests. Use state='open', 'closed', or 'all'",
        "parameters": {"state": "string (optional)"}
    },
    {
        "name": "get_github_pull",
        "description": "Get details of a specific PR by number",
        "parameters": {"pr_number": "integer"}
    },
    {
        "name": "get_github_pr_context",
        "description": "Get comprehensive PR context including CI status, reviews, and approvals",
        "parameters": {"pr_number": "integer"}
    },
    {
        "name": "get_calendar_availability",
        "description": "Get calendar availability and free time slots for scheduling",
        "parameters": {
            "calendar_id": "string (optional, default: 'primary' or user email)",
            "start_date": "string ISO format (optional)",
            "end_date": "string ISO format (optional)"
        }
    },
    {
        "name": "get_today_events",
        "description": "Get all events scheduled for today",
        "parameters": {"calendar_id": "string (optional)"}
    },
    {
        "name": "get_this_week_availability",
        "description": "Get availability for the current week with free slots",
        "parameters": {"calendar_id": "string (optional)"}
    }
]


class ConversationalAgent:
    """Conversational agent that uses Gemini to understand intent and call MCP tools."""
    
    def __init__(self):
        """Initialize the agent with Gemini client."""
        if not genai:
            raise ImportError("google-genai not installed. Run: pip install google-genai")
        
        project_id = os.getenv("GCP_PROJECT_ID", "continuum-ai-482615")
        location = os.getenv("GCP_LOCATION", "global")
        
        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location
        )
        self.model = "gemini-3-pro-preview"
        self.conversation_history = []
    
    def _get_tools_prompt(self) -> str:
        """Generate prompt describing available tools."""
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in MCP_TOOLS
        ])
        return f"""Available MCP Tools:
{tools_desc}

When the user asks for something, determine which tool(s) to call and extract the parameters.
Return your response as JSON with this format:
{{
    "tools": [
        {{"name": "tool_name", "params": {{"param": "value"}}}}
    ],
    "reasoning": "Why you chose these tools"
}}
"""
    
    async def parse_intent(self, user_message: str) -> dict:
        """
        Parse user intent and determine which tools to call.
        
        Returns:
            {
                "tools": [{"name": "...", "params": {...}}],
                "reasoning": "..."
            }
        """
        tools_prompt = self._get_tools_prompt()
        
        prompt = f"""{tools_prompt}

User message: "{user_message}"

Analyze the user's request and determine which MCP tool(s) to call.
Extract any parameters from the message (like board IDs, PR numbers, dates, etc.).

Return ONLY valid JSON, no other text."""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            # Parse JSON from response
            import json
            import re
            
            text = response.text.strip()
            # Extract JSON if wrapped in markdown
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)
            
            result = json.loads(text)
            return result
            
        except Exception as e:
            # Fallback: try to infer tool from keywords
            return self._fallback_intent_parsing(user_message)
    
    def _fallback_intent_parsing(self, message: str) -> dict:
        """Simple keyword-based intent parsing fallback."""
        message_lower = message.lower()
        
        if "jira" in message_lower and "board" in message_lower:
            if "issue" in message_lower or "task" in message_lower:
                # Try to extract board ID
                import re
                board_match = re.search(r'board\s*(\d+)', message_lower)
                if board_match:
                    return {
                        "tools": [{"name": "get_jira_board_issues", "params": {"board_id": int(board_match.group(1))}}],
                        "reasoning": "User wants issues from a specific board"
                    }
                return {
                    "tools": [{"name": "get_jira_boards", "params": {}}],
                    "reasoning": "User wants to see Jira boards"
                }
        
        if "pr" in message_lower or "pull request" in message_lower:
            import re
            pr_match = re.search(r'#?(\d+)', message)
            if pr_match:
                return {
                    "tools": [{"name": "get_github_pr_context", "params": {"pr_number": int(pr_match.group(1))}}],
                    "reasoning": "User wants PR details"
                }
            return {
                "tools": [{"name": "get_github_pulls", "params": {"state": "open"}}],
                "reasoning": "User wants to see open PRs"
            }
        
        if "calendar" in message_lower or "availability" in message_lower or "free" in message_lower:
            return {
                "tools": [{"name": "get_this_week_availability", "params": {}}],
                "reasoning": "User wants calendar availability"
            }
        
        return {
            "tools": [],
            "reasoning": "Could not determine intent"
        }
    
    async def execute_tools(self, tool_calls: list[dict]) -> list[dict]:
        """
        Execute MCP tools and return results.
        
        Args:
            tool_calls: List of {"name": "...", "params": {...}}
        
        Returns:
            List of tool execution results
        """
        results = []
        
        # Import underlying tool functions directly
        from app.tools.jira import (
            get_boards, get_board_issues, get_jira_issues, get_single_issue
        )
        from app.tools.github import (
            get_pull_requests, get_pull_request, get_pr_context
        )
        from app.tools.calendar import (
            get_availability, get_today_events, get_this_week_availability
        )
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            params = tool_call.get("params", {})
            
            try:
                if tool_name == "get_jira_boards":
                    result = await get_boards()
                elif tool_name == "get_jira_board_issues":
                    result = await get_board_issues(params.get("board_id"))
                elif tool_name == "get_jira_issues":
                    result = await get_jira_issues(params.get("jql", "ORDER BY created DESC"))
                elif tool_name == "get_jira_issue":
                    result = await get_single_issue(params.get("issue_key"))
                elif tool_name == "get_github_pulls":
                    result = await get_pull_requests(state=params.get("state", "open"))
                elif tool_name == "get_github_pull":
                    result = await get_pull_request(params.get("pr_number"))
                elif tool_name == "get_github_pr_context":
                    result = await get_pr_context(params.get("pr_number"))
                elif tool_name == "get_calendar_availability":
                    result = await get_availability(
                        calendar_id=params.get("calendar_id", "primary"),
                        start_date=params.get("start_date"),
                        end_date=params.get("end_date")
                    )
                elif tool_name == "get_today_events":
                    result = await get_today_events(calendar_id=params.get("calendar_id", "primary"))
                elif tool_name == "get_this_week_availability":
                    result = await get_this_week_availability(calendar_id=params.get("calendar_id", "primary"))
                else:
                    results.append({
                        "tool": tool_name,
                        "success": False,
                        "error": f"Unknown tool: {tool_name}"
                    })
                    continue
                    
                # Convert Pydantic models to dicts if needed
                if hasattr(result, 'model_dump'):
                    result = result.model_dump()
                elif isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
                    result = [item.model_dump() if hasattr(item, 'model_dump') else item for item in result]
                
                results.append({
                    "tool": tool_name,
                    "success": True,
                    "data": result
                })
            except Exception as e:
                results.append({
                    "tool": tool_name,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def format_response(self, user_message: str, tool_results: list[dict], intent: dict) -> str:
        """
        Format tool results into a human-friendly response using Gemini.
        
        Args:
            user_message: Original user message
            tool_results: Results from tool executions
            intent: Intent parsing result
        
        Returns:
            Formatted response string
        """
        # Build context for formatting
        results_summary = []
        for result in tool_results:
            if result["success"]:
                data = result["data"]
                if isinstance(data, list):
                    results_summary.append(f"{result['tool']}: {len(data)} items")
                elif isinstance(data, dict):
                    results_summary.append(f"{result['tool']}: {list(data.keys())}")
                else:
                    results_summary.append(f"{result['tool']}: {str(data)[:100]}")
            else:
                results_summary.append(f"{result['tool']}: ERROR - {result['error']}")
        
        prompt = f"""User asked: "{user_message}"

I called these tools: {intent.get('reasoning', 'N/A')}

Tool results:
{chr(10).join(results_summary)}

Format this data into a clear, helpful response for the user. Be concise but informative.
If there are errors, mention them politely.
If there's data, present it in a readable format."""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return response.text
        except Exception as e:
            # Fallback formatting
            return self._fallback_formatting(tool_results)
    
    def _fallback_formatting(self, tool_results: list[dict]) -> str:
        """Simple fallback formatting."""
        lines = []
        for result in tool_results:
            if result["success"]:
                data = result["data"]
                if isinstance(data, list):
                    lines.append(f"Found {len(data)} items:")
                    for item in data[:5]:  # Show first 5
                        if isinstance(item, dict):
                            lines.append(f"  - {item.get('summary', item.get('title', str(item)))}")
                elif isinstance(data, dict):
                    lines.append(f"Result: {data.get('summary', data.get('name', str(data)))}")
            else:
                lines.append(f"Error: {result['error']}")
        
        return "\n".join(lines) if lines else "No results found."
    
    async def chat(self, user_message: str) -> str:
        """
        Main chat method: parse intent → execute tools → format response.
        
        Args:
            user_message: User's natural language message
        
        Returns:
            Formatted response
        """
        # Add to history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Parse intent
        intent = await self.parse_intent(user_message)
        
        # Execute tools
        tool_results = []
        if intent.get("tools"):
            tool_results = await self.execute_tools(intent["tools"])
        
        # Format response
        response = await self.format_response(user_message, tool_results, intent)
        
        # Add to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response

