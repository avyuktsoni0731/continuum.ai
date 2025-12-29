"""
Database initialization script.

Run this to create the database tables:
    python -m app.db.init_db
"""

from app.db.database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialization complete!")

