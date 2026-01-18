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
                rating_sum INTEGER NOT NULL DEFAULT 0,
                rating_count INTEGER NOT NULL DEFAULT 0,
                download_count INTEGER NOT NULL DEFAULT 0,
                badges TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create version history table for tracking updates
        conn.execute("""
            CREATE TABLE IF NOT EXISTS version_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                version TEXT NOT NULL,
                description TEXT,
                author TEXT,
                capabilities TEXT,
                protocols TEXT,
                permissions TEXT,
                manifest_snapshot TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (agent_name) REFERENCES agents(name) ON DELETE CASCADE
            )
        """)

        # Create index for faster capability searches
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)
        """)

        # Create index for version history lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_version_history_agent ON version_history(agent_name)
        """)

        # Migration: Add rating columns if they don't exist (for existing DBs)
        for column, default in [("rating_sum", 0), ("rating_count", 0), ("download_count", 0)]:
            try:
                conn.execute(f"ALTER TABLE agents ADD COLUMN {column} INTEGER DEFAULT {default}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Migration: Add badges column if it doesn't exist
        try:
            conn.execute("ALTER TABLE agents ADD COLUMN badges TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.commit()
    finally:
        conn.close()


def compute_badges(download_count: int, rating_count: int, rating_sum: int) -> list[str]:
    """
    Compute badges for an agent based on quality signals.
    
    Args:
        download_count: Number of downloads
        rating_count: Number of ratings
        rating_sum: Sum of all ratings
        
    Returns:
        List of badge names
    """
    badges = []
    
    # Popular badge: >10 downloads OR >10 ratings
    if download_count > 10 or rating_count > 10:
        badges.append("popular")
    
    # Future badges can be added here:
    # - "verified": Has behavioral test evidence
    # - "security-audited": Has security attestation
    # - "well-documented": Documentation completeness score
    # - "highly-rated": Average rating > 4.5 with >5 ratings
    
    return badges


def update_badges(name: str) -> list[str]:
    """
    Update and persist badges for an agent based on current metrics.
    
    Args:
        name: Agent name
        
    Returns:
        Updated list of badges
        
    Raises:
        ValueError: If agent not found
    """
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        # For now, badges are computed server-side
        # This could call an API endpoint if we add one
        agent = get_agent(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found")
        badges = compute_badges(agent.download_count, agent.rating_count, agent.rating_sum)
        return badges
    
    # Local SQLite mode
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    
    try:
        # Get current metrics
        row = conn.execute(
            "SELECT download_count, rating_count, rating_sum FROM agents WHERE name = ?",
            (name,)
        ).fetchone()
        
        if not row:
            raise ValueError(f"Agent '{name}' not found")
        
        # Compute badges
        badges = compute_badges(row["download_count"], row["rating_count"], row["rating_sum"])
        
        # Update database
        conn.execute(
            """
            UPDATE agents 
            SET badges = ?, updated_at = ?
            WHERE name = ?
            """,
            (json.dumps(badges), now, name)
        )
        conn.commit()
        return badges
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
    
    # Compute initial badges
    badges = compute_badges(record.download_count, record.rating_count, record.rating_sum)
    
    try:
        cursor = conn.execute(
            """
            INSERT INTO agents 
            (name, version, description, author, capabilities, protocols, 
             permissions, lifecycle_state, badges, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(badges),
                now,
                now,
            )
        )
        conn.commit()
        
        record.id = cursor.lastrowid
        record.badges = badges
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


def update_agent_rating(name: str, rating: int) -> tuple[int, int]:
    """
    Add a rating to an agent.
    
    Args:
        name: Agent name
        rating: Rating value (1-5)
        
    Returns:
        Tuple of (new_rating_sum, new_rating_count)
        
    Raises:
        ValueError: If agent not found
    """
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        result = api_client.rate_agent(name, rating)
        return result["rating_sum"], result["rating_count"]
    
    # Local SQLite mode
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    
    try:
        # First check if agent exists
        existing = conn.execute(
            "SELECT rating_sum, rating_count FROM agents WHERE name = ?", (name,)
        ).fetchone()
        
        if not existing:
            raise ValueError(f"Agent '{name}' not found")
        
        # Update ratings
        new_sum = (existing["rating_sum"] or 0) + rating
        new_count = (existing["rating_count"] or 0) + 1
        
        # Recompute badges (popular badge may change based on rating_count)
        badges = compute_badges(existing["download_count"] or 0, new_count, new_sum)
        
        conn.execute(
            """
            UPDATE agents 
            SET rating_sum = ?, rating_count = ?, badges = ?, updated_at = ?
            WHERE name = ?
            """,
            (new_sum, new_count, json.dumps(badges), now, name)
        )
        conn.commit()
        return new_sum, new_count
    finally:
        conn.close()


def _row_to_record(row: sqlite3.Row) -> AgentRecord:
    """Convert a database row to an AgentRecord."""
    # Handle both old and new schema (migration compatibility)
    keys = row.keys()
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
        rating_sum=row["rating_sum"] if "rating_sum" in keys else 0,
        rating_count=row["rating_count"] if "rating_count" in keys else 0,
        download_count=row["download_count"] if "download_count" in keys else 0,
        badges=json.loads(row["badges"]) if "badges" in keys else [],
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
        rating_sum=data.get("rating_sum", 0),
        rating_count=data.get("rating_count", 0),
        download_count=data.get("download_count", 0),
        badges=data.get("badges", []),
        created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
    )


def bump_version(version: str, bump_type: str) -> str:
    """
    Increment a semantic version string.

    Args:
        version: Current version (e.g., "1.2.3")
        bump_type: One of "major", "minor", or "patch"

    Returns:
        New version string

    Raises:
        ValueError: If version format is invalid or bump_type is unknown
    """
    import re
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")


def update_agent(
    name: str,
    new_record: Optional[AgentRecord] = None,
    bump_type: Optional[str] = None
) -> AgentRecord:
    """
    Update an existing agent, storing the previous version in history.

    Args:
        name: Name of the agent to update
        new_record: New agent record with updated fields (if None, only bump version)
        bump_type: Version bump type ("major", "minor", "patch") - auto-increments version

    Returns:
        Updated AgentRecord

    Raises:
        ValueError: If agent not found or validation fails
    """
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        data = None
        if new_record:
            data = {
                "name": new_record.name,
                "version": new_record.version,
                "description": new_record.description,
                "author": new_record.author,
                "capabilities": new_record.capabilities,
                "protocols": [p.value for p in new_record.protocols],
                "permissions": new_record.permissions,
                "lifecycle_state": new_record.lifecycle_state.value,
            }
        result = api_client.update_agent(name, data, bump_type)
        return _dict_to_record(result)

    # Local SQLite mode
    conn = get_connection()
    now = datetime.utcnow().isoformat()

    try:
        # Get existing agent
        row = conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
        if not row:
            raise ValueError(f"Agent '{name}' not found")

        existing = _row_to_record(row)

        # Store current version in history
        manifest_snapshot = json.dumps({
            "name": existing.name,
            "version": existing.version,
            "description": existing.description,
            "author": existing.author,
            "capabilities": existing.capabilities,
            "protocols": [p.value for p in existing.protocols],
            "permissions": existing.permissions,
            "lifecycle_state": existing.lifecycle_state.value,
        })

        conn.execute(
            """
            INSERT INTO version_history
            (agent_name, version, description, author, capabilities, protocols, permissions, manifest_snapshot, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                existing.name,
                existing.version,
                existing.description,
                existing.author,
                json.dumps(existing.capabilities),
                json.dumps([p.value for p in existing.protocols]),
                json.dumps(existing.permissions),
                manifest_snapshot,
                existing.updated_at.isoformat() if existing.updated_at else now,
            )
        )

        # Determine new values
        if new_record:
            new_version = new_record.version
            new_description = new_record.description
            new_author = new_record.author
            new_capabilities = new_record.capabilities
            new_protocols = new_record.protocols
            new_permissions = new_record.permissions
            new_lifecycle = new_record.lifecycle_state
        else:
            new_version = existing.version
            new_description = existing.description
            new_author = existing.author
            new_capabilities = existing.capabilities
            new_protocols = existing.protocols
            new_permissions = existing.permissions
            new_lifecycle = existing.lifecycle_state

        # Apply version bump if requested
        if bump_type:
            new_version = bump_version(new_version, bump_type)

        # Update the agent
        conn.execute(
            """
            UPDATE agents
            SET version = ?, description = ?, author = ?, capabilities = ?,
                protocols = ?, permissions = ?, lifecycle_state = ?, updated_at = ?
            WHERE name = ?
            """,
            (
                new_version,
                new_description,
                new_author,
                json.dumps(new_capabilities),
                json.dumps([p.value for p in new_protocols]),
                json.dumps(new_permissions),
                new_lifecycle.value,
                now,
                name,
            )
        )
        conn.commit()

        # Return updated record
        updated_row = conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
        return _row_to_record(updated_row)

    finally:
        conn.close()


def get_version_history(name: str) -> list[dict]:
    """
    Get version history for an agent.

    Args:
        name: Agent name

    Returns:
        List of version history entries, newest first
    """
    # Remote API mode
    if is_remote_mode():
        from . import api_client
        return api_client.get_version_history(name)

    # Local SQLite mode
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT version, description, updated_at, manifest_snapshot
            FROM version_history
            WHERE agent_name = ?
            ORDER BY id DESC
            """,
            (name,)
        ).fetchall()

        return [
            {
                "version": row["version"],
                "description": row["description"],
                "updated_at": row["updated_at"],
                "manifest": json.loads(row["manifest_snapshot"]) if row["manifest_snapshot"] else None,
            }
            for row in rows
        ]
    finally:
        conn.close()
