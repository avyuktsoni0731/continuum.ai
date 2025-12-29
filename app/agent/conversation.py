"""
Conversational agent for continuum.ai

Uses Gemini to understand natural language, select MCP tools, and format responses.
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from google import genai
except ImportError:
    genai = None

# Set up logging
logger = logging.getLogger(__name__)


# Tool schemas for the LLM to understand available tools
MCP_TOOLS = [
    {
        "name": "get_jira_boards",
        "description": "List all Jira boards",
        "parameters": {},
        "examples": [
            "show me jira boards",
            "list all boards",
            "what boards are available"
        ]
    },
    {
        "name": "get_jira_board_issues",
        "description": "Get all issues from a specific Jira board. REQUIRES board_id (integer). Extract board ID from phrases like 'board 1', 'board ID 5', etc.",
        "parameters": {"board_id": "integer (required)"},
        "examples": [
            "show me issues in board 1",
            "what tasks are in board ID 5",
            "get all issues from board 2"
        ]
    },
    {
        "name": "get_jira_issues",
        "description": "Search Jira issues using JQL query. Use for custom searches like 'my tasks', 'high priority issues', etc.",
        "parameters": {"jql": "string (JQL query)"},
        "examples": [
            "show me my tasks",
            "find high priority issues",
            "get issues assigned to me"
        ]
    },
    {
        "name": "get_jira_issue",
        "description": "Get details of a specific Jira issue by key (e.g., PROJ-123, ABC-456). Extract issue key from text.",
        "parameters": {"issue_key": "string (required, format: PROJ-123)"},
        "examples": [
            "show me PROJ-123",
            "get details of issue ABC-456",
            "what's the status of PROJ-789"
        ]
    },
    {
        "name": "get_github_pulls",
        "description": "List pull requests. Use state='open' (default), 'closed', or 'all'",
        "parameters": {"state": "string (optional: 'open', 'closed', 'all')"},
        "examples": [
            "show me open PRs",
            "list all pull requests",
            "get closed PRs"
        ]
    },
    {
        "name": "get_github_pull",
        "description": "Get details of a specific PR by number. Extract PR number from phrases like 'PR #42', 'pull request 10', etc.",
        "parameters": {"pr_number": "integer (required)"},
        "examples": [
            "show me PR #42",
            "get details of pull request 10",
            "what's the status of PR 5"
        ]
    },
    {
        "name": "get_github_pr_context",
        "description": "Get comprehensive PR context including CI status, reviews, and approvals. Extract PR number from text.",
        "parameters": {"pr_number": "integer (required)"},
        "examples": [
            "check PR #42",
            "get full context for PR 10",
            "show me reviews and CI status for PR 5"
        ]
    },
    {
        "name": "get_calendar_availability",
        "description": "Get calendar availability and free time slots for scheduling",
        "parameters": {
            "calendar_id": "string (optional, default: 'primary')",
            "start_date": "string ISO format (optional)",
            "end_date": "string ISO format (optional)"
        },
        "examples": [
            "show me my availability",
            "when am I free",
            "check my calendar availability"
        ]
    },
    {
        "name": "get_today_events",
        "description": "Get all events scheduled for today",
        "parameters": {"calendar_id": "string (optional)"},
        "examples": [
            "what's on my calendar today",
            "show me today's events",
            "what meetings do I have today"
        ]
    },
    {
        "name": "get_this_week_availability",
        "description": "Get availability for the current week with free slots",
        "parameters": {"calendar_id": "string (optional)"},
        "examples": [
            "show me my week availability",
            "when am I free this week",
            "check my schedule for this week"
        ]
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
        
        # Check for credentials
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            logger.info(f"Using GCP credentials from: {creds_path}")
            if not os.path.exists(creds_path):
                logger.warning(f"Credentials file not found: {creds_path}")
        else:
            logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set. Will try default credentials.")
            logger.warning("For EC2, set GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json")
        
        try:
            self.client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location
            )
            self.model = "gemini-3-pro-preview"
            self.conversation_history = []
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def _get_tools_prompt(self) -> str:
        """Generate prompt describing available tools with examples."""
        tools_desc = []
        for tool in MCP_TOOLS:
            desc = f"- **{tool['name']}**: {tool['description']}"
            if tool.get('examples'):
                desc += f"\n  Examples: {', '.join(tool['examples'])}"
            tools_desc.append(desc)
        
        return f"""You are a tool selection assistant. Your job is to analyze user requests and determine which tools to call.

