#!/usr/bin/env python3
"""
Initialize database tables for PHANTOM Security AI
"""

from app.database import engine, Base
from app.models.scan import Scan  # Import all models
import sys

def create_tables():
    """Create all database tables"""
    try:
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

if __name__ == "__main__":
    success = create_tables()
    sys.exit(0 if success else 1)