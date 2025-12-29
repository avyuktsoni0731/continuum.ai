"""
Guardrails and safety rules for automation.

Ensures actions are safe before execution.
"""

from typing import Optional, Dict
from pydantic import BaseModel
from app.policy.models import TaskContext, Action


class GuardrailResult(BaseModel):
    """Result of guardrail checks."""
    allowed: bool
    reason: str
    checks: Dict[str, bool]  # Individual check results


def check_guardrails(
    action: Action,
    context: TaskContext,
    user_available: bool,
    automation_enabled: bool = False
) -> GuardrailResult:
    """
    Check if an action is safe to execute.
    
    Args:
        action: The action to check
        context: Task context
        user_available: Whether user is available
        automation_enabled: Whether user has opted into automation
    
    Returns:
        GuardrailResult with allowed status and reason
    """
    checks = {}
    reasons = []
    
    # Check 1: Automation opt-in
    if action == Action.AUTOMATE:
        checks["automation_opt_in"] = automation_enabled
        if not automation_enabled:
            reasons.append("User has not opted into automation")
    
    # Check 2: Critical actions require high scores
    if action == Action.AUTOMATE:
        # Only automate if AFS is high enough
        from app.policy.scoring import calculate_automation_feasibility_score
        afs = calculate_automation_feasibility_score(context)
        checks["high_afs"] = afs >= 70
        if afs < 70:
            reasons.append(f"Automation feasibility too low (AFS: {afs:.1f} < 70)")
    
    # Check 3: Production safety
    if action == Action.AUTOMATE:
        # Check if this touches production
        is_production = any(
            label in ["production", "prod", "live", "main", "master"]
            for label in context.labels
        )
        checks["production_safe"] = not is_production or context.approvals >= 2
        if is_production and context.approvals < 2:
            reasons.append("Production changes require 2+ approvals")
    
    # Check 4: CI must pass for automation
    if action == Action.AUTOMATE:
        checks["ci_passed"] = context.ci_passed is True
        if context.ci_passed is not True:
            reasons.append("CI must pass before automation")
    
    # Check 5: No blockers
    if action in [Action.AUTOMATE, Action.EXECUTE]:
        checks["no_blockers"] = not context.has_blockers
        if context.has_blockers:
            reasons.append("Task has blockers")
    
    # Check 6: Business hours (for automation)
    if action == Action.AUTOMATE:
        from datetime import datetime
        now = datetime.now()
        hour = now.hour
        # Business hours: 9 AM - 6 PM (adjust as needed)
        checks["business_hours"] = 9 <= hour < 18
        if not (9 <= hour < 18):
            reasons.append("Automation only allowed during business hours")
    
    # Determine if allowed
    allowed = all(checks.values())
    reason = "; ".join(reasons) if reasons else "All checks passed"
    
    return GuardrailResult(
        allowed=allowed,
        reason=reason,
        checks=checks
    )


def get_safe_automation_conditions() -> Dict[str, any]:
    """Get conditions that must be met for safe automation."""
    return {
        "afs_threshold": 70,
        "min_approvals": 2,
        "ci_required": True,
        "no_blockers": True,
        "business_hours_only": True,
        "opt_in_required": True,
    }

