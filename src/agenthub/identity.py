"""
Agent identity and lineage management for AgentHub.

This module provides utilities for generating persistent agent IDs
and tracking fork lineage (parent-child relationships).

ID Format: ah:<author>/<name>[+<fork>]
Examples:
    ah:griffen-lee/code-reviewer
    ah:griffen-lee/code-reviewer+security
"""

from typing import Optional


def generate_agent_id(author: str, name: str, fork_name: Optional[str] = None) -> str:
    """
    Generate a persistent agent ID.
    
    Args:
        author: Agent author/organization
        name: Base agent name
        fork_name: Optional fork identifier
        
    Returns:
        Agent ID in format ah:author/name[+fork]
    """
    base = f"ah:{author}/{name}"
    if fork_name:
        return f"{base}+{fork_name}"
    return base


def parse_agent_id(agent_id: str) -> dict:
    """
    Parse an agent ID into its components.
    
    Args:
        agent_id: Full agent ID (e.g., "ah:author/name+fork")
        
    Returns:
        Dict with 'author', 'name', 'fork_name' keys
    """
    if not agent_id.startswith("ah:"):
        raise ValueError(f"Invalid agent ID format: {agent_id}")
    
    # Remove prefix
    rest = agent_id[3:]
    
    # Check for fork
    fork_name = None
    if "+" in rest:
        rest, fork_name = rest.rsplit("+", 1)
    
    # Parse author/name
    if "/" not in rest:
        raise ValueError(f"Invalid agent ID format: {agent_id}")
    
    author, name = rest.split("/", 1)
    
    return {
        "author": author,
        "name": name,
        "fork_name": fork_name
    }


def build_lineage(parent_lineage: list[str], new_agent_id: str) -> list[str]:
    """
    Build the lineage chain for a new forked agent.
    
    Args:
        parent_lineage: Parent's lineage array
        new_agent_id: The new forked agent's ID
        
    Returns:
        New lineage array including the new agent
    """
    return parent_lineage + [new_agent_id]


def format_lineage_tree(lineage: list[str], versions: Optional[dict[str, str]] = None) -> str:
    """
    Format a lineage list as an ASCII tree.
    
    Args:
        lineage: List of agent IDs from original to current
        versions: Optional dict mapping agent_id to version string
        
    Returns:
        Formatted tree string
    """
    if not lineage:
        return "[No lineage data]"
    
    lines = []
    for i, agent_id in enumerate(lineage):
        indent = "  " * i
        prefix = "'-- " if i > 0 else ""
        version_str = f" (v{versions[agent_id]})" if versions and agent_id in versions else ""
        label = " [ORIGINAL]" if i == 0 else ""
        lines.append(f"{indent}{prefix}{agent_id}{version_str}{label}")
    
    return "\n".join(lines)


def get_generation(lineage: list[str]) -> int:
    """
    Get the generation number from a lineage.
    
    Generation is 0 for originals, 1 for first forks, etc.
    """
    return max(0, len(lineage) - 1)
