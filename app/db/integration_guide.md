# Integration Guide: Adding Context Awareness to Your Server

This guide shows how to integrate the database context system into your MCP server tools.

## Quick Start

1. **Initialize the database** (one-time setup):
   ```bash
   python -m app.db.init_db
   ```

2. **Import and use context service** in your tools:
   ```python
   from app.db.database import get_session
   from app.db.context_service import ContextService
   ```

## Integration Patterns

### Pattern 1: Add Caching to Existing Tools

Enhance your existing tools to use caching:

```python
# In app/server.py or your tool files
from app.db.database import get_session
from app.db.context_service import ContextService

@mcp.tool
async def get_jira_issue(issue_key: str) -> dict:
    """Fetch a Jira issue with caching."""
    db = next(get_session())
    ctx = ContextService(db)
    
    try:
        # Try cache first
        cache_key = f"jira_issue:{issue_key}"
        cached = ctx.get_cached_context(cache_key, cache_type="jira_issue")
        if cached:
            db.close()
            return cached
        
        # Cache miss - fetch from API
        from app.tools.jira import get_single_issue
        issue = await get_single_issue(issue_key)
        issue_dict = issue.model_dump()
        
        # Cache for 1 hour
        ctx.cache_context(
            cache_key=cache_key,
            cache_type="jira_issue",
            data=issue_dict,
            ttl_hours=1
        )
        
        return issue_dict
    finally:
        db.close()
```

### Pattern 2: Store Conversation Context

When the AI makes decisions, store context for future reference:

```python
@mcp.tool
async def get_github_pr_context(pr_number: int) -> dict:
    """Get PR context and store it for future reference."""
    from app.tools.github import get_pr_context
    
    # Get PR context (existing logic)
    context = await get_pr_context(pr_number)
    
    # Optionally store in database
    db = next(get_session())
    ctx = ContextService(db)
    
    try:
        # Cache the context
        cache_key = f"github_pr:{pr_number}"
        ctx.cache_context(
            cache_key=cache_key,
            cache_type="github_pr",
            data=context,
            ttl_hours=0.5  # Cache for 30 minutes
        )
        
        # Track the PR for monitoring
        ctx.track_task(
            task_type="github_pr",
            task_id=str(pr_number),
            title=context.get("pr", {}).get("title"),
            status="active",
            metadata={"repository": "your-org/your-repo"}
        )
    finally:
        db.close()
    
    return context
```

### Pattern 3: Use Conversation History for Context-Aware Responses

Store conversation history and use it to provide better context:

```python
from uuid import uuid4

# Generate a session ID (you might get this from the MCP client)
session_id = str(uuid4())

@mcp.tool
async def get_today_events(calendar_id: str = "primary") -> list[dict]:
    """Get today's events and store context."""
    from app.tools.calendar import get_today_events
    
    events = await get_today_events(calendar_id)
    events_dict = [e.model_dump() for e in events]
    
    # Store conversation context
    db = next(get_session())
    ctx = ContextService(db)
    
    try:
        # Store user query
        ctx.add_conversation(
            session_id=session_id,
            role="user",
            content=f"Get today's events from {calendar_id}",
            metadata={"tool": "get_today_events"}
        )
        
        # Store assistant response
        ctx.add_conversation(
            session_id=session_id,
            role="assistant",
            content=f"Found {len(events_dict)} events today",
            metadata={"events_count": len(events_dict)}
        )
        
        # Cache events
        ctx.cache_context(
            cache_key=f"calendar_events:{calendar_id}:today",
            cache_type="calendar_events",
            data={"events": events_dict},
            ttl_hours=0.25  # 15 minutes
        )
    finally:
        db.close()
    
    return events_dict
```

### Pattern 4: Context-Aware Decision Making

Retrieve past context to inform current decisions:

```python
@mcp.tool
async def get_my_work_context() -> dict:
    """Get comprehensive context about user's current work."""
    db = next(get_session())
    ctx = ContextService(db)
    
    try:
        # Get tracked tasks
        tasks = ctx.get_tracked_tasks(status="active")
        
        # Get user preferences
        user_id = "user@example.com"  # Get from context
        prefs = ctx.get_user_preferences(user_id)
        
        # Get recent conversation history
        session_id = "current_session"  # Get from context
        history = ctx.get_recent_context(session_id, days=1, limit=20)
        
        # Combine into context
        return {
            "tracked_tasks": [
                {
                    "type": task.task_type,
                    "id": task.task_id,
                    "title": task.title,
                    "status": task.status
                }
                for task in tasks
            ],
            "user_preferences": prefs,
            "recent_conversations": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in history
            ]
        }
    finally:
        db.close()
```

## Helper Function Pattern

Create a helper function to reduce boilerplate:

```python
from contextlib import contextmanager
from app.db.database import get_session
from app.db.context_service import ContextService

@contextmanager
def get_context_service():
    """Context manager for ContextService."""
    db = next(get_session())
    try:
        yield ContextService(db)
    finally:
        db.close()

# Usage
def my_function():
    with get_context_service() as ctx:
        cached = ctx.get_cached_context("my_key")
        # ... use ctx
```

## Recommended Cache TTL Values

- **Jira Issues**: 1-24 hours (depending on update frequency)
- **GitHub PRs**: 15 minutes - 1 hour
- **Calendar Events**: 15-30 minutes
- **GitHub Commits**: 1-6 hours
- **Jira Boards**: 1-6 hours

## Error Handling

Always handle database errors gracefully:

```python
@mcp.tool
async def safe_cached_get(issue_key: str) -> dict:
    """Safe wrapper that falls back to API on DB error."""
    try:
        db = next(get_session())
        ctx = ContextService(db)
        cached = ctx.get_cached_context(f"jira_issue:{issue_key}")
        if cached:
            db.close()
            return cached
        db.close()
    except Exception as e:
        print(f"Cache error: {e}, falling back to API")
    
    # Fall back to API
    from app.tools.jira import get_single_issue
    issue = await get_single_issue(issue_key)
    return issue.model_dump()
```

## Next Steps

1. Review `app/db/example_integration.py` for more examples
2. Start by adding caching to frequently-used tools
3. Add conversation history tracking for key interactions
4. Implement task tracking for items that need monitoring

