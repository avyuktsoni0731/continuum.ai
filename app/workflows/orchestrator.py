"""
Workflow orchestrator for executing multi-step sequential tool calls.

Handles complex workflows like:
- Reassigning Jira issue and updating due date
- Creating Jira issue with calendar check and optional PR creation
"""

import logging
from typing import List, Dict, Any
from app.workflows.models import WorkflowStep, WorkflowResult, WorkflowType

logger = logging.getLogger(__name__)


async def execute_workflow(steps: List[WorkflowStep]) -> WorkflowResult:
    """
    Execute a workflow with sequential tool calls.
    
    Steps are executed in order, with dependencies respected.
    Results from previous steps can be used in later steps.
    
    Args:
        steps: List of workflow steps to execute
    
    Returns:
        WorkflowResult with execution details
    """
    executed_steps = []
    step_results = {}  # Store results by step number
    
    try:
        for step in sorted(steps, key=lambda s: s.step_number):
            logger.info(f"Executing step {step.step_number}: {step.tool_name}")
            
            # Check dependencies
            for dep_step_num in step.depends_on:
                if dep_step_num not in step_results:
                    raise ValueError(f"Step {step.step_number} depends on step {dep_step_num} which hasn't been executed")
            
            # Resolve parameters (replace placeholders with previous step results)
            resolved_params = _resolve_params(step.params, step_results)
            
            # Execute tool
            result = await _execute_tool(step.tool_name, resolved_params)
            
            # Store result
            step_results[step.step_number] = result
            executed_steps.append({
                "step_number": step.step_number,
                "tool_name": step.tool_name,
                "params": resolved_params,
                "result": result,
                "success": result.get("success", False)
            })
            
            # If step failed, stop workflow
            if not result.get("success", False):
                logger.error(f"Step {step.step_number} failed: {result.get('error')}")
                return WorkflowResult(
                    workflow_type=WorkflowType.REASSIGN_ISSUE,  # Default, will be set by caller
                    success=False,
                    steps_executed=executed_steps,
                    error=f"Step {step.step_number} failed: {result.get('error')}"
                )
        
        # Workflow completed successfully
        final_result = step_results.get(max(step.step_number for step in steps)) if steps else None
        
        return WorkflowResult(
            workflow_type=WorkflowType.REASSIGN_ISSUE,  # Will be set by caller
            success=True,
            steps_executed=executed_steps,
            final_result=final_result
        )
        
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        return WorkflowResult(
            workflow_type=WorkflowType.REASSIGN_ISSUE,
            success=False,
            steps_executed=executed_steps,
            error=str(e)
        )


def _resolve_params(params: Dict[str, Any], step_results: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Resolve parameter placeholders with results from previous steps.
    
    Supports placeholders like:
    - "$step_1.issue_key" -> Gets issue_key from step 1 result
    - "$step_2.data.key" -> Gets nested data.key from step 2 result
    """
    resolved = {}
    
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("$step_"):
            # Extract step number and path
            parts = value[6:].split(".", 1)  # Remove "$step_" prefix
            step_num = int(parts[0])
            path = parts[1] if len(parts) > 1 else None
            
            # Get result from step
            if step_num in step_results:
                result = step_results[step_num]
                if path:
                    # Navigate nested path
                    value = _get_nested_value(result, path)
                else:
                    value = result
            else:
                raise ValueError(f"Step {step_num} result not found for placeholder {value}")
        
        resolved[key] = value
    
    return resolved


def _get_nested_value(obj: Any, path: str) -> Any:
    """Get nested value from object using dot notation."""
    parts = path.split(".")
    current = obj
    
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
        
        if current is None:
            return None
    
    return current


async def _execute_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single tool by name.
    
    Args:
        tool_name: Name of the tool to execute
        params: Tool parameters
    
    Returns:
        Tool execution result
    """
    try:
        # Route to appropriate tool - import only when needed
        if tool_name == "create_jira_issue":
            from app.tools.jira import create_issue
            result = await create_issue(**params)
            return {
                "success": True,
                "data": result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "update_jira_issue":
            from app.tools.jira import update_issue
            result = await update_issue(**params)
            return {
                "success": True,
                "data": result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "get_jira_issue":
            from app.tools.jira import get_single_issue
            result = await get_single_issue(**params)
            return {
                "success": True,
                "data": result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "find_jira_user":
            from app.tools.jira import find_user_by_name
            result = await find_user_by_name(**params)
            return {
                "success": True,
                "data": result if result else {}
            }
        
        elif tool_name == "check_calendar_availability":
            from app.tools.calendar import get_availability
            result = await get_availability(**params)
            return {
                "success": True,
                "data": result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "create_github_pr":
            from app.tools.github import create_pull_request
            result = await create_pull_request(**params)
            return {
                "success": True,
                "data": result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "update_github_pr":
            from app.tools.github import update_pull_request
            result = await update_pull_request(**params)
            return {
                "success": True,
                "data": result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "update_github_pr_assignees":
            from app.tools.github import update_pr_assignees
            result = await update_pr_assignees(**params)
            return {
                "success": True,
                "data": result if isinstance(result, dict) else result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "update_github_pr_labels":
            from app.tools.github import update_pr_labels
            result = await update_pr_labels(**params)
            return {
                "success": True,
                "data": result if isinstance(result, dict) else result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        elif tool_name == "request_github_pr_review":
            from app.tools.github import request_pr_review
            result = await request_pr_review(**params)
            return {
                "success": True,
                "data": result if isinstance(result, dict) else result.model_dump() if hasattr(result, 'model_dump') else result
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
            
    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

