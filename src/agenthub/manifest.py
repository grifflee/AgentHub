"""
YAML manifest parsing and validation for AgentHub.

This module handles loading agent manifests from YAML files
and validating them against the schema.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import AgentManifest, AgentRecord, Protocol


def load_manifest(path: Path) -> AgentRecord:
    """
    Load and validate an agent manifest from a YAML file.
    
    Args:
        path: Path to the YAML manifest file
        
    Returns:
        AgentRecord ready for database insertion
        
    Raises:
        FileNotFoundError: If the manifest file doesn't exist
        ValueError: If the manifest is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")
    
    with open(path, 'r') as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")
    
    if not isinstance(data, dict):
        raise ValueError("Manifest must be a YAML dictionary")
    
    # Convert protocol strings to Protocol enum (case-insensitive)
    if 'protocols' in data:
        protocols = []
        for p in data['protocols']:
            try:
                # Normalize to uppercase for matching (MCP, A2A are uppercase enums)
                normalized = p.upper() if isinstance(p, str) else p
                protocols.append(Protocol(normalized))
            except ValueError:
                protocols.append(Protocol.CUSTOM)
        data['protocols'] = protocols
    
    try:
        return AgentRecord(**data)
    except ValidationError as e:
        errors = []
        for error in e.errors():
            field = '.'.join(str(loc) for loc in error['loc'])
            msg = error['msg']
            errors.append(f"  - {field}: {msg}")
        raise ValueError(f"Invalid manifest:\n" + '\n'.join(errors))


def save_manifest(agent: AgentRecord, path: Path) -> None:
    """
    Save an agent manifest to a YAML file.
    
    Args:
        agent: The agent record to save
        path: Path to save the YAML file
    """
    data = {
        'name': agent.name,
        'version': agent.version,
        'description': agent.description,
        'author': agent.author,
        'capabilities': agent.capabilities,
        'protocols': [p.value for p in agent.protocols],
        'permissions': agent.permissions,
    }
    
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
