"""
Context service for managing conversation history, cached context, and user preferences.

Provides high-level functions for context awareness.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.db.models import (
    Conversation, ContextCache, ContextLink,
    UserPreference, TaskTracking, ContextSnapshot
)


class ContextService:
    """Service for managing context awareness data."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =============================================================================
    # Conversation History
    # =============================================================================
    
    def add_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Add a conversation message to history."""
        conversation = Conversation(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            meta_data=metadata or {}
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50,
        user_id: Optional[str] = None
    ) -> List[Conversation]:
        """Get conversation history for a session."""
        query = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        )
        
        if user_id:
            query = query.filter(Conversation.user_id == user_id)
        
        return query.order_by(desc(Conversation.created_at)).limit(limit).all()
    
    def get_recent_context(
        self,
        session_id: str,
        days: int = 7,
        limit: int = 100
    ) -> List[Conversation]:
        """Get recent conversation context within a time window."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db.query(Conversation).filter(
            and_(
                Conversation.session_id == session_id,
                Conversation.created_at >= cutoff_date
            )
        ).order_by(desc(Conversation.created_at)).limit(limit).all()
    
    # =============================================================================
    # Context Caching
    # =============================================================================
    
    def cache_context(
        self,
        cache_key: str,
        cache_type: str,
        data: Dict[str, Any],
        ttl_hours: Optional[int] = 24
    ) -> ContextCache:
        """Cache external context data (Jira issues, PRs, etc.)."""
        expires_at = None
        if ttl_hours:
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        # Check if cache entry exists
        cached = self.db.query(ContextCache).filter(
            ContextCache.cache_key == cache_key
        ).first()
        
        if cached:
            cached.data = data
            cached.expires_at = expires_at
            cached.updated_at = datetime.utcnow()
        else:
            cached = ContextCache(
                cache_key=cache_key,
                cache_type=cache_type,
                data=data,
                expires_at=expires_at
            )
            self.db.add(cached)
        
        self.db.commit()
        self.db.refresh(cached)
        return cached
    
    def get_cached_context(
        self,
        cache_key: str,
        cache_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached context if it exists and hasn't expired."""
        query = self.db.query(ContextCache).filter(
            ContextCache.cache_key == cache_key
        )
        
        if cache_type:
            query = query.filter(ContextCache.cache_type == cache_type)
        
        cached = query.first()
        
        if not cached:
            return None
        
        # Check if expired
        if cached.expires_at and cached.expires_at < datetime.utcnow():
            self.db.delete(cached)
            self.db.commit()
            return None
        
        return cached.data
    
    def link_conversation_to_context(
        self,
        conversation_id: int,
        context_cache_id: int
    ) -> ContextLink:
        """Link a conversation to cached context."""
        link = ContextLink(
            conversation_id=conversation_id,
            context_cache_id=context_cache_id
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link
    
    def get_context_for_conversation(
        self,
        conversation_id: int
    ) -> List[Dict[str, Any]]:
        """Get all cached context linked to a conversation."""
        links = self.db.query(ContextLink).filter(
            ContextLink.conversation_id == conversation_id
        ).all()
        
        context_data = []
        for link in links:
            cached = self.db.query(ContextCache).filter(
                ContextCache.id == link.context_cache_id
            ).first()
            if cached and (not cached.expires_at or cached.expires_at >= datetime.utcnow()):
                context_data.append({
                    "type": cached.cache_type,
                    "key": cached.cache_key,
                    "data": cached.data
                })
        
        return context_data
    
    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries. Returns count of deleted entries."""
        count = self.db.query(ContextCache).filter(
            and_(
                ContextCache.expires_at.isnot(None),
                ContextCache.expires_at < datetime.utcnow()
            )
        ).delete()
        self.db.commit()
        return count
    
    # =============================================================================
    # User Preferences
    # =============================================================================
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences, returning defaults if not found."""
        prefs = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if prefs:
            return prefs.preferences
        return {}
    
    def set_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any],
        merge: bool = True
    ) -> UserPreference:
        """Set user preferences. If merge=True, merges with existing preferences."""
        prefs = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if prefs:
            if merge:
                prefs.preferences = {**prefs.preferences, **preferences}
            else:
                prefs.preferences = preferences
            prefs.updated_at = datetime.utcnow()
        else:
            prefs = UserPreference(
                user_id=user_id,
                preferences=preferences
            )
            self.db.add(prefs)
        
        self.db.commit()
        self.db.refresh(prefs)
        return prefs
    
    def update_user_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ) -> UserPreference:
        """Update a single user preference key."""
        prefs = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if prefs:
            prefs.preferences[key] = value
            prefs.updated_at = datetime.utcnow()
        else:
            prefs = UserPreference(
                user_id=user_id,
                preferences={key: value}
            )
            self.db.add(prefs)
        
        self.db.commit()
        self.db.refresh(prefs)
        return prefs
    
    # =============================================================================
    # Task Tracking
    # =============================================================================
    
    def track_task(
        self,
        task_type: str,
        task_id: str,
        title: Optional[str] = None,
        status: str = "active",
        metadata: Optional[Dict[str, Any]] = None
    ) -> TaskTracking:
        """Track a task (Jira issue, PR, etc.) for monitoring."""
        task_key = f"{task_type}:{task_id}"
        
        task = self.db.query(TaskTracking).filter(
            TaskTracking.task_key == task_key
        ).first()
        
        if task:
            task.title = title or task.title
            task.status = status
            task.meta_data = metadata or task.meta_data
            task.updated_at = datetime.utcnow()
        else:
            task = TaskTracking(
                task_type=task_type,
                task_id=task_id,
                task_key=task_key,
                title=title,
                status=status,
                meta_data=metadata or {}
            )
            self.db.add(task)
        
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def get_tracked_tasks(
        self,
        task_type: Optional[str] = None,
        status: str = "active"
    ) -> List[TaskTracking]:
        """Get tracked tasks, optionally filtered by type and status."""
        query = self.db.query(TaskTracking).filter(
            TaskTracking.status == status
        )
        
        if task_type:
            query = query.filter(TaskTracking.task_type == task_type)
        
        return query.order_by(desc(TaskTracking.created_at)).all()
    
    def update_task_status(
        self,
        task_type: str,
        task_id: str,
        status: str,
        last_checked_at: Optional[datetime] = None
    ) -> Optional[TaskTracking]:
        """Update task status and last checked time."""
        task_key = f"{task_type}:{task_id}"
        task = self.db.query(TaskTracking).filter(
            TaskTracking.task_key == task_key
        ).first()
        
        if task:
            task.status = status
            task.last_checked_at = last_checked_at or datetime.utcnow()
            task.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(task)
        
        return task
    
    # =============================================================================
    # Context Snapshots
    # =============================================================================
    
    def save_snapshot(
        self,
        snapshot_key: str,
        context_data: Dict[str, Any],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> ContextSnapshot:
        """Save a context snapshot for later reference."""
        snapshot = self.db.query(ContextSnapshot).filter(
            ContextSnapshot.snapshot_key == snapshot_key
        ).first()
        
        if snapshot:
            snapshot.context_data = context_data
            snapshot.description = description or snapshot.description
            snapshot.tags = tags or snapshot.tags
        else:
            snapshot = ContextSnapshot(
                snapshot_key=snapshot_key,
                description=description,
                context_data=context_data,
                tags=tags or []
            )
            self.db.add(snapshot)
        
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot
    
    def get_snapshot(self, snapshot_key: str) -> Optional[Dict[str, Any]]:
        """Get a context snapshot by key."""
        snapshot = self.db.query(ContextSnapshot).filter(
            ContextSnapshot.snapshot_key == snapshot_key
        ).first()
        
        if snapshot:
            return snapshot.context_data
        return None
    
    def search_snapshots(
        self,
        tags: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[ContextSnapshot]:
        """Search snapshots by tags."""
        query = self.db.query(ContextSnapshot)
        
        if tags:
            # SQLite JSON search (simple tag matching)
            for tag in tags:
                query = query.filter(
                    ContextSnapshot.tags.contains([tag])
                )
        
        return query.order_by(desc(ContextSnapshot.created_at)).limit(limit).all()


def get_context_service(db: Session) -> ContextService:
    """Get a ContextService instance with the given database session."""
    return ContextService(db)

