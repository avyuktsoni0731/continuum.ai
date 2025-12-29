"""
Streamlit frontend for Continuum.ai context awareness system.

Run with: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from datetime import datetime, timezone
from contextlib import contextmanager
import json
from typing import Optional, List

from app.db.database import get_session, init_db
from app.db.context_service import ContextService
from app.db.models import Conversation, ContextCache, TaskTracking, ContextSnapshot
from sqlalchemy import desc, func

# Page configuration
st.set_page_config(
    page_title="Continuum.ai Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)


@contextmanager
def get_context_service():
    """Context manager for ContextService."""
    db = get_session()
    try:
        yield ContextService(db)
    finally:
        db.close()


def get_db_session():
    """Get a database session for direct queries."""
    return get_session()


# =============================================================================
# Dashboard Page
# =============================================================================

def show_dashboard():
    """Display dashboard with overview metrics."""
    st.title("📊 Dashboard")
    st.markdown("---")
    
    # Get database session
    db = get_db_session()
    
    try:
        # Calculate metrics
        total_convs = db.query(Conversation).count()
        total_cache = db.query(ContextCache).count()
        active_tasks = db.query(TaskTracking).filter(TaskTracking.status == "active").count()
        completed_tasks = db.query(TaskTracking).filter(TaskTracking.status == "completed").count()
        
        # Get recent activity
        recent_convs = db.query(Conversation).order_by(desc(Conversation.created_at)).limit(5).all()
        
        # Cache statistics
        expired_cache = db.query(ContextCache).filter(
            ContextCache.expires_at.isnot(None),
            ContextCache.expires_at < datetime.now(timezone.utc)
        ).count()
        active_cache = total_cache - expired_cache
        
    finally:
        db.close()
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Conversations", total_convs)
    with col2:
        st.metric("Cache Entries", total_cache, delta=active_cache)
    with col3:
        st.metric("Active Tasks", active_tasks)
    with col4:
        st.metric("Completed Tasks", completed_tasks)
    
    st.markdown("---")
    
    # Recent activity
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Recent Conversations")
        if recent_convs:
            for conv in recent_convs:
                role_icon = {"user": "👤", "assistant": "🤖", "system": "⚙️"}
                with st.expander(f"{role_icon.get(conv.role, '📝')} {conv.role.upper()} - {conv.created_at.strftime('%Y-%m-%d %H:%M:%S')}"):
                    st.write(conv.content[:200] + "..." if len(conv.content) > 200 else conv.content)
                    st.caption(f"Session: {conv.session_id}")
        else:
            st.info("No conversations yet")
    
    with col2:
        st.subheader("Quick Actions")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        if st.button("🗑️ Clear Expired Cache", use_container_width=True):
            with get_context_service() as ctx:
                deleted = ctx.cleanup_expired_cache()
                st.success(f"Cleared {deleted} expired cache entries")
                st.rerun()
        
        if st.button("📊 View All Tasks", use_container_width=True):
            st.session_state.page = "✅ Tasks"
            st.rerun()


# =============================================================================
# Conversations Page
# =============================================================================

def show_conversations():
    """Display conversation history."""
    st.title("💬 Conversation History")
    st.markdown("---")
    
    # Sidebar filters
    st.sidebar.subheader("Filters")
    session_id = st.sidebar.text_input("Session ID", value=st.session_state.get("conv_session_id", ""), key="conv_session_id")
    user_id = st.sidebar.text_input("User ID", value=st.session_state.get("conv_user_id", ""), key="conv_user_id")
    limit = st.sidebar.slider("Limit", 10, 200, value=st.session_state.get("conv_limit", 50), key="conv_limit")
    
    # Add conversation form
    with st.expander("➕ Add New Conversation", expanded=False):
        with st.form("add_conversation_form"):
            new_session_id = st.text_input("Session ID *")
            new_user_id = st.text_input("User ID")
            new_role = st.selectbox("Role", ["user", "assistant", "system"])
            new_content = st.text_area("Content *", height=150)
            submitted = st.form_submit_button("Add Conversation")
            
            if submitted:
                if new_session_id and new_content:
                    try:
                        with get_context_service() as ctx:
                            ctx.add_conversation(
                                session_id=new_session_id,
                                user_id=new_user_id if new_user_id else None,
                                role=new_role,
                                content=new_content
                            )
                        st.success("Conversation added successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding conversation: {e}")
                else:
                    st.warning("Please fill in required fields (Session ID and Content)")
    
    # Fetch and display conversations
    if session_id:
        try:
            with get_context_service() as ctx:
                conversations = ctx.get_conversation_history(
                    session_id=session_id,
                    limit=limit,
                    user_id=user_id if user_id else None
                )
            
            if conversations:
                st.subheader(f"Found {len(conversations)} conversation(s)")
                
                # Display options
                view_mode = st.radio("View Mode", ["Chat View", "Table View"], horizontal=True)
                
                if view_mode == "Chat View":
                    # Chat-style display
                    for conv in reversed(conversations):  # Show oldest first
                        role_icon = {"user": "👤", "assistant": "🤖", "system": "⚙️"}
                        role_color = {"user": "blue", "assistant": "green", "system": "gray"}
                        
                        with st.chat_message(conv.role, avatar=role_icon.get(conv.role, "📝")):
                            st.write(conv.content)
                            st.caption(f"{conv.created_at.strftime('%Y-%m-%d %H:%M:%S')} | Session: {conv.session_id}")
                            if conv.meta_data:
                                with st.expander("Metadata"):
                                    st.json(conv.meta_data)
                else:
                    # Table view (no pandas)
                    rows = [{
                        "Role": conv.role,
                        "Content": conv.content[:100] + "..." if len(conv.content) > 100 else conv.content,
                        "User ID": conv.user_id or "N/A",
                        "Created": conv.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        "ID": conv.id
                    } for conv in conversations]
                    st.table(rows)
            else:
                st.info("No conversations found for this session ID")
        except Exception as e:
            st.error(f"Error fetching conversations: {e}")
    else:
        st.warning("👈 Please enter a Session ID in the sidebar to view conversations")
        
        # Show all sessions
        st.subheader("Available Sessions")
        db = get_db_session()
        try:
            sessions = db.query(Conversation.session_id).distinct().limit(20).all()
            if sessions:
                session_list = [s[0] for s in sessions]
                selected = st.selectbox("Select a session to view:", session_list)
                if selected:
                    st.session_state.conv_session_id = selected
                    st.rerun()
            else:
                st.info("No sessions found in database")
        finally:
            db.close()


# =============================================================================
# Context Cache Page
# =============================================================================

def show_context_cache():
    """Display context cache entries."""
    st.title("💾 Context Cache")
    st.markdown("---")
    
    # Sidebar filters
    st.sidebar.subheader("Filters")
    cache_type = st.sidebar.selectbox(
        "Cache Type",
        ["All", "jira_issue", "github_pr", "calendar_event", "calendar_events"],
        key="cache_type_filter"
    )
    show_expired = st.sidebar.checkbox("Show Expired", value=False, key="show_expired")
    limit = st.sidebar.slider("Limit", 10, 200, value=50, key="cache_limit")
    
    # Fetch cache entries
    db = get_db_session()
    try:
        query = db.query(ContextCache)
        
        if cache_type != "All":
            query = query.filter(ContextCache.cache_type == cache_type)
        
        if not show_expired:
            query = query.filter(
                (ContextCache.expires_at.is_(None)) | 
                (ContextCache.expires_at >= datetime.now(timezone.utc))
            )
        
        cache_entries = query.order_by(desc(ContextCache.created_at)).limit(limit).all()
    finally:
        db.close()
    
    # Display cache entries
    if cache_entries:
        st.subheader(f"Found {len(cache_entries)} cache entry/entries")
        
        view_mode = st.radio("View Mode", ["Card View", "Table View"], horizontal=True, key="cache_view")
        
        if view_mode == "Card View":
            for entry in cache_entries:
                with st.container():
                    col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                    
                    with col1:
                        st.write(f"**{entry.cache_key}**")
                        st.caption(f"Type: `{entry.cache_type}`")
                    
                    with col2:
                        st.caption("Created")
                        st.write(entry.created_at.strftime('%Y-%m-%d'))
                    
                    with col3:
                        if entry.expires_at:
                            if entry.expires_at > datetime.now(timezone.utc):
                                st.success("Active")
                            else:
                                st.error("Expired")
                            st.caption(f"Expires: {entry.expires_at.strftime('%Y-%m-%d %H:%M')}")
                        else:
                            st.info("No expiry")
                    
                    with col4:
                        st.caption("Size")
                        data_size = len(json.dumps(entry.data))
                        st.write(f"{data_size} bytes")
                    
                    with st.expander("View Data"):
                        st.json(entry.data)
                    
                    st.divider()
        else:
            # Table view (no pandas)
            rows = [{
                "Cache Key": entry.cache_key,
                "Type": entry.cache_type,
                "Created": entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "Expires": entry.expires_at.strftime('%Y-%m-%d %H:%M:%S') if entry.expires_at else "Never",
                "Status": "Active" if (not entry.expires_at or entry.expires_at > datetime.now(timezone.utc)) else "Expired"
            } for entry in cache_entries]
            st.table(rows)
    else:
        st.info("No cache entries found")
    
    # Add cache entry form
    with st.expander("➕ Add Cache Entry", expanded=False):
        with st.form("add_cache_form"):
            cache_key = st.text_input("Cache Key *")
            cache_type_input = st.text_input("Cache Type *")
            ttl_hours = st.number_input("TTL (hours)", min_value=0, value=24, step=1)
            cache_data = st.text_area("Data (JSON)", height=200, help="Enter JSON data")
            
            submitted = st.form_submit_button("Add Cache Entry")
            
            if submitted:
                if cache_key and cache_type_input and cache_data:
                    try:
                        data = json.loads(cache_data)
                        with get_context_service() as ctx:
                            ctx.cache_context(
                                cache_key=cache_key,
                                cache_type=cache_type_input,
                                data=data,
                                ttl_hours=ttl_hours if ttl_hours > 0 else None
                            )
                        st.success("Cache entry added successfully!")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Invalid JSON data")
                    except Exception as e:
                        st.error(f"Error adding cache entry: {e}")
                else:
                    st.warning("Please fill in all required fields")


# =============================================================================
# Tasks Page
# =============================================================================

def show_tasks():
    """Display tracked tasks."""
    st.title("✅ Tracked Tasks")
    st.markdown("---")
    
    # Sidebar filters
    st.sidebar.subheader("Filters")
    task_type = st.sidebar.selectbox(
        "Task Type",
        ["All", "jira_issue", "github_pr", "calendar_event"],
        key="task_type_filter"
    )
    status = st.sidebar.selectbox(
        "Status",
        ["active", "completed", "archived"],
        key="task_status_filter"
    )
    
    # Fetch tasks
    with get_context_service() as ctx:
        tasks = ctx.get_tracked_tasks(
            task_type=task_type if task_type != "All" else None,
            status=status
        )
    
    # Display tasks
    if tasks:
        st.subheader(f"Found {len(tasks)} task(s)")
        
        view_mode = st.radio("View Mode", ["Table View", "Card View"], horizontal=True, key="task_view")
        
        if view_mode == "Table View":
            rows = [{
                "Type": task.task_type,
                "ID": task.task_id,
                "Title": task.title or "N/A",
                "Status": task.status,
                "Created": task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "Last Checked": task.last_checked_at.strftime('%Y-%m-%d %H:%M:%S') if task.last_checked_at else "Never",
                "Updated": task.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            } for task in tasks]
            st.table(rows)
        else:
            # Card view
            for task in tasks:
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    
                    with col1:
                        st.write(f"**{task.task_id}**: {task.title or 'No title'}")
                        st.caption(f"Type: `{task.task_type}`")
                    
                    with col2:
                        status_color = {"active": "green", "completed": "blue", "archived": "gray"}
                        st.markdown(f"<span style='color: {status_color.get(task.status, 'black')}'>{task.status.upper()}</span>", unsafe_allow_html=True)
                    
                    with col3:
                        st.caption("Created")
                        st.write(task.created_at.strftime('%Y-%m-%d'))
                    
                    if task.meta_data:
                        with st.expander("Metadata"):
                            st.json(task.meta_data)
                    
                    if task.last_checked_at:
                        st.caption(f"Last checked: {task.last_checked_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    st.divider()
    else:
        st.info("No tasks found")
    
    # Add task form
    with st.expander("➕ Add New Task", expanded=False):
        with st.form("add_task_form"):
            task_type_input = st.selectbox("Task Type", ["jira_issue", "github_pr", "calendar_event"])
            task_id = st.text_input("Task ID *")
            title = st.text_input("Title")
            status_input = st.selectbox("Status", ["active", "completed", "archived"])
            metadata_json = st.text_area("Metadata (JSON)", height=150, help="Optional JSON metadata")
            
            submitted = st.form_submit_button("Add Task")
            
            if submitted:
                if task_id:
                    try:
                        metadata = None
                        if metadata_json:
                            metadata = json.loads(metadata_json)
                        
                        with get_context_service() as ctx:
                            ctx.track_task(
                                task_type=task_type_input,
                                task_id=task_id,
                                title=title if title else None,
                                status=status_input,
                                metadata=metadata
                            )
                        st.success("Task added successfully!")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Invalid JSON in metadata")
                    except Exception as e:
                        st.error(f"Error adding task: {e}")
                else:
                    st.warning("Please enter a Task ID")


# =============================================================================
# Preferences Page
# =============================================================================

def show_preferences():
    """Display and manage user preferences."""
    st.title("⚙️ User Preferences")
    st.markdown("---")
    
    # User ID input
    user_id = st.sidebar.text_input("User ID", value=st.session_state.get("pref_user_id", "user@example.com"), key="pref_user_id")
    
    # Fetch preferences
    with get_context_service() as ctx:
        prefs = ctx.get_user_preferences(user_id)
    
    if prefs:
        st.subheader(f"Preferences for: `{user_id}`")
        
        # Display preferences
        st.json(prefs)
        
        # Edit preferences
        with st.expander("✏️ Edit Preferences", expanded=False):
            with st.form("edit_prefs_form"):
                st.info("Enter JSON to replace all preferences, or use the form below to update specific keys")
                
                new_prefs_json = st.text_area("New Preferences (JSON)", value=str(prefs), height=200)
                merge_mode = st.checkbox("Merge with existing (keep old values if not in new)", value=True)
                
                submitted = st.form_submit_button("Update Preferences")
                
                if submitted:
                    try:
                        new_prefs = json.loads(new_prefs_json)
                        
                        with get_context_service() as ctx:
                            ctx.set_user_preferences(
                                user_id=user_id,
                                preferences=new_prefs,
                                merge=merge_mode
                            )
                        st.success("Preferences updated successfully!")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Invalid JSON format")
                    except Exception as e:
                        st.error(f"Error updating preferences: {e}")
        
        # Quick update single preference
        with st.expander("🔧 Quick Update", expanded=False):
            with st.form("quick_update_form"):
                pref_key = st.text_input("Preference Key")
                pref_value = st.text_input("Preference Value")
                
                submitted = st.form_submit_button("Update Single Preference")
                
                if submitted:
                    if pref_key:
                        try:
                            # Try to parse as JSON, otherwise store as string
                            try:
                                pref_value_parsed = json.loads(pref_value)
                            except:
                                pref_value_parsed = pref_value
                            
                            with get_context_service() as ctx:
                                ctx.update_user_preference(user_id, pref_key, pref_value_parsed)
                            st.success(f"Updated `{pref_key}` successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating preference: {e}")
    else:
        st.info(f"No preferences found for user: `{user_id}`")
        
        # Create new preferences
        with st.expander("➕ Create Preferences", expanded=False):
            with st.form("create_prefs_form"):
                new_prefs_json = st.text_area("Preferences (JSON)", value="{}", height=200)
                
                submitted = st.form_submit_button("Create Preferences")
                
                if submitted:
                    try:
                        new_prefs = json.loads(new_prefs_json)
                        
                        with get_context_service() as ctx:
                            ctx.set_user_preferences(
                                user_id=user_id,
                                preferences=new_prefs,
                                merge=False
                            )
                        st.success("Preferences created successfully!")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Invalid JSON format")
                    except Exception as e:
                        st.error(f"Error creating preferences: {e}")


# =============================================================================
# Snapshots Page
# =============================================================================

def show_snapshots():
    """Display context snapshots."""
    st.title("📸 Context Snapshots")
    st.markdown("---")
    
    # Sidebar filters
    st.sidebar.subheader("Filters")
    tag_input = st.sidebar.text_input("Search Tags (comma-separated)", key="snapshot_tags")
    tags = [t.strip() for t in tag_input.split(",") if t.strip()] if tag_input else None
    limit = st.sidebar.slider("Limit", 10, 100, value=50, key="snapshot_limit")
    
    # Fetch snapshots
    with get_context_service() as ctx:
        snapshots = ctx.search_snapshots(tags=tags, limit=limit)
    
    # Display snapshots
    if snapshots:
        st.subheader(f"Found {len(snapshots)} snapshot(s)")
        
        for snapshot in snapshots:
            with st.expander(f"📸 {snapshot.snapshot_key} - {snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S')}"):
                if snapshot.description:
                    st.write(f"**Description:** {snapshot.description}")
                
                if snapshot.tags:
                    tag_str = ", ".join([f"`{tag}`" for tag in snapshot.tags])
                    st.write(f"**Tags:** {tag_str}")
                
                st.write("**Context Data:**")
                st.json(snapshot.context_data)
    else:
        st.info("No snapshots found")
    
    # Add snapshot form
    with st.expander("➕ Add New Snapshot", expanded=False):
        with st.form("add_snapshot_form"):
            snapshot_key = st.text_input("Snapshot Key *")
            description = st.text_input("Description")
            tags_input = st.text_input("Tags (comma-separated)")
            context_data_json = st.text_area("Context Data (JSON) *", height=200)
            
            submitted = st.form_submit_button("Add Snapshot")
            
            if submitted:
                if snapshot_key and context_data_json:
                    try:
                        context_data = json.loads(context_data_json)
                        tags_list = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else None
                        
                        with get_context_service() as ctx:
                            ctx.save_snapshot(
                                snapshot_key=snapshot_key,
                                context_data=context_data,
                                description=description if description else None,
                                tags=tags_list
                            )
                        st.success("Snapshot added successfully!")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Invalid JSON format")
                    except Exception as e:
                        st.error(f"Error adding snapshot: {e}")
                else:
                    st.warning("Please fill in required fields (Snapshot Key and Context Data)")


# =============================================================================
# Main App
# =============================================================================

def main():
    """Main application entry point."""
    # Sidebar navigation
    st.sidebar.title("🧠 Continuum.ai")
    st.sidebar.markdown("---")
    
    # Check database connection
    try:
        db = get_db_session()
        db.close()
        st.sidebar.success("✓ Database Connected")
    except Exception as e:
        st.sidebar.error(f"✗ Database Error: {e}")
        st.sidebar.info("Run: `python -m app.db.init_db`")
        st.stop()
    
    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["📊 Dashboard", "💬 Conversations", "💾 Cache", "✅ Tasks", "⚙️ Preferences", "📸 Snapshots"],
        key="main_nav"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Context Awareness System")
    
    # Route to appropriate page
    if page == "📊 Dashboard":
        show_dashboard()
    elif page == "💬 Conversations":
        show_conversations()
    elif page == "💾 Cache":
        show_context_cache()
    elif page == "✅ Tasks":
        show_tasks()
    elif page == "⚙️ Preferences":
        show_preferences()
    elif page == "📸 Snapshots":
        show_snapshots()


if __name__ == "__main__":
    main()
