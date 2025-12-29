"""
Conversational agent for continuum.ai

Uses Gemini to understand natural language, select MCP tools, and format responses.
"""

import os
import sys
import json
import re
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

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
# NOTE: Jira tools are now handled by Agno agent - removed from here
MCP_TOOLS = [
    # NOTE: GitHub tools are now handled by Agno agent - removed from here
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
1. Extract ALL parameters from the user message (dates, calendar IDs, etc.)
2. Convert parameters to correct types (strings for dates, calendar IDs)
3. If a required parameter is missing, use the most reasonable default or return an error
4. Return ONLY valid JSON, no markdown, no explanations

Response Format (MUST be valid JSON):
{{
    "tools": [
        {{"name": "tool_name", "params": {{"param1": "value1", "param2": "value2"}}}}
    ],
    "reasoning": "Brief explanation of why these tools were chosen"
}}

Examples of correct responses:

User: "show me my availability"
Response: {{"tools": [{{"name": "get_calendar_availability", "params": {{}}}}], "reasoning": "User wants to see calendar availability"}}

User: "what's on my calendar today"
Response: {{"tools": [{{"name": "get_today_events", "params": {{}}}}], "reasoning": "User wants today's calendar events"}}

User: "when am I free this week"
Response: {{"tools": [{{"name": "get_this_week_availability", "params": {{}}}}], "reasoning": "User wants this week's availability"}}
"""
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize date strings to ISO format.
        
        Handles:
        - "today" -> current date in ISO format
        - "YYYY-MM-DD" -> ISO format with time
        - Relative dates like "2nd of january, 2026" -> ISO format
        """
        if not date_str:
            return None
        
        date_str = date_str.lower().strip()
        
        # Handle "today"
        if date_str == "today":
            now = datetime.now()
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        
        # Handle "tomorrow"
        if date_str == "tomorrow":
            tomorrow = datetime.now() + timedelta(days=1)
            return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        
        # Handle ISO date format (YYYY-MM-DD)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
            except ValueError:
                pass
        
        # Handle dates like "2nd of january, 2026" or "January 2, 2026"
        date_patterns = [
            r'(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(\w+),?\s+(\d{4})',  # "2nd of january, 2026"
            r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',      # "january 2, 2026"
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',                  # "01/02/2026" or "01-02-2026"
        ]
        
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        if groups[1].lower() in month_names:
                            # Format: "2nd of january, 2026"
                            day = int(groups[0])
                            month = month_names[groups[1].lower()]
                            year = int(groups[2])
                        elif groups[0].lower() in month_names:
                            # Format: "january 2, 2026"
                            month = month_names[groups[0].lower()]
                            day = int(groups[1])
                            year = int(groups[2])
                        else:
                            # Format: "01/02/2026" (US format) or "01-02-2026"
                            month = int(groups[0])
                            day = int(groups[1])
                            year = int(groups[2])
                        
                        date_obj = datetime(year, month, day)
                        return date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
                except (ValueError, KeyError):
                    continue
        
        # If we can't parse it, return as-is (might already be in ISO format)
        # But ensure it has timezone if it's a full datetime
        if 'T' in date_str and not date_str.endswith('Z') and '+' not in date_str:
            return date_str + 'Z'
        
        return date_str
    
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
            
            # NOTE: GitHub parameter validation removed - handled by Agno agent
            # Type conversion for remaining tools (Calendar, etc.)
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

Analyze the user's request and determine which Calendar tool(s) to call.
Extract ALL parameters from the message (dates, calendar IDs, etc.).
Be precise with parameter extraction - look for dates, time ranges, etc.

NOTE: Jira and GitHub requests are handled by Agno agent. This agent only handles Calendar tools.

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
        
        # NOTE: Jira and GitHub requests are now handled by Agno agent - skip fallback parsing
        
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
        
        # NOTE: Jira and GitHub fallback parsing removed - handled by Agno agent
        
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
        # NOTE: Jira and GitHub tools are now handled by Agno agent
        from app.tools.calendar import (
            get_availability, get_today_events, get_this_week_availability
        )
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            params = tool_call.get("params", {})
            
            logger.info(f"Executing tool: {tool_name} with params: {params}")
            
            try:
                # Validate required parameters
                # NOTE: Jira and GitHub tools are now handled by Agno agent
                # Execute tool
                # NOTE: Jira and GitHub tools removed - handled by Agno
                if tool_name == "get_calendar_availability":
                    # Convert date strings to ISO format
                    start_date = params.get("start_date")
                    end_date = params.get("end_date")
                    
                    # Handle "today" and relative dates
                    if start_date:
                        start_date = self._normalize_date(start_date)
                    if end_date:
                        end_date = self._normalize_date(end_date)
                    
                    result = await get_availability(
                        calendar_id=params.get("calendar_id", "primary"),
                        start_date=start_date,
                        end_date=end_date
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
    
    async def _execute_workflow(self, workflow_type: str, workflow_params: dict) -> dict:
        """
        Execute a multi-step workflow.
        
        Args:
            workflow_type: Type of workflow ("reassign_issue", "create_issue", etc.)
            workflow_params: Parameters for the workflow
        
        Returns:
            WorkflowResult as dict
        """
        try:
            from app.workflows.orchestrator import execute_workflow
            from app.workflows.models import WorkflowStep, WorkflowType
            
            # Convert workflow_type string to enum
            workflow_enum = WorkflowType(workflow_type)
            
            # NOTE: Jira workflows are now handled by Agno agent
            # Only GitHub/Calendar workflows remain here if needed
            raise ValueError(f"Jira workflows are now handled by Agno agent. Unknown workflow type: {workflow_type}")
            
            # Execute workflow
            result = await execute_workflow(steps)
            result.workflow_type = workflow_enum
            
            return result.model_dump() if hasattr(result, 'model_dump') else result
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            from app.workflows.models import WorkflowResult, WorkflowType
            return WorkflowResult(
                workflow_type=WorkflowType.REASSIGN_ISSUE,
                success=False,
                steps_executed=[],
                error=str(e)
            ).model_dump()
    
    async def _check_user_availability(self) -> bool:
        """Check if user is currently available based on calendar."""
        try:
            from app.tools.calendar import get_today_events
            events = await get_today_events()
            now = datetime.now()
            
            # Check if user is in a meeting right now
            for event in events:
                start = event.get('start') or event.get('start_time', '')
                end = event.get('end') or event.get('end_time', '')
                if start and end:
                    try:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        if start_dt <= now <= end_dt:
                            logger.info(f"User is in meeting: {event.get('summary')}")
                            return False
                    except (ValueError, AttributeError):
                        pass
            
            return True
        except Exception as e:
            logger.warning(f"Could not check availability: {e}")
            return True  # Default to available if check fails
    
    async def _apply_policy_engine(self, tool_results: list[dict], user_message: str) -> list[dict]:
        """
        Apply policy engine to tool results for decision intelligence.
        
        Returns list of decision traces for PRs and Jira issues.
        """
        decision_traces = []
        
        try:
            from app.policy.scoring import (
                extract_task_context_from_pr,
                extract_task_context_from_jira
            )
            from app.policy.decision import decide_action
            
            # Check user availability
            user_available = await self._check_user_availability()
            
            for result in tool_results:
                if not result.get("success"):
                    continue
                
                data = result["data"]
                tool_name = result.get("tool", "")
                
                # Process PR context
                if tool_name == "get_github_pr_context" and isinstance(data, dict):
                    try:
                        context = extract_task_context_from_pr(data)
                        decision = decide_action(context, user_available, automation_enabled=False)
                        decision_traces.append({
                            "task_type": "pr",
                            "task_id": context.task_id,
                            "decision": decision.model_dump()
                        })
                        logger.info(f"Policy decision for PR {context.task_id}: {decision.action.value} (CS: {decision.criticality_score:.1f}, AFS: {decision.automation_feasibility_score:.1f})")
                    except Exception as e:
                        logger.error(f"Policy engine error for PR: {e}", exc_info=True)
                
                # Process single Jira issue
                elif tool_name == "get_jira_issue" and isinstance(data, dict):
                    try:
                        context = extract_task_context_from_jira(data)
                        decision = decide_action(context, user_available, automation_enabled=False)
                        decision_traces.append({
                            "task_type": "jira_issue",
                            "task_id": context.task_id,
                            "decision": decision.model_dump()
                        })
                        logger.info(f"Policy decision for issue {context.task_id}: {decision.action.value} (CS: {decision.criticality_score:.1f})")
                    except Exception as e:
                        logger.error(f"Policy engine error for Jira issue: {e}", exc_info=True)
                
                # Process list of Jira issues (take first one for now)
                elif tool_name in ["get_jira_board_issues", "get_jira_issues"] and isinstance(data, list) and data:
                    try:
                        # Process first issue as example
                        issue = data[0]
                        context = extract_task_context_from_jira(issue)
                        decision = decide_action(context, user_available, automation_enabled=False)
                        decision_traces.append({
                            "task_type": "jira_issue",
                            "task_id": context.task_id,
                            "decision": decision.model_dump()
                        })
                        logger.info(f"Policy decision for issue {context.task_id}: {decision.action.value} (CS: {decision.criticality_score:.1f})")
                    except Exception as e:
                        logger.error(f"Policy engine error for Jira issues: {e}", exc_info=True)
        
        except ImportError as e:
            logger.warning(f"Policy engine not available: {e}")
        except Exception as e:
            logger.error(f"Error applying policy engine: {e}", exc_info=True)
        
        return decision_traces
    
    async def _execute_delegation(self, trace: dict, tool_results: list[dict]) -> Optional[dict]:
        """
        Execute delegation when decision is DELEGATE.
        
        Returns delegation result with teammate info.
        """
        try:
            from app.delegation.selector import select_teammate
            from app.delegation.notifier import notify_teammate
            from app.delegation.models import DelegationNotification
            from app.policy.scoring import (
                extract_task_context_from_pr,
                extract_task_context_from_jira
            )
            
            decision = trace.get("decision", {})
            task_type = trace.get("task_type")
            task_id = trace.get("task_id")
            
            # Find task context from tool results
            task_context = None
            task_data = None
            
            for result in tool_results:
                if not result.get("success"):
                    continue
                
                data = result["data"]
                
                if task_type == "pr" and isinstance(data, dict):
                    task_context = extract_task_context_from_pr(data)
                    task_data = data
                    break
                elif task_type == "jira_issue" and isinstance(data, dict):
                    task_context = extract_task_context_from_jira(data)
                    task_data = data
                    break
                elif task_type == "jira_issue" and isinstance(data, list) and data:
                    # Find the specific issue
                    for issue in data:
                        if issue.get("key") == task_id:
                            task_context = extract_task_context_from_jira(issue)
                            task_data = issue
                            break
            
            if not task_context:
                logger.warning(f"Could not find task context for {task_id}")
                return None
            
            # Select best teammate
            teammate_score = await select_teammate(task_context)
            
            if not teammate_score:
                logger.warning("No suitable teammate found for delegation")
                return {
                    "success": False,
                    "reason": "No suitable teammate available"
                }
            
            teammate = teammate_score.teammate
            
            # Determine action requested based on task type
            if task_type == "pr":
                action_requested = "review and approve"
                urgency = "high" if decision.get("criticality_score", 0) > 70 else "medium"
            elif task_type == "jira_issue":
                action_requested = "review and update"
                urgency = "high" if decision.get("criticality_score", 0) > 70 else "medium"
            else:
                action_requested = "review"
                urgency = "medium"
            
            # Build context for notification
            context = {
                "criticality_score": decision.get("criticality_score", 0),
                "reasoning": decision.get("reasoning", ""),
            }
            
            # Add URL if available
            if task_type == "pr" and task_data:
                pr_detail = task_data.get("pr", {})
                context["url"] = pr_detail.get("html_url", "")
            elif task_type == "jira_issue":
                # TODO: Build Jira URL
                context["url"] = f"https://continuum-ai.atlassian.net/browse/{task_id}"
            
            # Create notification
            notification = DelegationNotification(
                teammate=teammate,
                task_type=task_type,
                task_id=task_id,
                task_title=task_context.title,
                action_requested=action_requested,
                context=context,
                urgency=urgency
            )
            
            # Send notification
            success = await notify_teammate(notification)
            
            return {
                "success": success,
                "teammate": teammate.username,
                "task_id": task_id,
                "reasoning": teammate_score.reasoning
            }
            
        except Exception as e:
            logger.error(f"Delegation execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def format_response(
        self, 
        user_message: str, 
        tool_results: list[dict], 
        intent: dict, 
        decision_traces: Optional[list[dict]] = None,
        delegation_results: Optional[list[dict]] = None
    ) -> str:
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
        
        # Add decision traces to prompt if available
        decision_info = ""
        if decision_traces:
            decision_info = "\n\nDecision Intelligence:\n"
            for trace in decision_traces:
                decision = trace.get("decision", {})
                decision_info += f"- {trace.get('task_type')} {trace.get('task_id')}: "
                decision_info += f"Action: {decision.get('action')}, "
                decision_info += f"CS: {decision.get('criticality_score', 0):.1f}, "
                decision_info += f"AFS: {decision.get('automation_feasibility_score', 0):.1f}, "
                decision_info += f"Reasoning: {decision.get('reasoning', 'N/A')}\n"
        
        # Add delegation results if available
        delegation_info = ""
        if delegation_results:
            delegation_info = "\n\nDelegation Actions:\n"
            for result in delegation_results:
                if result.get("success"):
                    delegation_info += f"- Delegated to {result.get('teammate')}: {result.get('reasoning', 'N/A')}\n"
                else:
                    delegation_info += f"- Delegation failed: {result.get('reason', result.get('error', 'Unknown'))}\n"
        
        prompt = f"""User asked: "{user_message}"

I called these tools: {intent.get('reasoning', 'N/A')}

Tool Results:
{chr(10).join(results_detail)}{decision_info}{delegation_info}

Format this data for Slack messaging. Use Slack-friendly formatting:
- Use *bold* for emphasis (not **double asterisks**)
- Use `code` for technical terms, IDs, or keys
- Use _italic_ sparingly
- Use emojis where appropriate (📅 for calendar, ✅ for success, ❌ for errors, 📋 for lists)
- Group related items together
- Use clear section headers
- Keep formatting clean and readable

CRITICAL RULES:
1. If there are multiple items in a list, you MUST show details for ALL items, not just the first one
2. For calendar events: Group by date, show time clearly, use 📅 emoji
3. For Jira issues: Show key, summary, status, priority clearly
4. For PRs: Show number, title, status, CI status clearly
5. Use blank lines to separate sections for better readability
6. Keep each line concise - Slack messages should be scannable
7. If Decision Intelligence is provided, include it at the end with a "💡 Decision" section showing:
   - Recommended action (Execute/Delegate/Summarize/Reschedule/Automate)
   - Criticality Score (CS) and Automation Feasibility Score (AFS)
   - Reasoning: why this action was chosen
   - Format: "💡 *Decision for [task]*: [action] | CS: [score] | AFS: [score] | *Why*: [reasoning]"
8. If Delegation Actions are provided, mention:
   - "✅ Delegated to [teammate]: [reasoning]"
   - Or "❌ Delegation failed: [reason]"

Format example for calendar events:
📅 *Events for [Date]*
• *Event Name* - Time: 09:45 AM - 10:45 AM
• *Event Name* - Time: 01:45 PM - 02:45 PM

Format example for Jira issues:
📋 *Jira Issues*
• `PROJ-123` *Issue Title* - Status: In Progress - Priority: High

Format example for PRs:
🔀 *Pull Requests*
• PR #42 *PR Title* - Status: Open - CI: ✅ Passing

Now format the data accordingly:"""
        
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
            return self._fallback_formatting(tool_results, decision_traces, delegation_results)
    
    def _fallback_formatting(
        self, 
        tool_results: list[dict], 
        decision_traces: Optional[list[dict]] = None,
        delegation_results: Optional[list[dict]] = None
    ) -> str:
        """Simple fallback formatting optimized for Slack."""
        lines = []
        for result in tool_results:
            if result["success"]:
                data = result["data"]
                tool_name = result.get('tool', '')
                
                if isinstance(data, list):
                    if len(data) == 0:
                        lines.append("No results found.")
                    else:
                        # Determine emoji based on tool type
                        emoji = "📋"
                        if "calendar" in tool_name or "event" in tool_name:
                            emoji = "📅"
                        elif "jira" in tool_name:
                            emoji = "📋"
                        elif "github" in tool_name or "pr" in tool_name:
                            emoji = "🔀"
                        
                        lines.append(f"{emoji} *Found {len(data)} items:*\n")
                        
                        # Group calendar events by date
                        if "calendar" in tool_name or "event" in tool_name:
                            events_by_date = defaultdict(list)
                            for item in data:
                                if isinstance(item, dict):
                                    start = item.get('start') or item.get('start_time', '')
                                    # Extract date from start time
                                    date_key = start.split('T')[0] if start and 'T' in start else 'Unknown'
                                    events_by_date[date_key].append(item)
                            
                            for date, events in sorted(events_by_date.items()):
                                lines.append(f"*{date}*")
                                for item in events:
                                    summary = item.get('summary') or item.get('title', 'Untitled')
                                    start = item.get('start') or item.get('start_time', '')
                                    end = item.get('end') or item.get('end_time', '')
                                    if start and end:
                                        # Format time nicely
                                        start_time = start.split('T')[1][:5] if 'T' in start else start
                                        end_time = end.split('T')[1][:5] if 'T' in end else end
                                        lines.append(f"• *{summary}* - {start_time} - {end_time}")
                                    else:
                                        lines.append(f"• *{summary}*")
                                lines.append("")  # Blank line between dates
                        else:
                            # For other types, simple list
                            for item in data:
                                if isinstance(item, dict):
                                    summary = item.get('summary') or item.get('title') or item.get('name', 'Untitled')
                                    key = item.get('key') or item.get('number') or ''
                                    if key:
                                        lines.append(f"• `{key}` *{summary}*")
                                    else:
                                        lines.append(f"• *{summary}*")
                elif isinstance(data, dict):
                    summary = data.get('summary') or data.get('name') or str(data)[:100]
                    lines.append(f"*Result:* {summary}")
            else:
                lines.append(f"❌ *Error:* {result['error']}")
        
        # Add decision traces if available
        if decision_traces:
            lines.append("\n💡 *Decision Intelligence:*")
            for trace in decision_traces:
                decision = trace.get("decision", {})
                task_id = trace.get("task_id", "unknown")
                action = decision.get("action", "unknown")
                cs = decision.get("criticality_score", 0)
                afs = decision.get("automation_feasibility_score", 0)
                reasoning = decision.get("reasoning", "N/A")
                
                lines.append(f"• *{task_id}*: {action.upper()}")
                lines.append(f"  CS: {cs:.1f} | AFS: {afs:.1f}")
                lines.append(f"  *Why*: {reasoning}")
        
        # Add delegation results if available
        if delegation_results:
            lines.append("\n👥 *Delegation Actions:*")
            for result in delegation_results:
                if result.get("success"):
                    teammate = result.get("teammate", "unknown")
                    reasoning = result.get("reasoning", "N/A")
                    lines.append(f"✅ Delegated to *{teammate}*: {reasoning}")
                else:
                    reason = result.get("reason") or result.get("error", "Unknown error")
                    lines.append(f"❌ Delegation failed: {reason}")
        
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
        
        # Check if this is a workflow (multi-step action)
        workflow_type = intent.get("workflow")
        tool_results = []
        
        if workflow_type:
            # Execute workflow
            logger.info(f"Detected workflow: {workflow_type}")
            workflow_result = await self._execute_workflow(workflow_type, intent.get("workflow_params", {}))
            # Convert workflow result to tool_results format for compatibility
            tool_results = [{
                "tool": f"workflow_{workflow_type}",
                "success": workflow_result.get("success", False),
                "data": workflow_result.get("final_result") if workflow_result.get("success") else None,
                "error": workflow_result.get("error"),
                "workflow_steps": workflow_result.get("steps_executed", [])
            }]
        elif intent.get("tools"):
            # Execute regular tools
            tool_results = await self.execute_tools(intent["tools"])
        else:
            logger.warning("No tools or workflow selected by intent parser")
        
        # Apply policy engine for decision intelligence (if applicable)
        decision_traces = []
        if tool_results:
            decision_traces = await self._apply_policy_engine(tool_results, user_message)
        
        # Execute delegation if decision is DELEGATE
        delegation_results = []
        for trace in decision_traces:
            decision = trace.get("decision", {})
            if decision.get("action") == "delegate":
                delegation_result = await self._execute_delegation(trace, tool_results)
                if delegation_result:
                    delegation_results.append(delegation_result)
        
        # Format response (include decision traces and delegation results)
        response = await self.format_response(
            user_message, 
            tool_results, 
            intent, 
            decision_traces,
            delegation_results
        )
        
        # Add to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        logger.info(f"=== Response generated ({len(response)} chars) ===")
        return response
