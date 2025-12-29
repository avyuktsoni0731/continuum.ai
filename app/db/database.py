"""
Database connection and initialization utilities.
"""

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{project_root / 'continuum.db'}"  # Default to SQLite
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.getenv("DB_ECHO", "false").lower() == "true"  # Set DB_ECHO=true for SQL logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables."""
    from app.db.models import Base
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DATABASE_URL}")


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.
    Use in FastAPI-style dependencies or context managers.
    
    Example:
        with get_db() as db:
            # use db session
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

