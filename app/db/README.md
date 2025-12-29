# Database Integration for Context Awareness

This module provides database integration for storing and retrieving context information to enable context-aware behavior in the continuum.ai MCP server.

## Features

- **Conversation History**: Store and retrieve conversation history across sessions
- **Context Caching**: Cache external API responses (Jira issues, GitHub PRs, calendar events) to reduce API calls
- **User Preferences**: Store user preferences and settings
- **Task Tracking**: Track tasks (Jira issues, PRs) for monitoring and follow-up
- **Context Snapshots**: Save and retrieve context snapshots for later reference

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure database** (optional):
   By default, the system uses SQLite (no setup needed). To use PostgreSQL or MySQL, set the `DATABASE_URL` environment variable in your `.env` file:
   ```env
   # SQLite (default)
   DATABASE_URL=sqlite:///continuum.db
   
   # PostgreSQL
   DATABASE_URL=postgresql://user:password@localhost:5432/continuum
   
   # MySQL
   DATABASE_URL=mysql+pymysql://user:password@localhost:3306/continuum
   ```

3. **Initialize database**:
   ```bash
   python -m app.db.init_db
   ```
   
   Or programmatically:
   ```python
   from app.db.database import init_db
   init_db()
   ```

## Usage

### Basic Example

```python
from app.db.database import get_session
from app.db.context_service import ContextService

# Get a database session
db = next(get_session())
ctx = ContextService(db)

# Cache a Jira issue
ctx.cache_context(
    cache_key="jira_issue:PROJ-123",
    cache_type="jira_issue",
    data={"key": "PROJ-123", "summary": "Fix bug"},
    ttl_hours=1
)

# Retrieve from cache
cached = ctx.get_cached_context("jira_issue:PROJ-123")

# Store conversation
ctx.add_conversation(
    session_id="session_123",
    role="user",
    content="What PRs need review?",
    user_id="user@example.com"
)

db.close()
```

### Integration with Tools

Here's how to enhance your existing tools with caching:

```python
from app.db.database import get_session
from app.db.context_service import ContextService
from app.tools.jira import get_single_issue

async def get_jira_issue_cached(issue_key: str):
    db = next(get_session())
    ctx = ContextService(db)
    
    # Try cache first
    cache_key = f"jira_issue:{issue_key}"
    cached = ctx.get_cached_context(cache_key, cache_type="jira_issue")
    if cached:
        db.close()
        return cached
    
    # Cache miss - fetch from API
    issue = await get_single_issue(issue_key)
    issue_dict = issue.model_dump()
    
    # Cache for future use
    ctx.cache_context(
        cache_key=cache_key,
        cache_type="jira_issue",
        data=issue_dict,
        ttl_hours=1
    )
    
    db.close()
    return issue_dict
```

### Conversation History

```python
# Store conversation
ctx.add_conversation(
    session_id="session_123",
    user_id="user@example.com",
    role="user",
    content="What are my tasks?",
    metadata={"source": "chat"}
)

# Retrieve history
history = ctx.get_conversation_history("session_123", limit=50)

# Get recent context (last 7 days)
recent = ctx.get_recent_context("session_123", days=7)
```

### Task Tracking

```python
# Track a PR
ctx.track_task(
    task_type="github_pr",
    task_id="42",
    title="Add authentication",
    status="active",
    metadata={"repository": "org/repo"}
)

# Get all active tracked tasks
tasks = ctx.get_tracked_tasks(status="active")

# Update task status
ctx.update_task_status("github_pr", "42", "completed")
```

### User Preferences

```python
# Set preferences
ctx.set_user_preferences(
    user_id="user@example.com",
    preferences={
        "work_hours_start": 9,
        "work_hours_end": 17,
        "timezone": "UTC"
    }
)

# Get preferences
prefs = ctx.get_user_preferences("user@example.com")
```

### Context Snapshots

```python
# Save a snapshot
ctx.save_snapshot(
    snapshot_key="morning_status_2025-01-15",
    context_data={
        "jira_issues": ["PROJ-123"],
        "github_prs": [42],
        "calendar_events": ["Meeting"]
    },
    description="Morning work status",
    tags=["daily", "status"]
)

# Retrieve snapshot
snapshot = ctx.get_snapshot("morning_status_2025-01-15")

# Search by tags
snapshots = ctx.search_snapshots(tags=["daily"])
```

## Database Schema

### Tables

- **conversations**: Stores conversation messages
- **context_cache**: Caches external API responses
- **context_links**: Links conversations to cached context
- **user_preferences**: Stores user preferences
- **task_tracking**: Tracks tasks for monitoring
- **context_snapshots**: Stores context snapshots

## Best Practices

1. **Cache TTL**: Set appropriate TTL values for cached data based on how frequently it changes
   - Jira issues: 1-24 hours
   - GitHub PRs: 15 minutes - 1 hour
   - Calendar events: 15-30 minutes

2. **Session Management**: Always close database sessions after use:
   ```python
   db = next(get_session())
   try:
       # Use db
       pass
   finally:
       db.close()
   ```

3. **Cleanup**: Periodically clean up expired cache entries:
   ```python
   ctx.cleanup_expired_cache()
   ```

4. **Error Handling**: Handle database errors gracefully:
   ```python
   try:
       cached = ctx.get_cached_context(key)
   except Exception as e:
       # Fall back to API call
       pass
   ```

## Examples

See `app/db/example_integration.py` for complete examples of all features.

