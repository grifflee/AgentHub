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


class AttestationType(str, Enum):
    """
    Types of attestations for SLSA-style provenance (§3.2.5).
    
    Based on SLSA v1.1 Verification Summary Attestation (VSA) concepts.
    These provide structured, signed evidence of checks performed on agents.
    """
    BUILD = "build"              # Attestation about how agent was built
    TEST = "test"                # Attestation that tests passed
    SECURITY_SCAN = "security"   # Attestation from security scanner
    CODE_REVIEW = "review"       # Attestation from human/automated review
    REGISTRY_CHECK = "registry"  # Attestation from registry admission
    CUSTOM = "custom"            # Custom attestation type


class Attestation(BaseModel):
    """
    A single attestation providing verifiable evidence about an agent.
    
    SLSA-style attestations enable third-party verification of claims.
    Each attestation is signed by its verifier (CI system, auditor, etc.)
    
    Example:
        Attestation(
            type=AttestationType.TEST,
            verifier="github-actions",
            verifier_id="https://github.com/griffen-lee/.github-actions",
            statement="All 47 tests passed on commit abc123",
            timestamp="2026-01-17T10:00:00Z",
            signature="base64-signature...",
            public_key="base64-verifier-public-key..."
        )
    """
    type: AttestationType = Field(
        ...,
        description="Type of attestation"
    )
    verifier: str = Field(
        ...,
        description="Name of entity that created this attestation (e.g., 'github-actions', 'snyk')"
    )
    verifier_id: Optional[str] = Field(
        default=None,
        description="URI or identifier for the verifier"
    )
    statement: str = Field(
        ...,
        description="Human-readable statement of what was verified"
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="When the attestation was created"
    )
    signature: Optional[str] = Field(
        default=None,
        description="Base64-encoded signature from the verifier (optional until signing is implemented)"
    )
    public_key: Optional[str] = Field(
        default=None,
        description="Base64-encoded public key of the verifier"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Additional metadata (commit hash, test count, etc.)"
    )


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
    
    # Trust & Provenance (§3.2.5)
    # Basic author signing (Phase 2)
    signature: Optional[str] = Field(
        default=None,
        description="Base64-encoded Ed25519 signature of manifest content"
    )
    public_key: Optional[str] = Field(
        default=None,
        description="Base64-encoded Ed25519 public key of the author"
    )
    signed_at: Optional[datetime] = Field(
        default=None,
        description="When the manifest was signed"
    )
    
    # SLSA-style attestations (Phase 2.5 - schema only for now)
    attestations: list[Attestation] = Field(
        default_factory=list,
        description="List of third-party attestations (build, test, security, etc.)"
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
