"""
API Client for AgentHub CLI.

This module provides functions to communicate with the AgentHub API server.
Falls back to local SQLite when no API URL is configured.
"""

import os
from typing import Optional
import requests

# Default to local mode if no API URL is set
API_URL = os.environ.get("AGENTHUB_API_URL", "").rstrip("/")


def is_remote_mode() -> bool:
    """Check if we're using the remote API."""
    return bool(API_URL)


def _handle_response(response: requests.Response):
    """Handle API response and raise appropriate errors."""
    if response.status_code >= 400:
        try:
            error = response.json().get("error", response.text)
        except:
            error = response.text
        raise ValueError(error)
    return response.json()


def register_agent(data: dict) -> dict:
    """Register a new agent via the API."""
    response = requests.post(f"{API_URL}/api/agents", json=data)
    return _handle_response(response)


def get_agent(name: str) -> Optional[dict]:
    """Get an agent by name."""
    response = requests.get(f"{API_URL}/api/agents/{name}")
    if response.status_code == 404:
        return None
    return _handle_response(response)


def list_agents(lifecycle_state: Optional[str] = None, limit: int = 100) -> list:
    """List all agents, optionally filtered by state."""
    params = {"limit": limit}
    if lifecycle_state:
        params["state"] = lifecycle_state
    
    response = requests.get(f"{API_URL}/api/agents", params=params)
    return _handle_response(response)


def search_agents(
    capability: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 50
) -> list:
    """Search agents by capability or text query."""
    params = {"limit": limit}
    if capability:
        params["capability"] = capability
    if query:
        params["q"] = query
    
    response = requests.get(f"{API_URL}/api/search", params=params)
    return _handle_response(response)


def update_lifecycle_state(name: str, state: str) -> bool:
    """Update an agent's lifecycle state."""
    response = requests.patch(
        f"{API_URL}/api/agents/{name}",
        json={"lifecycle_state": state}
    )
    return response.status_code == 200


def delete_agent(name: str) -> bool:
    """Delete an agent from the registry."""
    response = requests.delete(f"{API_URL}/api/agents/{name}")
    return response.status_code == 200
