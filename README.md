# AgentHub

A CLI tool for registering, discovering, and managing AI agents.

## Installation

```bash
# Install in development mode
pip install -e .

# Or install dependencies directly
pip install -e ".[dev]"
```

## Usage

```bash
# Show help
agenthub --help

# Register an agent from a manifest file
agenthub register examples/sample_agent.yaml

# List all registered agents
agenthub list

# Search agents by capability
agenthub search --capability "code-review"

# Get details about a specific agent
agenthub info my-agent

# Mark an agent as deprecated
agenthub deprecate my-agent
```

## Agent Manifest Format

Create a YAML file with this structure:

```yaml
name: my-agent
version: 1.0.0
description: A helpful agent for code review
author: your-name

capabilities:
  - code-review
  - bug-detection
  - style-checking

protocols:
  - MCP

permissions:
  - read-files
  - write-files
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=agenthub
```
