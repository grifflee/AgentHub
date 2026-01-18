# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentHub is a CLI registry for AI agents—like npm for JavaScript, but for autonomous AI agents. It supports registration, discovery, signing, and lifecycle management of agents through YAML manifests.

## Build & Development Commands

```bash
# Install in development mode
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=agenthub

# Manual testing (no automated tests yet)
ah --help
ah list
ah trust status
```

## Architecture

**Two operating modes:**
- **Local mode** (default): SQLite at `~/.agenthub/registry.db`
- **Remote mode**: Set `AGENTHUB_API_URL` environment variable to use hosted server

**Key modules in `src/agenthub/`:**
- `cli.py` - Click-based CLI commands (use `rich-click`)
- `models.py` - Pydantic data models and enums
- `database.py` - SQLite storage + API client mode routing
- `manifest.py` - YAML parsing and validation
- `signing.py` - Ed25519 cryptographic signing
- `identity.py` - Agent ID generation and lineage utilities
- `api_client.py` - HTTP client for remote API

**Server (`server/`):**
- `app.py` - Flask REST endpoints
- `models.py` - SQLAlchemy models

## CLI Entry Points

Both `agenthub` and `ah` commands are registered (prefer `ah` for brevity).

## Design Decisions (Must Follow)

| Decision | Details |
|----------|---------|
| Signing | Ed25519 client-side only, keys in `~/.agenthub/keys/` |
| ID Format | `ah:author/name[+fork]` for lineage tracking |
| UI Style | No emojis, use Rich color tags (theme: `#45c1ff`) |
| Output | Use `Panel()` for command output |
| Models | Pydantic v2 for all data validation |

## Documentation Requirement

Every feature must be documented in `IMPLEMENTATION_PLAN.md`. This is the single source of truth for project state. Check it before implementing anything and update it after completing work.

## Current Implementation Status

Completed: Core MVP, Trust & Provenance (Ed25519 signing), SLSA Attestations, Backend Server, UX Improvements, Quality/Permissions/Identity (partial)

Not started: Trusted Verifier Registry, Governance, Extended Metadata, Discovery & Recommendation, Evidence & Verification, Interoperability, Security Hardening

See `IMPLEMENTATION_PLAN.md` for full details.
