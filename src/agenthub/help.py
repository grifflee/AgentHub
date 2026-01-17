"""
Help utilities for AgentHub CLI.

This module provides template manifests and documentation helpers
to improve the user experience when registering agents.
"""

import webbrowser
from pathlib import Path


# Template manifest with helpful comments for new users
TEMPLATE_MANIFEST = '''# AgentHub Agent Manifest
# This file defines your agent's metadata for registration.
# Learn more: run `agenthub register --docs`

# REQUIRED FIELDS
# ================

# Unique name for your agent (lowercase, hyphens allowed)
# Pattern: must start and end with letter/number, hyphens in between
name: {name}

# Semantic version (major.minor.patch)
version: 1.0.0

# Brief description of what your agent does (max 500 characters)
description: A brief description of what this agent does

# Author name or organization
author: your-name

# OPTIONAL FIELDS
# ================

# Capabilities - what your agent can do
# List the specific tasks or skills your agent provides
capabilities:
  - example-capability-1
  - example-capability-2

# Protocols - how to communicate with your agent
# Valid options: MCP, A2A, custom
protocols:
  - MCP

# Permissions - what resources your agent needs access to
# Common examples: read-files, write-files, network-access, execute-code
permissions:
  - read-files
'''


def get_template_manifest(name: str) -> str:
    """
    Generate a template manifest with the given agent name.
    
    Args:
        name: The name to use for the agent
        
    Returns:
        A formatted YAML manifest string
    """
    return TEMPLATE_MANIFEST.format(name=name)


def get_docs_path() -> Path:
    """Get the path to the HTML documentation file."""
    # docs/ is at the package root level, not in src/agenthub/
    package_dir = Path(__file__).parent.parent.parent
    return package_dir / "docs" / "manifest_format.html"


def open_docs_in_browser() -> bool:
    """
    Open the manifest documentation in the default browser.
    
    Returns:
        True if successful, False otherwise
    """
    docs_path = get_docs_path()
    
    if not docs_path.exists():
        return False
    
    webbrowser.open(f"file://{docs_path.absolute()}")
    return True
