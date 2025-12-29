# Streamlit Frontend Implementation Guide

This guide provides step-by-step instructions for implementing a Streamlit frontend to visualize and interact with the continuum.ai context awareness database.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [Setup and Installation](#setup-and-installation)
4. [Basic App Structure](#basic-app-structure)
5. [Database Connection](#database-connection)
6. [Displaying Data](#displaying-data)
7. [Interactive Features](#interactive-features)
8. [UI Components Reference](#ui-components-reference)
9. [Complete Example App](#complete-example-app)

---

## Prerequisites

Before starting, ensure you have:
- Python 3.8+ installed
- Database initialized (run `python -m app.db.init_db`)
- Basic understanding of Streamlit
- Familiarity with the existing database models and context service

---

## Project Structure

Recommended structure for your Streamlit app:

```
continuum.ai/
├── app/
│   ├── db/              # Existing database code
│   └── streamlit_app.py # Main Streamlit application
├── requirements.txt     # Add streamlit here
└── README.md
```

---

## Setup and Installation

### 1. Install Streamlit

Add Streamlit to your `requirements.txt`:

```txt
streamlit
pandas  # For data tables
plotly  # Optional: for charts
```

Then install:

```bash
pip install streamlit pandas plotly
```

### 2. Verify Database Connection

Ensure your database is initialized and accessible:

```bash
python -m app.db.init_db
```

---

## Basic App Structure

### Minimal Streamlit App Template

Create `app/streamlit_app.py` with this structure:

```python
import streamlit as st
from app.db.database import get_session, init_db
from app.db.context_service import ContextService

# Page configuration
st.set_page_config(
    page_title="Continuum.ai Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Page",
    ["Dashboard", "Conversations", "Context Cache", "Tasks", "Preferences", "Snapshots"]
)

# Main content area
if page == "Dashboard":
    show_dashboard()
elif page == "Conversations":
    show_conversations()
elif page == "Context Cache":
    show_context_cache()
elif page == "Tasks":
    show_tasks()
elif page == "Preferences":
    show_preferences()
elif page == "Snapshots":
    show_snapshots()
```

---

## Database Connection

### Helper Function for Database Access

Create a helper function to manage database sessions:

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

# Usage in Streamlit
def show_data():
    with get_context_service() as ctx:
        # Use ctx to access data
        tasks = ctx.get_tracked_tasks(status="active")
        # Display tasks...
```

### Caching Database Queries

Streamlit's `@st.cache_data` decorator helps cache expensive database queries:

```python
@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_cached_tasks():
    with get_context_service() as ctx:
        return ctx.get_tracked_tasks(status="active")
```

**Note**: Be careful with caching when data changes frequently. Use `st.cache_data.clear()` to refresh.

---

## Displaying Data

### 1. Conversations Page

Display conversation history with filtering options:

```python
def show_conversations():
    st.header("Conversation History")
    
    # Filters in sidebar
    st.sidebar.subheader("Filters")
    session_id = st.sidebar.text_input("Session ID", "")
    user_id = st.sidebar.text_input("User ID", "")
    limit = st.sidebar.slider("Limit", 10, 200, 50)
    
    # Fetch conversations
    with get_context_service() as ctx:
        if session_id:
            conversations = ctx.get_conversation_history(
                session_id=session_id,
                limit=limit,
                user_id=user_id if user_id else None
            )
        else:
            # If no session_id, you might need a different query
            st.warning("Please enter a Session ID")
            return
    
    # Display conversations
    if conversations:
        for conv in conversations:
            with st.expander(f"{conv.role.upper()} - {conv.created_at.strftime('%Y-%m-%d %H:%M:%S')}"):
                st.write(conv.content)
                if conv.meta_data:
                    st.json(conv.meta_data)
    else:
        st.info("No conversations found")
```

**UI Components to Use:**
- `st.expander()` - Collapsible conversation messages
- `st.json()` - Display metadata
- `st.dataframe()` - Table view option
- `st.chat_message()` - Chat-style display (Streamlit 1.28+)

### 2. Context Cache Page

Show cached context entries with expiration status:

```python
def show_context_cache():
    st.header("Context Cache")
    
    # Filters
    cache_type = st.sidebar.selectbox(
        "Cache Type",
        ["All", "jira_issue", "github_pr", "calendar_event"]
    )
    
    with get_context_service() as ctx:
        # Note: You may need to add a method to get all cache entries
        # For now, this is a conceptual example
        db = next(get_session())
        from app.db.models import ContextCache
        from sqlalchemy import desc
        
        query = db.query(ContextCache)
        if cache_type != "All":
            query = query.filter(ContextCache.cache_type == cache_type)
        
        cache_entries = query.order_by(desc(ContextCache.created_at)).limit(100).all()
        db.close()
    
    # Display as cards or table
    if cache_entries:
        for entry in cache_entries:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.subheader(entry.cache_key)
                st.caption(f"Type: {entry.cache_type}")
            with col2:
                st.write(f"Created: {entry.created_at.strftime('%Y-%m-%d')}")
            with col3:
                if entry.expires_at:
                    if entry.expires_at > datetime.utcnow():
                        st.success("Active")
                    else:
                        st.error("Expired")
                else:
                    st.info("No expiry")
            
            with st.expander("View Data"):
                st.json(entry.data)
    else:
        st.info("No cache entries found")
```

**UI Components to Use:**
- `st.columns()` - Multi-column layout
- `st.caption()` - Small text labels
- `st.success()`, `st.error()`, `st.info()` - Status indicators
- `st.json()` - Display JSON data

### 3. Tasks Page

Display tracked tasks with status filtering:

```python
def show_tasks():
    st.header("Tracked Tasks")
    
    # Filters
    task_type = st.sidebar.selectbox(
        "Task Type",
        ["All", "jira_issue", "github_pr", "calendar_event"]
    )
    status = st.sidebar.selectbox(
        "Status",
        ["active", "completed", "archived"]
    )
    
    with get_context_service() as ctx:
        tasks = ctx.get_tracked_tasks(
            task_type=task_type if task_type != "All" else None,
            status=status
        )
    
    # Display as table or cards
    if tasks:
        # Option 1: Table view
        import pandas as pd
        df = pd.DataFrame([{
            "Type": task.task_type,
            "ID": task.task_id,
            "Title": task.title,
            "Status": task.status,
            "Created": task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "Last Checked": task.last_checked_at.strftime('%Y-%m-%d %H:%M:%S') if task.last_checked_at else "Never"
        } for task in tasks])
        st.dataframe(df, use_container_width=True)
        
        # Option 2: Card view
        for task in tasks:
            with st.container():
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"**{task.task_id}**: {task.title}")
                with col2:
                    st.badge(task.status)
                with col3:
                    st.caption(task.created_at.strftime('%Y-%m-%d'))
                
                if task.meta_data:
                    with st.expander("Metadata"):
                        st.json(task.meta_data)
    else:
        st.info("No tasks found")
```

**UI Components to Use:**
- `st.dataframe()` - Pandas DataFrame table
- `st.badge()` - Status badges
- `st.container()` - Grouped content

### 4. User Preferences Page

Display and edit user preferences:

```python
def show_preferences():
    st.header("User Preferences")
    
    user_id = st.sidebar.text_input("User ID", "user@example.com")
    
    with get_context_service() as ctx:
        prefs = ctx.get_user_preferences(user_id)
    
    if prefs:
        st.json(prefs)
        
        # Allow editing (optional)
        if st.button("Edit Preferences"):
            # Create form for editing
            with st.form("edit_prefs"):
                # Add form fields based on your preference structure
                new_prefs = {}
                submitted = st.form_submit_button("Save")
                if submitted:
                    with get_context_service() as ctx:
                        ctx.set_user_preferences(user_id, new_prefs, merge=False)
                    st.success("Preferences updated!")
                    st.rerun()
    else:
        st.info("No preferences found for this user")
```

### 5. Context Snapshots Page

Display saved context snapshots:

```python
def show_snapshots():
    st.header("Context Snapshots")
    
    # Search by tags
    tag_input = st.sidebar.text_input("Search Tags (comma-separated)", "")
    tags = [t.strip() for t in tag_input.split(",")] if tag_input else None
    
    limit = st.sidebar.slider("Limit", 10, 100, 50)
    
    with get_context_service() as ctx:
        snapshots = ctx.search_snapshots(tags=tags, limit=limit)
    
    if snapshots:
        for snapshot in snapshots:
            with st.expander(f"{snapshot.snapshot_key} - {snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S')}"):
                if snapshot.description:
                    st.write(snapshot.description)
                
                if snapshot.tags:
                    st.write("Tags: " + ", ".join(snapshot.tags))
                
                st.json(snapshot.context_data)
    else:
        st.info("No snapshots found")
```

---

## Interactive Features

### Adding New Data

Create forms to add new entries:

```python
def add_conversation_form():
    st.subheader("Add Conversation")
    
    with st.form("add_conversation"):
        session_id = st.text_input("Session ID", required=True)
        user_id = st.text_input("User ID")
        role = st.selectbox("Role", ["user", "assistant", "system"])
        content = st.text_area("Content", required=True)
        
        submitted = st.form_submit_button("Add Conversation")
        
        if submitted:
            with get_context_service() as ctx:
                ctx.add_conversation(
                    session_id=session_id,
                    user_id=user_id if user_id else None,
                    role=role,
                    content=content
                )
            st.success("Conversation added!")
            st.rerun()
```

### Real-time Updates

Use `st.rerun()` to refresh data:

```python
if st.button("Refresh"):
    st.cache_data.clear()  # Clear cache
    st.rerun()  # Rerun the app
```

### Auto-refresh

Add auto-refresh option:

```python
auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", False)
if auto_refresh:
    time.sleep(30)
    st.rerun()
```

---

## UI Components Reference

### Essential Streamlit Components

| Component | Use Case | Example |
|-----------|----------|---------|
| `st.title()` | Main page title | `st.title("Dashboard")` |
| `st.header()` | Section headers | `st.header("Conversations")` |
| `st.subheader()` | Subsection headers | `st.subheader("Recent Messages")` |
| `st.write()` | Display text/data | `st.write(data)` |
| `st.dataframe()` | Display tables | `st.dataframe(df)` |
| `st.json()` | Display JSON | `st.json(data)` |
| `st.expander()` | Collapsible content | `st.expander("Details")` |
| `st.columns()` | Multi-column layout | `col1, col2 = st.columns(2)` |
| `st.sidebar.*` | Sidebar widgets | `st.sidebar.selectbox()` |
| `st.form()` | Form inputs | `with st.form("my_form"):` |
| `st.button()` | Action buttons | `if st.button("Save"):` |
| `st.selectbox()` | Dropdown selection | `st.selectbox("Options", [...])` |
| `st.text_input()` | Text input | `st.text_input("Name")` |
| `st.slider()` | Numeric slider | `st.slider("Limit", 0, 100)` |
| `st.checkbox()` | Checkbox | `st.checkbox("Enable")` |

### Status Indicators

- `st.success()` - Green success message
- `st.error()` - Red error message
- `st.warning()` - Yellow warning message
- `st.info()` - Blue info message

### Data Display

- `st.metric()` - Display metrics/KPIs
- `st.badge()` - Status badges
- `st.caption()` - Small caption text
- `st.code()` - Code blocks

---

## Complete Example App

Here's a complete example combining all features:

```python
import streamlit as st
from datetime import datetime
from contextlib import contextmanager
import pandas as pd

from app.db.database import get_session, init_db
from app.db.context_service import ContextService

# Page config
st.set_page_config(
    page_title="Continuum.ai Dashboard",
    page_icon="🧠",
    layout="wide"
)

# Helper function
@contextmanager
def get_context_service():
    db = next(get_session())
    try:
        yield ContextService(db)
    finally:
        db.close()

# Sidebar
st.sidebar.title("🧠 Continuum.ai")
page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "💬 Conversations", "💾 Cache", "✅ Tasks", "⚙️ Preferences", "📸 Snapshots"]
)

# Dashboard page
if page == "📊 Dashboard":
    st.title("Dashboard")
    
    with get_context_service() as ctx:
        # Get stats
        db = next(get_session())
        from app.db.models import Conversation, ContextCache, TaskTracking
        
        total_convs = db.query(Conversation).count()
        total_cache = db.query(ContextCache).count()
        active_tasks = db.query(TaskTracking).filter(TaskTracking.status == "active").count()
        db.close()
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Conversations", total_convs)
    with col2:
        st.metric("Cache Entries", total_cache)
    with col3:
        st.metric("Active Tasks", active_tasks)
    with col4:
        st.metric("Database", "Connected", "✓")

# Conversations page
elif page == "💬 Conversations":
    st.title("Conversation History")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        session_id = st.text_input("Session ID", key="conv_session")
    with col2:
        limit = st.slider("Limit", 10, 200, 50, key="conv_limit")
    
    if session_id:
        with get_context_service() as ctx:
            conversations = ctx.get_conversation_history(session_id, limit=limit)
        
        if conversations:
            for conv in conversations:
                role_icon = {"user": "👤", "assistant": "🤖", "system": "⚙️"}
                with st.expander(f"{role_icon.get(conv.role, '📝')} {conv.role.upper()} - {conv.created_at.strftime('%Y-%m-%d %H:%M:%S')}"):
                    st.write(conv.content)
                    if conv.meta_data:
                        st.json(conv.meta_data)
        else:
            st.info("No conversations found")
    else:
        st.warning("Please enter a Session ID")

# Cache page
elif page == "💾 Cache":
    st.title("Context Cache")
    
    cache_type = st.sidebar.selectbox("Type", ["All", "jira_issue", "github_pr", "calendar_event"])
    
    with get_context_service() as ctx:
        db = next(get_session())
        from app.db.models import ContextCache
        from sqlalchemy import desc
        
        query = db.query(ContextCache)
        if cache_type != "All":
            query = query.filter(ContextCache.cache_type == cache_type)
        
        entries = query.order_by(desc(ContextCache.created_at)).limit(100).all()
        db.close()
    
    if entries:
        for entry in entries:
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.write(f"**{entry.cache_key}**")
                st.caption(f"Type: {entry.cache_type}")
            with col2:
                st.caption(f"Created: {entry.created_at.strftime('%Y-%m-%d')}")
            with col3:
                if entry.expires_at:
                    if entry.expires_at > datetime.utcnow():
                        st.success("Active")
                    else:
                        st.error("Expired")
                else:
                    st.info("No expiry")
            
            with st.expander("View Data"):
                st.json(entry.data)
    else:
        st.info("No cache entries found")

# Tasks page
elif page == "✅ Tasks":
    st.title("Tracked Tasks")
    
    task_type = st.sidebar.selectbox("Type", ["All", "jira_issue", "github_pr", "calendar_event"])
    status = st.sidebar.selectbox("Status", ["active", "completed", "archived"])
    
    with get_context_service() as ctx:
        tasks = ctx.get_tracked_tasks(
            task_type=task_type if task_type != "All" else None,
            status=status
        )
    
    if tasks:
        df = pd.DataFrame([{
            "Type": task.task_type,
            "ID": task.task_id,
            "Title": task.title or "N/A",
            "Status": task.status,
            "Created": task.created_at.strftime('%Y-%m-%d %H:%M'),
        } for task in tasks])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No tasks found")

# Preferences page
elif page == "⚙️ Preferences":
    st.title("User Preferences")
    
    user_id = st.text_input("User ID", "user@example.com")
    
    with get_context_service() as ctx:
        prefs = ctx.get_user_preferences(user_id)
    
    if prefs:
        st.json(prefs)
    else:
        st.info("No preferences found")

# Snapshots page
elif page == "📸 Snapshots":
    st.title("Context Snapshots")
    
    tag_input = st.sidebar.text_input("Tags (comma-separated)")
    tags = [t.strip() for t in tag_input.split(",")] if tag_input else None
    
    with get_context_service() as ctx:
        snapshots = ctx.search_snapshots(tags=tags, limit=50)
    
    if snapshots:
        for snapshot in snapshots:
            with st.expander(f"{snapshot.snapshot_key} - {snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S')}"):
                if snapshot.description:
                    st.write(snapshot.description)
                if snapshot.tags:
                    st.write("Tags: " + ", ".join(snapshot.tags))
                st.json(snapshot.context_data)
    else:
        st.info("No snapshots found")
```

---

## Running the App

1. **Start the Streamlit app:**

```bash
streamlit run app/streamlit_app.py
```

2. **Access the app:**

The app will open in your browser at `http://localhost:8501`

3. **Development tips:**

- Use `st.rerun()` to refresh data
- Clear cache with `st.cache_data.clear()`
- Use `st.stop()` to stop execution
- Enable "Always rerun" in Streamlit settings for auto-refresh during development

---

## Advanced Features

### 1. Charts and Visualizations

Use Plotly or Streamlit's built-in charts:

```python
import plotly.express as px

# Example: Task status distribution
with get_context_service() as ctx:
    tasks = ctx.get_tracked_tasks()
    
df = pd.DataFrame([{"status": t.status, "type": t.task_type} for t in tasks])
fig = px.pie(df, names="status", title="Task Status Distribution")
st.plotly_chart(fig)
```

### 2. Export Data

Add export functionality:

```python
if st.button("Export to CSV"):
    df = pd.DataFrame([...])  # Your data
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="data.csv",
        mime="text/csv"
    )
```

### 3. Search Functionality

Add search across all data:

```python
search_term = st.text_input("Search")
if search_term:
    # Search in conversations, tasks, etc.
    results = search_all_data(search_term)
    st.write(results)
```

### 4. Authentication (Optional)

Add simple authentication:

```python
def check_password():
    if 'authenticated' not in st.session_state:
        password = st.sidebar.text_input("Password", type="password")
        if password == "your_password":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
            st.stop()
    
    return st.session_state.authenticated

if check_password():
    # Your app code here
    pass
```

---

## Best Practices

1. **Error Handling**: Always wrap database calls in try-except blocks
2. **Caching**: Use `@st.cache_data` for expensive queries
3. **Session State**: Use `st.session_state` to persist data across reruns
4. **Performance**: Limit query results and use pagination for large datasets
5. **User Experience**: Provide loading indicators with `st.spinner()`
6. **Data Validation**: Validate user inputs before database operations

---

## Troubleshooting

### Database Connection Issues

```python
try:
    with get_context_service() as ctx:
        # Your code
except Exception as e:
    st.error(f"Database error: {e}")
    st.info("Make sure the database is initialized: python -m app.db.init_db")
```

### Cache Not Updating

```python
# Clear cache manually
if st.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()
```

### Performance Issues

- Use `limit` parameters in queries
- Implement pagination
- Cache expensive operations
- Use `st.empty()` for dynamic content updates

---

## Next Steps

1. **Customize the UI**: Adjust colors, fonts, and layout to match your brand
2. **Add More Features**: Implement data editing, deletion, and bulk operations
3. **Add Charts**: Visualize trends and statistics
4. **Implement Search**: Add full-text search across all data types
5. **Add Authentication**: Secure the app with user authentication
6. **Deploy**: Deploy to Streamlit Cloud, Heroku, or your own server

---

## Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Streamlit Components Gallery](https://streamlit.io/components)
- [Streamlit Cheat Sheet](https://docs.streamlit.io/library/cheatsheet)

---

## Example: Quick Start Command

```bash
# 1. Install dependencies
pip install streamlit pandas

# 2. Initialize database (if not done)
python -m app.db.init_db

# 3. Run the app
streamlit run app/streamlit_app.py
```

---

**Note**: This guide provides the structure and examples. You'll need to adapt the code to match your specific database schema and requirements. Always test database operations in a development environment first.

