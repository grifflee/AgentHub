"""
Data models for AgentHub using Pydantic for validation.

This module defines the core data structures that represent agents
in the registry, closely following the AgentHub paper's specifications.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LifecycleState(str, Enum):
    """
    Lifecycle states for agents as defined in the AgentHub paper (§3.2.2).
    
    Lifecycle transparency is essential for safe reuse and governance.
    """
    ACTIVE = "active"           # Agent is maintained and safe to use
    DEPRECATED = "deprecated"   # Agent works but is being phased out
    RETIRED = "retired"         # Agent no longer maintained
    REVOKED = "revoked"         # Agent removed for security/policy reasons


class Protocol(str, Enum):
    """
    Supported agent protocols for interoperability (§3.2.3).
    
    MCP = Model Context Protocol (agent -> tools)
    A2A = Agent-to-Agent protocol (agent -> agent)
    """
    MCP = "MCP"
    A2A = "A2A"
    CUSTOM = "custom"


class AgentManifest(BaseModel):
    """
    The core agent manifest schema.
    
    Based on AgentHub paper's requirements for:
    - Capability clarity (§3.2.1): capabilities, permissions
    - Lifecycle transparency (§3.2.2): lifecycle_state
    - Ecosystem interoperability (§3.2.3): protocols
    """
    
    # Identity
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        pattern=r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$',
        description="Unique agent name (lowercase, hyphens allowed)"
    )
    version: str = Field(
        ..., 
        pattern=r'^\d+\.\d+\.\d+$',
        description="Semantic version (e.g., 1.0.0)"
    )
    description: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="Brief description of what the agent does"
    )
    author: str = Field(
        ..., 
        min_length=1,
        description="Agent author or organization"
    )
    
    # Capability & Evidence (§3.2.1)
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of capabilities this agent provides"
    )
    protocols: list[Protocol] = Field(
        default_factory=list,
        description="Supported protocols (MCP, A2A, etc.)"
    )
    permissions: list[str] = Field(
        default_factory=list,
        description="Required permissions (read-files, network-access, etc.)"
    )
    
    # Lifecycle (§3.2.2)
    lifecycle_state: LifecycleState = Field(
        default=LifecycleState.ACTIVE,
        description="Current lifecycle state"
    )
    
    # Metadata
    created_at: Optional[datetime] = Field(
        default=None,
        description="When the agent was first registered"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="When the agent was last updated"
    )


class AgentRecord(AgentManifest):
    """
    Extended agent record stored in the database.
    
    Includes additional fields for registry management.
    """
    id: Optional[int] = Field(default=None, description="Database ID")
    
    class Config:
        from_attributes = True  # Allow ORM mode
