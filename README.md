# AgentHub

A CLI tool for registering, discovering, and managing AI agents.

## Requirements

- **Python 3.10+** (Python 3.10, 3.11, or 3.12 recommended)
- **pip** (Python package manager)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/AgentHub.git
cd AgentHub
```

### 2. Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows
```

### 3. Install the CLI

```bash
# Install in development/editable mode
pip install -e .

# Or with dev dependencies (for testing)
pip install -e ".[dev]"
```

### 4. Verify Installation

```bash
# Both commands work
agenthub --help
ah --help
```

## Dependencies

These are installed automatically when you run `pip install -e .`:

| Package | Version | Purpose |
|---------|---------|---------|
| click | ≥8.0 | CLI framework |
| rich-click | ≥1.7 | Enhanced CLI styling |
| pyyaml | ≥6.0 | YAML manifest parsing |
| rich | ≥13.0 | Terminal formatting |
| pydantic | ≥2.0 | Data validation |
| requests | ≥2.28 | HTTP client |
| cryptography | ≥41.0 | Agent signing |

## Usage

```bash
# Show all commands
ah --help

# Initialize a new agent manifest
ah init my-agent

# Register an agent
ah publish register examples/sample_agent.yaml

# Browse registered agents
ah browse list
ah browse search --capability "code-review"
ah browse info my-agent

# Rate an agent
ah browse rate my-agent 5

# Manage your identity (for signing)
ah identity create
ah identity show
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

See `examples/` for more manifest examples.

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=agenthub
```

## Troubleshooting

### Command not found after install

Make sure your virtual environment is activated, or reinstall:

```bash
source venv/bin/activate
pip install -e .
```

### Python version errors

Check your Python version:

```bash
python3 --version
```

Must be 3.10 or higher. Install via [python.org](https://python.org) or use pyenv.

## License

MIT
