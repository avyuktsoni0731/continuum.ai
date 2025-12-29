"""
Example integration showing how to use the context service in your tools.

This demonstrates:
1. Caching external API responses
2. Storing conversation history
3. Tracking tasks for monitoring
4. Retrieving context for better decision-making
"""

import asyncio
from app.db.database import get_session, init_db
from app.db.context_service import ContextService


async def example_caching_jira_issue():
    """Example: Cache a Jira issue to avoid repeated API calls."""
    db = next(get_session())
    ctx = ContextService(db)
    
    # Simulate fetching a Jira issue
    issue_data = {
        "key": "PROJ-123",
        "summary": "Fix login bug",
        "status": "In Progress",
        "assignee": "user@example.com"
    }
    
    # Cache it with 1 hour TTL
    ctx.cache_context(
        cache_key=f"jira_issue:PROJ-123",
        cache_type="jira_issue",
        data=issue_data,
        ttl_hours=1
    )
    
    # Later, retrieve from cache
    cached = ctx.get_cached_context("jira_issue:PROJ-123")
    if cached:
        print(f"Found cached issue: {cached['summary']}")
    else:
        print("Cache miss - fetch from API")
    
    db.close()


async def example_conversation_history():
    """Example: Store and retrieve conversation history."""
    db = next(get_session())
    ctx = ContextService(db)
    
    session_id = "session_123"
    user_id = "user@example.com"
    
    # Store user message
    ctx.add_conversation(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content="What PRs need my review?",
        metadata={"source": "chat"}
    )
    
    # Store assistant response
    ctx.add_conversation(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content="Here are 3 PRs waiting for your review...",
        metadata={"prs": [42, 43, 44]}
    )
    
    # Retrieve recent history
    history = ctx.get_conversation_history(session_id, limit=10)
    for msg in history:
        print(f"{msg.role}: {msg.content[:50]}...")
    
    db.close()


async def example_task_tracking():
    """Example: Track tasks for monitoring."""
    db = next(get_session())
    ctx = ContextService(db)
    
    # Track a PR that needs monitoring
    ctx.track_task(
        task_type="github_pr",
        task_id="42",
        title="Add authentication feature",
        status="active",
        metadata={
            "repository": "myorg/myrepo",
            "author": "developer@example.com",
            "priority": "high"
        }
    )
    
    # Track a Jira issue
    ctx.track_task(
        task_type="jira_issue",
        task_id="PROJ-123",
        title="Fix login bug",
        status="active"
    )
    
    # Get all active tracked tasks
    tasks = ctx.get_tracked_tasks(status="active")
    for task in tasks:
        print(f"{task.task_type}: {task.task_id} - {task.title}")
    
    # Update task status
    ctx.update_task_status("github_pr", "42", "completed")
    
    db.close()


async def example_user_preferences():
    """Example: Store and retrieve user preferences."""
    db = next(get_session())
    ctx = ContextService(db)
    
    user_id = "user@example.com"
    
    # Set user preferences
    ctx.set_user_preferences(
        user_id=user_id,
        preferences={
            "work_hours_start": 9,
            "work_hours_end": 17,
            "timezone": "UTC",
            "notification_preferences": {
                "email": True,
                "slack": False
            }
        }
    )
    
    # Update a single preference
    ctx.update_user_preference(user_id, "work_hours_start", 8)
    
    # Retrieve preferences
    prefs = ctx.get_user_preferences(user_id)
    print(f"Work hours: {prefs.get('work_hours_start')} - {prefs.get('work_hours_end')}")
    
    db.close()


async def example_context_snapshots():
    """Example: Save and retrieve context snapshots."""
    db = next(get_session())
    ctx = ContextService(db)
    
    # Save a snapshot of current work context
    snapshot_data = {
        "jira_issues": ["PROJ-123", "PROJ-124"],
        "github_prs": [42, 43],
        "calendar_events": ["Meeting with team"],
        "timestamp": "2025-01-15T10:00:00Z"
    }
    
    ctx.save_snapshot(
        snapshot_key="morning_status_2025-01-15",
        context_data=snapshot_data,
        description="Morning work status snapshot",
        tags=["daily", "status", "morning"]
    )
    
    # Retrieve snapshot
    snapshot = ctx.get_snapshot("morning_status_2025-01-15")
    if snapshot:
        print(f"Snapshot contains {len(snapshot.get('jira_issues', []))} Jira issues")
    
    # Search by tags
    snapshots = ctx.search_snapshots(tags=["daily"], limit=10)
    print(f"Found {len(snapshots)} daily snapshots")
    
    db.close()


async def example_combined_context():
    """Example: Combined context for decision-making."""
    db = next(get_session())
    ctx = ContextService(db)
    
    session_id = "session_123"
    user_id = "user@example.com"
    
    # Get recent conversation history
    history = ctx.get_recent_context(session_id, days=1)
    
    # Get tracked tasks
    tasks = ctx.get_tracked_tasks(status="active")
    
    # Get user preferences
    prefs = ctx.get_user_preferences(user_id)
    
    # Combine into context for AI decision-making
    context = {
        "conversation_history": [
            {"role": msg.role, "content": msg.content, "timestamp": msg.created_at.isoformat()}
            for msg in history[-5:]  # Last 5 messages
        ],
        "tracked_tasks": [
            {
                "type": task.task_type,
                "id": task.task_id,
                "title": task.title,
                "status": task.status
            }
            for task in tasks
        ],
        "user_preferences": prefs
    }
    
    print(f"Context ready for AI with {len(context['conversation_history'])} messages")
    
    db.close()


# Integration pattern for your tools
async def enhanced_get_jira_issue(issue_key: str, use_cache: bool = True):
    """
    Example: Enhanced Jira issue fetcher with caching.
    
    This pattern can be applied to any tool that fetches external data.
    """
    from app.tools.jira import get_single_issue
    
    db = next(get_session())
    ctx = ContextService(db)
    
    cache_key = f"jira_issue:{issue_key}"
    
    # Try cache first
    if use_cache:
        cached = ctx.get_cached_context(cache_key, cache_type="jira_issue")
        if cached:
            db.close()
            return cached
    
    # Cache miss - fetch from API
    issue = await get_single_issue(issue_key)
    issue_dict = issue.model_dump()
    
    # Cache the result
    ctx.cache_context(
        cache_key=cache_key,
        cache_type="jira_issue",
        data=issue_dict,
        ttl_hours=1  # Cache for 1 hour
    )
    
    # Link to current conversation if you have a session
    # conversation = ctx.add_conversation(...)
    # ctx.link_conversation_to_context(conversation.id, cached_context.id)
    
    db.close()
    return issue_dict


if __name__ == "__main__":
    # Initialize database first
    init_db()
    
    # Run examples
    print("Running examples...")
    asyncio.run(example_caching_jira_issue())
    asyncio.run(example_conversation_history())
    asyncio.run(example_task_tracking())
    asyncio.run(example_user_preferences())
    asyncio.run(example_context_snapshots())
    asyncio.run(example_combined_context())
    print("Examples complete!")

