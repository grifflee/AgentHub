"""
Database operations for AgentHub.

This module handles all database interactions. It supports two modes:
1. LOCAL: SQLite database at ~/.agenthub/registry.db (default)
2. REMOTE: API calls to the AgentHub server (when AGENTHUB_API_URL is set)
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import AgentRecord, LifecycleState, Protocol


def is_remote_mode() -> bool:
    """Check if we're using the remote API."""
    return bool(os.environ.get("AGENTHUB_API_URL"))



def get_db_path() -> Path:
    """Get the path to the SQLite database file."""
    db_dir = Path.home() / ".agenthub"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "registry.db"


def get_connection() -> sqlite3.Connection:
    """Create a database connection with row factory for dict-like access."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    """Initialize the database schema if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                version TEXT NOT NULL,
                description TEXT NOT NULL,
                author TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                protocols TEXT NOT NULL,
                permissions TEXT NOT NULL,
                lifecycle_state TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create index for faster capability searches
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)
        """)
        
        conn.commit()
    finally:
        conn.close()


def register_agent(record: AgentRecord) -> AgentRecord:
    """
    Register a new agent in the database.
    
    Raises:
        ValueError: If an agent with the same name already exists
    """
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        data = {
            "name": record.name,
            "version": record.version,
            "description": record.description,
            "author": record.author,
            "capabilities": record.capabilities,
            "protocols": [p.value for p in record.protocols],
            "permissions": record.permissions,
            "lifecycle_state": record.lifecycle_state.value,
        }
        result = api_client.register_agent(data)
        record.id = result.get("id")
        record.created_at = datetime.fromisoformat(result["created_at"]) if result.get("created_at") else None
        record.updated_at = datetime.fromisoformat(result["updated_at"]) if result.get("updated_at") else None
        return record
    
    # Local SQLite mode
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    
    try:
        cursor = conn.execute(
            """
            INSERT INTO agents 
            (name, version, description, author, capabilities, protocols, 
             permissions, lifecycle_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.name,
                record.version,
                record.description,
                record.author,
                json.dumps(record.capabilities),
                json.dumps([p.value for p in record.protocols]),
                json.dumps(record.permissions),
                record.lifecycle_state.value,
                now,
                now,
            )
        )
        conn.commit()
        
        record.id = cursor.lastrowid
        record.created_at = datetime.fromisoformat(now)
        record.updated_at = datetime.fromisoformat(now)
        return record
        
    except sqlite3.IntegrityError:
        raise ValueError(f"Agent '{record.name}' already exists")
    finally:
        conn.close()


def get_agent(name: str) -> Optional[AgentRecord]:
    """Get an agent by name."""
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        result = api_client.get_agent(name)
        if result is None:
            return None
        return _dict_to_record(result)
    
    # Local SQLite mode
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM agents WHERE name = ?", (name,)
        ).fetchone()
        
        if row is None:
            return None
            
        return _row_to_record(row)
    finally:
        conn.close()


def list_agents(
    lifecycle_state: Optional[LifecycleState] = None,
    limit: int = 100
) -> list[AgentRecord]:
    """List all agents, optionally filtered by lifecycle state."""
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        state_value = lifecycle_state.value if lifecycle_state else None
        results = api_client.list_agents(state_value, limit)
        return [_dict_to_record(r) for r in results]
    
    # Local SQLite mode
    conn = get_connection()
    try:
        if lifecycle_state:
            rows = conn.execute(
                "SELECT * FROM agents WHERE lifecycle_state = ? LIMIT ?",
                (lifecycle_state.value, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agents LIMIT ?", (limit,)
            ).fetchall()
        
        return [_row_to_record(row) for row in rows]
    finally:
        conn.close()


def search_agents(
    capability: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 50
) -> list[AgentRecord]:
    """
    Search agents by capability or text query.
    
    This implements basic discovery as described in §3.2.6 of the paper.
    """
    conn = get_connection()
    try:
        if capability:
            # Search in capabilities JSON array
            rows = conn.execute(
                """
                SELECT * FROM agents 
                WHERE capabilities LIKE ? 
                AND lifecycle_state != 'revoked'
                LIMIT ?
                """,
                (f'%"{capability}"%', limit)
            ).fetchall()
        elif query:
            # Full-text search in name and description
            rows = conn.execute(
                """
                SELECT * FROM agents 
                WHERE (name LIKE ? OR description LIKE ?)
                AND lifecycle_state != 'revoked'
                LIMIT ?
                """,
                (f'%{query}%', f'%{query}%', limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agents WHERE lifecycle_state != 'revoked' LIMIT ?",
                (limit,)
            ).fetchall()
        
        return [_row_to_record(row) for row in rows]
    finally:
        conn.close()


def update_lifecycle_state(name: str, state: LifecycleState) -> bool:
    """
    Update an agent's lifecycle state.
    
    This supports the lifecycle transparency requirement (§3.2.2).
    """
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        return api_client.update_lifecycle_state(name, state.value)
    
    # Local SQLite mode
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    
    try:
        cursor = conn.execute(
            """
            UPDATE agents 
            SET lifecycle_state = ?, updated_at = ?
            WHERE name = ?
            """,
            (state.value, now, name)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_agent(name: str) -> bool:
    """Delete an agent from the registry."""
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        return api_client.delete_agent(name)
    
    # Local SQLite mode
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM agents WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _row_to_record(row: sqlite3.Row) -> AgentRecord:
    """Convert a database row to an AgentRecord."""
    return AgentRecord(
        id=row["id"],
        name=row["name"],
        version=row["version"],
        description=row["description"],
        author=row["author"],
        capabilities=json.loads(row["capabilities"]),
        protocols=[Protocol(p) for p in json.loads(row["protocols"])],
        permissions=json.loads(row["permissions"]),
        lifecycle_state=LifecycleState(row["lifecycle_state"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _dict_to_record(data: dict) -> AgentRecord:
    """Convert an API response dict to an AgentRecord."""
    return AgentRecord(
        id=data.get("id"),
        name=data["name"],
        version=data["version"],
        description=data["description"],
        author=data["author"],
        capabilities=data.get("capabilities", []),
        protocols=[Protocol(p) for p in data.get("protocols", [])],
        permissions=data.get("permissions", []),
        lifecycle_state=LifecycleState(data.get("lifecycle_state", "active")),
        created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
    )
