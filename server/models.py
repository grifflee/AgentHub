"""
Database models for AgentHub API server.

Uses SQLAlchemy for ORM with PostgreSQL support.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY
import os

# Database configuration
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./agenthub.db"  # Default to SQLite for local development
)

# Handle Render's postgres:// URL format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class LifecycleState(str, PyEnum):
    """Lifecycle states for agents."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    REVOKED = "revoked"


class Agent(Base):
    """SQLAlchemy model for agents in the registry."""
    
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    version = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)
    
    # Store lists as JSON strings for SQLite compatibility
    capabilities = Column(Text, nullable=False, default="[]")
    protocols = Column(Text, nullable=False, default="[]")
    permissions = Column(Text, nullable=False, default="[]")
    
    lifecycle_state = Column(
        String(20),
        nullable=False,
        default=LifecycleState.ACTIVE.value
    )
    
    # Quality signals
    rating_sum = Column(Integer, nullable=False, default=0)
    rating_count = Column(Integer, nullable=False, default=0)
    download_count = Column(Integer, nullable=False, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        import json
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "capabilities": json.loads(self.capabilities),
            "protocols": json.loads(self.protocols),
            "permissions": json.loads(self.permissions),
            "lifecycle_state": self.lifecycle_state,
            "rating_sum": self.rating_sum,
            "rating_count": self.rating_count,
            "download_count": self.download_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def init_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session (for use with Flask)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
