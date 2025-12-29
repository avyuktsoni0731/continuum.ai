"""
Teammate selection algorithm.

Selects the best teammate(s) for delegation based on:
- Code ownership (file paths in PR)
- Current workload (open PRs, assigned issues)
- Timezone/availability
- Recent activity
"""

import logging
from typing import Optional, List
from app.delegation.models import Teammate, TeammateScore
from app.policy.models import TaskContext

logger = logging.getLogger(__name__)


async def get_teammate_list() -> List[Teammate]:
    """
    Get list of potential teammates.
    
    Fetches from:
    - Config file (for now)
    - TODO: GitHub contributors
    - TODO: Jira project members
    - TODO: Slack team members
    """
    from app.delegation.config import load_teammates_from_config
    
    # Load from config (can be extended to fetch from APIs)
    teammates = await load_teammates_from_config()
    
    # TODO: Calculate actual workload for each teammate
    # For now, set default workload
    for teammate in teammates:
        if teammate.workload_score == 0.0:
            # TODO: Fetch actual workload from GitHub/Jira
            teammate.workload_score = 30.0  # Default moderate workload
    
    return teammates


async def calculate_ownership_score(
    teammate: Teammate,
    task_context: TaskContext
) -> float:
    """
    Calculate ownership score (0-100) based on code ownership.
    
    For PRs: Check if teammate has contributed to files in PR
    For Jira: Check if teammate owns the component/project
    """
    score = 0.0
    
    if task_context.task_type == "pr":
        # Check if teammate has contributed to files in PR
        # TODO: Fetch PR files and check git blame/history
        pr_files = task_context.metadata.get("pr_data", {}).get("pr", {}).get("changed_files", 0)
        
        # Placeholder: If teammate's GitHub username matches PR author, higher score
        pr_author = task_context.metadata.get("pr_data", {}).get("pr", {}).get("user", {}).get("login", "")
        if teammate.github_username and pr_author.lower() == teammate.github_username.lower():
            score += 50
        
        # TODO: Check file ownership from git history
        # For now, give base score
        score += 20
    
    elif task_context.task_type == "jira_issue":
        # Check component ownership
        components = task_context.metadata.get("issue_data", {}).get("components", [])
        # TODO: Map components to owners
        # For now, give base score
        score += 20
    
    return min(score, 100.0)


async def calculate_workload_score(teammate: Teammate) -> float:
    """
    Calculate workload score (0-100).
    
    Higher score = more busy = less available.
    We want teammates with LOWER workload scores.
    """
    # TODO: Fetch actual workload:
    # - Open PRs assigned to them
    # - Open Jira issues assigned
    # - Recent activity
    
    # For now, use the pre-set workload_score
    # Invert it: high workload = low availability
    return teammate.workload_score


async def calculate_availability_score(teammate: Teammate) -> float:
    """
    Calculate availability score (0-100).
    
    Based on:
    - Current timezone (are they awake?)
    - Calendar availability
    - Recent activity (are they active?)
    """
    score = 50.0  # Base score
    
    # TODO: Check calendar availability
    # TODO: Check timezone (are they in work hours?)
    # TODO: Check recent GitHub/Jira activity
    
    return min(score, 100.0)


async def select_teammate(
    task_context: TaskContext,
    max_candidates: int = 2
) -> Optional[TeammateScore]:
    """
    Select the best teammate(s) for delegation.
    
    Args:
        task_context: Context about the task to delegate
        max_candidates: Maximum number of teammates to return
    
    Returns:
        TeammateScore with best teammate, or None if no suitable candidates
    """
    logger.info(f"Selecting teammate for {task_context.task_type} {task_context.task_id}")
    
    # Get potential teammates
    teammates = await get_teammate_list()
    
    if not teammates:
        logger.warning("No teammates available for delegation")
        return None
    
    # Score each teammate
    scored_teammates = []
    
    for teammate in teammates:
        # Calculate individual scores
        ownership = await calculate_ownership_score(teammate, task_context)
        workload = await calculate_workload_score(teammate)
        availability = await calculate_availability_score(teammate)
        
        # Combined score (weighted)
        # Higher ownership = better
        # Lower workload = better (so invert)
        # Higher availability = better
        total_score = (
            ownership * 0.4 +      # 40% weight on ownership
            (100 - workload) * 0.3 +  # 30% weight on low workload
            availability * 0.3      # 30% weight on availability
        )
        
        # Build reasoning
        factors = {
            "ownership": ownership,
            "workload": workload,
            "availability": availability
        }
        
        reasoning_parts = []
        if ownership > 50:
            reasoning_parts.append(f"High ownership match ({ownership:.1f})")
        if workload < 50:
            reasoning_parts.append(f"Low workload ({workload:.1f})")
        if availability > 50:
            reasoning_parts.append(f"Available ({availability:.1f})")
        
        reasoning = ". ".join(reasoning_parts) if reasoning_parts else "General availability"
        
        scored_teammates.append(TeammateScore(
            teammate=teammate,
            total_score=total_score,
            reasoning=reasoning,
            factors=factors
        ))
    
    # Sort by total score (highest first)
    scored_teammates.sort(key=lambda x: x.total_score, reverse=True)
    
    # Return best candidate
    if scored_teammates:
        best = scored_teammates[0]
        logger.info(f"Selected teammate: {best.teammate.username} (score: {best.total_score:.1f})")
        return best
    
    return None


async def select_multiple_teammates(
    task_context: TaskContext,
    max_candidates: int = 2
) -> List[TeammateScore]:
    """
    Select multiple teammates for delegation (e.g., for code review).
    
    Returns top N candidates.
    """
    teammates = await get_teammate_list()
    
    if not teammates:
        return []
    
    scored_teammates = []
    
    for teammate in teammates:
        ownership = await calculate_ownership_score(teammate, task_context)
        workload = await calculate_workload_score(teammate)
        availability = await calculate_availability_score(teammate)
        
        total_score = (
            ownership * 0.4 +
            (100 - workload) * 0.3 +
            availability * 0.3
        )
        
        factors = {
            "ownership": ownership,
            "workload": workload,
            "availability": availability
        }
        
        reasoning = f"Ownership: {ownership:.1f}, Workload: {workload:.1f}, Availability: {availability:.1f}"
        
        scored_teammates.append(TeammateScore(
            teammate=teammate,
            total_score=total_score,
            reasoning=reasoning,
            factors=factors
        ))
    
    # Sort and return top N
    scored_teammates.sort(key=lambda x: x.total_score, reverse=True)
    return scored_teammates[:max_candidates]

