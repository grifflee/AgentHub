# AgentHub Master Implementation Plan

> **Consolidated from multiple planning sessions. This is the single source of truth for all agents working on this project.**
>
> Last updated: 2026-01-17

---

## Project Overview

AgentHub is a **registry for sharing AI agents** — similar to npm for JavaScript or PyPI for Python, but designed for autonomous AI agents. Key requirements from the research papers:

| Requirement | Description |
|------------|-------------|
| **Capability Clarity** | Machine-readable manifests declaring capabilities, permissions, protocols |
| **Lifecycle Transparency** | States like active/deprecated/retired |
| **Ecosystem Interoperability** | Support for MCP, A2A, and other protocols |
| **Trust & Security** | Cryptographically signed manifests |
| **Discovery** | Find agents by capability, not just keywords |
| **Quality Signals** | Ratings, downloads, badges |

---

## Current Architecture

```
AgentHub/
├── src/agenthub/          # CLI package
│   ├── cli.py             # Click-based CLI
│   ├── models.py          # Pydantic data models
│   ├── database.py        # SQLite + API client mode
│   ├── manifest.py        # YAML parsing/validation
│   ├── api_client.py      # HTTP client for remote API
│   └── help.py            # Help utilities
├── server/                # Flask API (optional remote mode)
│   ├── app.py             # REST endpoints
│   └── models.py          # SQLAlchemy models
├── examples/              # Sample manifests
└── docs/                  # HTML documentation
```

**Two operating modes:**
- **Local mode** (default): SQLite at `~/.agenthub/registry.db`
- **Remote mode**: Set `AGENTHUB_API_URL` to use shared server

---

## ✅ Completed Features

### Core MVP (Done)
- [x] Agent manifest schema (name, version, capabilities, protocols, permissions)
- [x] CLI commands: `register`, `list`, `info`, `deprecate`, `remove`
- [x] Local SQLite storage
- [x] YAML manifest parsing with validation
- [x] Lifecycle states (active, deprecated, retired, revoked)

### UX Improvements (Done)
- [x] `agenthub init <name>` — Generate template manifest
- [x] `agenthub example-manifest` — Show example inline
- [x] `agenthub register --docs` — Open HTML documentation
- [x] Helpful prompts when running `register` without arguments
- [x] Available commands shown after `list`

### Backend Server (Done)
- [x] Flask REST API (`server/app.py`)
- [x] SQLAlchemy models with PostgreSQL support
- [x] CLI can talk to remote API via `AGENTHUB_API_URL`
- [x] Local mode fallback preserved

---

## 🚧 Planned Features (Not Yet Implemented)

### Phase 1: Metadata & Dependencies

Add richer metadata and inter-agent dependency tracking.

**New fields in `models.py`:**
```python
# Extended Metadata
homepage: Optional[str]          # Project URL
repository: Optional[str]        # Source code URL
license: Optional[str]           # SPDX license identifier
tags: list[str]                  # Searchable tags

# Dependencies
dependencies: list[str]          # Required agents (e.g., ["text-analyzer>=1.0"])
conflicts: list[str]             # Incompatible agents
suggests: list[str]              # Optional recommended agents
```

**Files to modify:** `models.py`, `manifest.py`, `database.py`, `server/models.py`

---

### Phase 2: Trust & Provenance (Ed25519 Signing)

Cryptographic signing for manifest authenticity.

**Key Management (Client-Side Signing):**
```
~/.agenthub/
├── keys/
│   ├── private.pem    # NEVER leaves user's machine
│   └── public.pem     # Embedded in signed manifests
└── registry.db
```

**New commands:**
- `agenthub keygen` — Generate Ed25519 keypair
- `agenthub sign <manifest.yaml>` — Sign manifest in-place
- `agenthub verify <manifest.yaml>` — Verify signature

**New fields:**
```python
signature: Optional[str]         # Base64-encoded Ed25519 signature
public_key: Optional[str]        # Author's public key
signed_at: Optional[datetime]    # When signed
```

**New file:** `src/agenthub/signing.py`  
**New dependency:** `cryptography>=41.0`

---

### Phase 2.5: SLSA-Style Attestations (Schema Added ✅)

Third-party attestations for verifiable evidence about agents.

**Already added to `models.py`:**
```python
class AttestationType(Enum):
    BUILD = "build"       # How agent was built
    TEST = "test"         # Tests passed
    SECURITY = "security" # Security scan results
    REVIEW = "review"     # Code review attestation
    REGISTRY = "registry" # Registry admission check
    CUSTOM = "custom"

class Attestation(BaseModel):
    type: AttestationType
    verifier: str              # Who created this (e.g., "github-actions")
    verifier_id: Optional[str] # URI for verifier
    statement: str             # What was verified
    timestamp: Optional[datetime]
    signature: Optional[str]   # Verifier's signature
    public_key: Optional[str]  # Verifier's public key
    metadata: Optional[dict]   # Extra data (commit hash, etc.)

# In AgentManifest:
attestations: list[Attestation] = []
```

**Future work (not implemented yet):**
- CLI command to add attestations
- Verification of attestation signatures
- CI/CD integration for automated attestations

---

### Phase 3: Governance & Lifecycle

Support open vs. curated submission models.

**New enums and fields:**
```python
class SubmissionMode(Enum):
    OPEN = "open"          # Anyone can register
    CURATED = "curated"    # Requires approval

class ReviewStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# New fields:
submission_mode: SubmissionMode
review_status: Optional[ReviewStatus]
reviewed_by: Optional[str]
review_notes: Optional[str]
```

**New commands:**
- `agenthub pending` — List agents awaiting review
- `agenthub approve <name>` — Approve an agent
- `agenthub reject <name> --reason "..."` — Reject with feedback

**New file:** `src/agenthub/governance.py`

---

### Phase 4: Quality Signals

Ratings, downloads, and badges.

**New fields:**
```python
download_count: int = 0
rating_sum: int = 0
rating_count: int = 0
badges: list[str] = []  # ["verified", "popular", "official"]
```

**New commands:**
- `agenthub rate <name> <1-5>` — Rate an agent
- Updated `list`/`info` to show ⭐ ratings and 📥 downloads

**New file:** `src/agenthub/ratings.py`

---

## Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.10+ |
| CLI Framework | Click + rich-click |
| Data Validation | Pydantic |
| Local Database | SQLite |
| Server Framework | Flask |
| Server Database | PostgreSQL (SQLite for dev) |
| Signing | Ed25519 via `cryptography` |

---

## Verification Approach

No automated tests exist yet. Verification is manual:

```bash
# Install in dev mode
cd /Users/griffenlee/Desktop/AgentHub
pip install -e .

# Test CLI
agenthub --help
agenthub init test-agent
agenthub register test-agent.yaml
agenthub list
agenthub info test-agent
```

---

## Notes for Agents

1. **This file is the master plan** — update it when making significant changes
2. **Local mode must always work** — don't break offline functionality
3. **Keep CLI UX consistent** — use rich panels and tables
4. **Phase order matters** — Phase 1 schema changes are foundational
5. **Client-side signing chosen** — private keys stay on user machines
