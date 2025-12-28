"""
Database models for context awareness.

Stores conversation history, cached context, user preferences, and task tracking.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    JSON, Float, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Conversation(Base):
    """Stores conversation history and context."""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    meta_data = Column(JSON, nullable=True)  # Store additional context
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    # Relationships
    context_links = relationship("ContextLink", back_populates="conversation")


class ContextCache(Base):
    """Caches external data (Jira issues, PRs, calendar events) for faster access."""
    __tablename__ = "context_cache"
    
    id = Column(Integer, primary_key=True)
    cache_key = Column(String(500), unique=True, nullable=False, index=True)
    cache_type = Column(String(100), nullable=False, index=True)  # 'jira_issue', 'github_pr', 'calendar_event'
    data = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    context_links = relationship("ContextLink", back_populates="cached_context")


class ContextLink(Base):
    """Links conversations to cached context (many-to-many relationship)."""
    __tablename__ = "context_links"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    context_cache_id = Column(Integer, ForeignKey("context_cache.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="context_links")
    cached_context = relationship("ContextCache", back_populates="context_links")


class UserPreference(Base):
    """Stores user preferences and settings."""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    preferences = Column(JSON, nullable=False, default=dict)  # Store all preferences as JSON
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class TaskTracking(Base):
    """Tracks tasks and items the AI should monitor or follow up on."""
    __tablename__ = "task_tracking"
    
    id = Column(Integer, primary_key=True)
    task_type = Column(String(100), nullable=False, index=True)  # 'jira_issue', 'github_pr', 'calendar_event'
    task_id = Column(String(255), nullable=False, index=True)  # External ID (e.g., "PROJ-123", PR #42)
    task_key = Column(String(500), nullable=False, unique=True, index=True)  # Composite key: type:id
    title = Column(String(500), nullable=True)
    status = Column(String(100), nullable=False, default="active")  # 'active', 'completed', 'archived'
    meta_data = Column(JSON, nullable=True)  # Store task-specific data
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class ContextSnapshot(Base):
    """Stores context snapshots for later reference."""
    __tablename__ = "context_snapshots"
    
    id = Column(Integer, primary_key=True)
    snapshot_key = Column(String(500), unique=True, nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    context_data = Column(JSON, nullable=False)  # Store any context data
    tags = Column(JSON, nullable=True)  # Array of tags for categorization
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)