Available Tools:
{chr(10).join(tools_desc)}

CRITICAL INSTRUCTIONS:
1. Extract ALL parameters from the user message (board IDs, PR numbers, issue keys, etc.)
2. Convert parameters to correct types (integers for IDs, strings for keys)
3. If a required parameter is missing, use the most reasonable default or return an error
4. Return ONLY valid JSON, no markdown, no explanations

Response Format (MUST be valid JSON):
{{
    "tools": [
        {{"name": "tool_name", "params": {{"param1": "value1", "param2": 123}}}}
    ],
    "reasoning": "Brief explanation of why these tools were chosen"
}}

Examples of correct responses:

User: "show me open PRs"
Response: {{"tools": [{{"name": "get_github_pulls", "params": {{"state": "open"}}}}], "reasoning": "User wants to see open pull requests"}}

User: "get issues from board 5"
Response: {{"tools": [{{"name": "get_jira_board_issues", "params": {{"board_id": 5}}}}], "reasoning": "User wants issues from board ID 5"}}

User: "show me PR #42"
Response: {{"tools": [{{"name": "get_github_pr_context", "params": {{"pr_number": 42}}}}], "reasoning": "User wants details of PR number 42"}}

User: "what's the status of PROJ-123"
Response: {{"tools": [{{"name": "get_jira_issue", "params": {{"issue_key": "PROJ-123"}}}}], "reasoning": "User wants details of Jira issue PROJ-123"}}
"""
    
    def _validate_and_convert_params(self, tool_name: str, params: dict) -> dict:
        """Validate and convert parameters to correct types."""
        validated = {}
        
        # Find tool schema
        tool_schema = next((t for t in MCP_TOOLS if t["name"] == tool_name), None)
        if not tool_schema:
            return params  # Unknown tool, return as-is
        
        for param_name, param_value in params.items():
            if param_value is None:
                continue
            
            # Type conversion based on tool requirements
            if tool_name == "get_jira_board_issues" and param_name == "board_id":
                try:
                    validated["board_id"] = int(param_value)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid board_id: {param_value}, trying to extract number")
                    # Try to extract number from string
                    match = re.search(r'(\d+)', str(param_value))
                    if match:
                        validated["board_id"] = int(match.group(1))
                    else:
                        raise ValueError(f"Could not extract board_id from: {param_value}")
            
            elif tool_name in ["get_github_pull", "get_github_pr_context"] and param_name == "pr_number":
                try:
                    validated["pr_number"] = int(param_value)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid pr_number: {param_value}, trying to extract number")
                    # Try to extract number from string (handles "PR #42", "42", etc.)
                    match = re.search(r'(\d+)', str(param_value))
                    if match:
                        validated["pr_number"] = int(match.group(1))
                    else:
                        raise ValueError(f"Could not extract pr_number from: {param_value}")
            
            elif tool_name == "get_jira_issue" and param_name == "issue_key":
                # Extract issue key (format: PROJ-123)
                issue_key = str(param_value).strip().upper()
                # Validate format
                if re.match(r'^[A-Z]+-\d+$', issue_key):
                    validated["issue_key"] = issue_key
                else:
                    # Try to extract from text
                    match = re.search(r'([A-Z]+-\d+)', issue_key, re.IGNORECASE)
                    if match:
                        validated["issue_key"] = match.group(1).upper()
                    else:
                        raise ValueError(f"Invalid issue key format: {param_value}")
            
            else:
                # Keep as-is for other parameters
                validated[param_name] = param_value
        
        return validated
    
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
Extract ALL parameters from the message (board IDs, PR numbers, issue keys, etc.).
Be precise with parameter extraction - look for numbers, issue keys (PROJ-123 format), etc.

Return ONLY valid JSON, no markdown code blocks, no explanations outside JSON."""
        
        try:
            logger.info(f"Parsing intent for: {user_message}")
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            raw_response = response.text.strip()
            logger.debug(f"Raw Gemini response: {raw_response[:500]}")
            
            # Extract JSON from response (handle markdown code blocks)
            json_text = raw_response
            
            # Remove markdown code blocks if present
            if "```json" in json_text:
                json_text = re.sub(r'```json\s*', '', json_text)
                json_text = re.sub(r'```\s*$', '', json_text)
            elif "```" in json_text:
                json_text = re.sub(r'```\s*', '', json_text)
                json_text = re.sub(r'```\s*$', '', json_text)
            
            # Extract JSON object
            json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            
            result = json.loads(json_text)
            logger.info(f"Parsed intent: {json.dumps(result, indent=2)}")
            
            # Validate and convert parameters
            if result.get("tools"):
                for tool_call in result["tools"]:
                    tool_name = tool_call.get("name")
                    params = tool_call.get("params", {})
                    try:
                        validated_params = self._validate_and_convert_params(tool_name, params)
                        tool_call["params"] = validated_params
                        logger.info(f"Validated params for {tool_name}: {validated_params}")
                    except Exception as e:
                        logger.error(f"Parameter validation failed for {tool_name}: {e}")
                        raise
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response text: {raw_response[:500]}")
            # Retry with a clearer prompt
            return await self._retry_parse_intent(user_message, raw_response)
        except Exception as e:
            logger.error(f"Intent parsing error: {e}", exc_info=True)
            # Fallback: try to infer tool from keywords
            return self._fallback_intent_parsing(user_message)
    
    async def _retry_parse_intent(self, user_message: str, failed_response: str) -> dict:
        """Retry intent parsing with a clearer prompt."""
        logger.info("Retrying intent parsing with clearer prompt")
        
        prompt = f"""The previous attempt to parse this user message failed. 
Previous (failed) response: {failed_response[:200]}

User message: "{user_message}"

Return ONLY a valid JSON object with this exact structure:
{{
    "tools": [{{"name": "tool_name", "params": {{"param": "value"}}}}],
    "reasoning": "why"
}}

Do not include any markdown, code blocks, or text outside the JSON object."""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            text = response.text.strip()
            # Clean up
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)
            
            result = json.loads(text)
            logger.info(f"Retry successful: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            logger.error(f"Retry also failed: {e}")
            return self._fallback_intent_parsing(user_message)
    
    def _fallback_intent_parsing(self, message: str) -> dict:
        """Simple keyword-based intent parsing fallback."""
        logger.warning(f"Using fallback intent parsing for: {message}")
        message_lower = message.lower().strip()
        
        # Handle "get jira boards" or "show jira boards" or just "jira boards"
        if "jira" in message_lower and "board" in message_lower:
            # Check if asking for specific board issues
            if "issue" in message_lower or "task" in message_lower:
                # Try to extract board ID
                board_match = re.search(r'board\s*(?:id\s*)?(\d+)', message_lower)
                if board_match:
                    board_id = int(board_match.group(1))
                    return {
                        "tools": [{"name": "get_jira_board_issues", "params": {"board_id": board_id}}],
                        "reasoning": f"User wants issues from board {board_id} (fallback parsing)"
                    }
            # Check if asking for a specific board by number
            board_match = re.search(r'board\s*(?:id\s*)?(\d+)', message_lower)
            if board_match:
                board_id = int(board_match.group(1))
                return {
                    "tools": [{"name": "get_jira_board_issues", "params": {"board_id": board_id}}],
                    "reasoning": f"User wants issues from board {board_id} (fallback parsing)"
                }
            # Default: list all boards
            return {
                "tools": [{"name": "get_jira_boards", "params": {}}],
                "reasoning": "User wants to see Jira boards (fallback parsing)"
            }
            if "issue" in message_lower or "task" in message_lower:
                # Try to extract board ID
                board_match = re.search(r'board\s*(?:id\s*)?(\d+)', message_lower)
                if board_match:
                    board_id = int(board_match.group(1))
                    return {
                        "tools": [{"name": "get_jira_board_issues", "params": {"board_id": board_id}}],
                        "reasoning": f"User wants issues from board {board_id} (fallback parsing)"
                    }
                return {
                    "tools": [{"name": "get_jira_boards", "params": {}}],
                    "reasoning": "User wants to see Jira boards (fallback parsing)"
                }
        
        if "pr" in message_lower or "pull request" in message_lower:
            pr_match = re.search(r'#?(\d+)', message)
            if pr_match:
                pr_number = int(pr_match.group(1))
                return {
                    "tools": [{"name": "get_github_pr_context", "params": {"pr_number": pr_number}}],
                    "reasoning": f"User wants PR {pr_number} details (fallback parsing)"
                }
            return {
                "tools": [{"name": "get_github_pulls", "params": {"state": "open"}}],
                "reasoning": "User wants to see open PRs (fallback parsing)"
            }
        
        if "calendar" in message_lower or "availability" in message_lower or "free" in message_lower:
            if "today" in message_lower:
                return {
                    "tools": [{"name": "get_today_events", "params": {}}],
                    "reasoning": "User wants today's calendar events (fallback parsing)"
                }
            return {
                "tools": [{"name": "get_this_week_availability", "params": {}}],
                "reasoning": "User wants calendar availability (fallback parsing)"
            }
        
        # Try to match Jira issue key
        issue_match = re.search(r'([A-Z]+-\d+)', message, re.IGNORECASE)
        if issue_match:
            issue_key = issue_match.group(1).upper()
            return {
                "tools": [{"name": "get_jira_issue", "params": {"issue_key": issue_key}}],
                "reasoning": f"User wants Jira issue {issue_key} (fallback parsing)"
            }
        
        return {
            "tools": [],
            "reasoning": "Could not determine intent (fallback parsing)"
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
            
            logger.info(f"Executing tool: {tool_name} with params: {params}")
            
            try:
                # Validate required parameters
                if tool_name == "get_jira_board_issues" and not params.get("board_id"):
                    raise ValueError("board_id is required for get_jira_board_issues")
                if tool_name == "get_jira_issue" and not params.get("issue_key"):
                    raise ValueError("issue_key is required for get_jira_issue")
                if tool_name in ["get_github_pull", "get_github_pr_context"] and not params.get("pr_number"):
                    raise ValueError("pr_number is required for this tool")
                
                # Execute tool
                if tool_name == "get_jira_boards":
                    result = await get_boards()
                elif tool_name == "get_jira_board_issues":
                    result = await get_board_issues(params.get("board_id"))
                elif tool_name == "get_jira_issues":
                    jql = params.get("jql", "ORDER BY created DESC")
                    result = await get_jira_issues(jql)
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
                
                logger.info(f"Tool {tool_name} succeeded: {len(result) if isinstance(result, list) else 'dict'} items")
                
                results.append({
                    "tool": tool_name,
                    "success": True,
                    "data": result
                })
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
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
        # Build detailed context for formatting
        results_detail = []
        for result in tool_results:
            if result["success"]:
                data = result["data"]
                if isinstance(data, list):
                    if len(data) == 0:
                        results_detail.append(f"{result['tool']}: No items found")
                    else:
                        # Include ALL items, but limit total size to avoid token limits
                        # For small lists (< 20 items), include all
                        # For larger lists, include first 20 and mention total count
                        items_to_include = data[:20] if len(data) > 20 else data
                        items_json = json.dumps(items_to_include, default=str, indent=2)
                        
                        if len(data) > 20:
                            results_detail.append(
                                f"{result['tool']}: Found {len(data)} items (showing first 20):\n{items_json}"
                            )
                        else:
                            results_detail.append(
                                f"{result['tool']}: Found {len(data)} items:\n{items_json}"
                            )
                elif isinstance(data, dict):
                    results_detail.append(f"{result['tool']}: {json.dumps(data, default=str, indent=2)}")
                else:
                    results_detail.append(f"{result['tool']}: {str(data)[:200]}")
            else:
                results_detail.append(f"{result['tool']}: ERROR - {result['error']}")
        
        prompt = f"""User asked: "{user_message}"

I called these tools: {intent.get('reasoning', 'N/A')}

Tool Results:
{chr(10).join(results_detail)}

Format this data into a clear, helpful response for the user. 
CRITICAL: If there are multiple items in a list, you MUST show details for ALL items, not just the first one.
- If there are results, present them in a readable, organized format
- For lists with multiple items, show ALL items with their details (summary, time, etc.)
- If there are errors, explain them clearly and suggest what might be wrong
- If no results were found, explain why (e.g., "No open PRs found" or "Board ID not found")
- Be concise but informative
- Use bullet points or lists when showing multiple items
- Include all relevant details for each item (time, summary, status, etc.)"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            formatted = response.text.strip()
            logger.info(f"Formatted response length: {len(formatted)}")
            return formatted
        except Exception as e:
            logger.error(f"Response formatting failed: {e}", exc_info=True)
            # Fallback formatting
            return self._fallback_formatting(tool_results)
    
    def _fallback_formatting(self, tool_results: list[dict]) -> str:
        """Simple fallback formatting."""
        lines = []
        for result in tool_results:
            if result["success"]:
                data = result["data"]
                if isinstance(data, list):
                    if len(data) == 0:
                        lines.append("No results found.")
                    else:
                        lines.append(f"Found {len(data)} items:")
                        # Show ALL items, not just first 10
                        for item in data:
                            if isinstance(item, dict):
                                summary = item.get('summary') or item.get('title') or item.get('name', 'Untitled')
                                # Include time if available (for calendar events)
                                start = item.get('start') or item.get('start_time', '')
                                end = item.get('end') or item.get('end_time', '')
                                if start:
                                    lines.append(f"  • {summary}")
                                    if start and end:
                                        lines.append(f"    Time: {start} - {end}")
                                else:
                                    lines.append(f"  • {summary}")
                elif isinstance(data, dict):
                    summary = data.get('summary') or data.get('name') or str(data)[:100]
                    lines.append(f"Result: {summary}")
            else:
                lines.append(f"❌ Error: {result['error']}")
        
        return "\n".join(lines) if lines else "No results found."
    
    async def chat(self, user_message: str) -> str:
        """
        Main chat method: parse intent → execute tools → format response.
        
        Args:
            user_message: User's natural language message
        
        Returns:
            Formatted response
        """
        logger.info(f"=== New chat request: {user_message} ===")
        
        # Add to history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Parse intent
        intent = await self.parse_intent(user_message)
        logger.info(f"Intent parsed: {intent.get('reasoning')}")
        
        # Execute tools
        tool_results = []
        if intent.get("tools"):
            tool_results = await self.execute_tools(intent["tools"])
        else:
            logger.warning("No tools selected by intent parser")
        
        # Format response
        response = await self.format_response(user_message, tool_results, intent)
        
        # Add to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        logger.info(f"=== Response generated ({len(response)} chars) ===")
        return response
