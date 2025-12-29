"""
Decision engine - Routes actions based on scores and context.

This is the core intelligence layer that decides what to do.
"""

from typing import Optional
from app.policy.models import TaskContext, Action, DecisionTrace
from app.policy.scoring import (
    calculate_criticality_score,
    calculate_automation_feasibility_score
)
from app.policy.rules import check_guardrails


def decide_action(
    context: TaskContext,
    user_available: bool,
    automation_enabled: bool = False
) -> DecisionTrace:
    """
    Decide what action to take based on context and scores.
    
    Decision logic:
    - CS > 80 AND user_available → EXECUTE
    - CS > 60 AND user_unavailable → DELEGATE
    - CS > 60 AND AFS > 70 AND automation_enabled → AUTOMATE (with guardrails)
    - CS < 40 → SUMMARIZE (low priority, batch for later)
    - CS 40-60 AND user_unavailable → RESCHEDULE
    - Otherwise → NOTIFY
    
    Args:
        context: Task context
        user_available: Whether user is available
        automation_enabled: Whether user has opted into automation
    
    Returns:
        DecisionTrace with action and reasoning
    """
    # Calculate scores
    cs = calculate_criticality_score(context)
    afs = calculate_automation_feasibility_score(context)
    
    # Build factors dict for trace
    factors = {
        "criticality_score": cs,
        "automation_feasibility_score": afs,
        "user_available": user_available,
        "task_type": context.task_type,
        "priority": context.priority,
        "status": context.status,
    }
    
    # Decision logic
    action = Action.NOTIFY
    reasoning_parts = []
    selected_teammate = None
    
    # High criticality + user available → Execute directly
    if cs > 80 and user_available:
        action = Action.EXECUTE
        reasoning_parts.append(f"High criticality (CS: {cs:.1f})")
        reasoning_parts.append("User is available")
        reasoning_parts.append("Execute directly")
    
    # High criticality + user unavailable → Delegate
    elif cs > 60 and not user_available:
        action = Action.DELEGATE
        reasoning_parts.append(f"High criticality (CS: {cs:.1f})")
        reasoning_parts.append("User is unavailable")
        reasoning_parts.append("Delegate to best teammate")
        # TODO: Implement teammate selection
        selected_teammate = "teammate_to_select"
    
    # High criticality + high AFS + automation enabled → Consider automation
    elif cs > 60 and afs >= 70 and automation_enabled:
        # Check guardrails first
        guardrail_result = check_guardrails(
            Action.AUTOMATE,
            context,
            user_available,
            automation_enabled
        )
        
        if guardrail_result.allowed:
            action = Action.AUTOMATE
            reasoning_parts.append(f"High criticality (CS: {cs:.1f})")
            reasoning_parts.append(f"High automation feasibility (AFS: {afs:.1f})")
            reasoning_parts.append("Guardrails passed")
            reasoning_parts.append("Safe to automate")
        else:
            # Fallback to delegate if automation not safe
            action = Action.DELEGATE
            reasoning_parts.append(f"High criticality (CS: {cs:.1f})")
            reasoning_parts.append("Automation not safe")
            reasoning_parts.append(guardrail_result.reason)
            reasoning_parts.append("Delegate instead")
            selected_teammate = "teammate_to_select"
    
    # Low criticality → Summarize for later
    elif cs < 40:
        action = Action.SUMMARIZE
        reasoning_parts.append(f"Low criticality (CS: {cs:.1f})")
        reasoning_parts.append("Summarize and batch for later")
    
    # Medium criticality + user unavailable → Reschedule
    elif 40 <= cs <= 60 and not user_available:
        action = Action.RESCHEDULE
        reasoning_parts.append(f"Medium criticality (CS: {cs:.1f})")
        reasoning_parts.append("User is unavailable")
        reasoning_parts.append("Reschedule for when user is available")
    
    # Default: Notify
    else:
        action = Action.NOTIFY
        reasoning_parts.append(f"Criticality: {cs:.1f}")
        reasoning_parts.append("Notify user/team")
    
    reasoning = ". ".join(reasoning_parts)
    
    # Get guardrail checks if applicable
    guardrail_checks = None
    if action in [Action.AUTOMATE, Action.EXECUTE]:
        guardrail_result = check_guardrails(
            action,
            context,
            user_available,
            automation_enabled
        )
        guardrail_checks = guardrail_result.checks
    
    return DecisionTrace(
        action=action,
        criticality_score=cs,
        automation_feasibility_score=afs,
        user_available=user_available,
        reasoning=reasoning,
        factors=factors,
        selected_teammate=selected_teammate,
        guardrail_checks=guardrail_checks
    )

