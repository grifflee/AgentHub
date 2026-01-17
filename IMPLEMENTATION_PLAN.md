# AgentHub Implementation Plan

> **Single source of truth for all development on AgentHub.**  
> Last updated: 2026-01-17

---

## Project Overview

AgentHub is a **registry for sharing AI agents** — like npm for JavaScript or PyPI for Python, but for autonomous AI agents.

| Requirement | Description |
|------------|-------------|
| Capability Clarity | Machine-readable manifests with capabilities, permissions, protocols |
| Lifecycle Transparency | States: active, deprecated, retired, revoked |
| Ecosystem Interoperability | MCP, A2A protocol support |
| Trust & Security | Signed manifests, provenance attestations |
| Discovery | Find agents by capability |
| Quality Signals | Ratings, downloads, badges |

---

## Architecture

```
AgentHub/
├── src/agenthub/          # CLI package
│   ├── cli.py             # Click-based CLI commands
│   ├── models.py          # Pydantic data models + enums
│   ├── database.py        # SQLite + API client mode
│   ├── manifest.py        # YAML parsing/validation
│   ├── signing.py         # Ed25519 cryptographic signing
│   ├── identity.py        # Agent ID + lineage utilities
│   ├── api_client.py      # HTTP client for remote API
│   └── help.py            # Help utilities
├── server/                # Flask API (optional remote mode)
│   ├── app.py             # REST endpoints
│   └── models.py          # SQLAlchemy models
├── examples/              # Sample manifests
├── docs/                  # HTML documentation
└── .agent/workflows/      # Agent rules (onboarding.md)
```

**Two operating modes:**
- **Local mode** (default): SQLite at `~/.agenthub/registry.db`
- **Remote mode**: Set `AGENTHUB_API_URL` to use hosted server

---

## Phase 1: Core MVP [COMPLETE]

- [x] Agent manifest schema (name, version, capabilities, protocols, permissions)
- [x] CLI commands: `register`, `list`, `info`, `search`, `deprecate`, `remove`
- [x] Local SQLite storage in `~/.agenthub/`
- [x] YAML manifest parsing with Pydantic validation
- [x] Lifecycle states enum

---

## Phase 2: Trust & Provenance [COMPLETE]

Ed25519 client-side cryptographic signing.

- [x] `signing.py` module with keypair generation, signing, verification
- [x] Keys stored in `~/.agenthub/keys/`
- [x] `ah trust keygen` — Generate Ed25519 keypair
- [x] `ah trust sign <manifest>` — Sign manifest in-place
- [x] `ah trust verify <manifest>` — Verify signature
- [x] `ah trust status` — Show key configuration
- [x] Signature fields in manifest: `signature`, `public_key`, `signed_at`

---

## Phase 2.5: SLSA Attestations [SCHEMA ONLY]

Attestation schema added, verification not implemented.

- [x] `AttestationType` enum (build, test, security, review, registry)
- [x] `Attestation` model with verifier, statement, signature
- [x] `attestations: list[Attestation]` field in manifest
- [ ] CLI command to add attestations
- [ ] Attestation signature verification
- [ ] CI/CD integration examples

---

## Phase 3: Backend Server [COMPLETE]

Flask REST API for shared registry.

- [x] `server/app.py` with REST endpoints
- [x] SQLAlchemy models in `server/models.py`
- [x] `database.py` routes to API when `AGENTHUB_API_URL` is set
- [x] Local fallback preserved

---

## Phase 4: UX Improvements [COMPLETE]

- [x] `ah init <name>` — Generate template manifest
- [x] `ah example-manifest` — Show example inline
- [x] `ah register --docs` — Open HTML docs in browser
- [x] Helpful prompts when `register` called without args
- [x] `ah` alias for `agenthub` command
- [x] Commands grouped: `ah trust` subcommand group

---

## Phase 5: Quality, Permissions & Identity [PARTIAL]

- [x] `ExecutionLevel` enum (SAFE, STANDARD, ELEVATED, SYSTEM)
- [x] `calculate_execution_level()` function
- [x] Quality signal fields: `download_count`, `rating_sum`, `rating_count`, `badges`
- [x] Documentation fields: `documentation_url`, `homepage`, `repository`
- [x] Lineage fields: `agent_id`, `parent_id`, `generation`, `lineage`, `fork_name`
- [x] `identity.py` module with ID generation and lineage utilities
- [x] `ah fork <agent> --name <fork>` — Fork with lineage
- [x] `ah rate <agent> <1-5>` — Rate command (simplified)
- [x] `ah lineage <agent>` — Show ancestry tree
- [ ] **Download receipt verification for ratings** (on docket)
- [x] Persist ratings to database
- [ ] Auto-compute "popular" badge at >10 downloads
- [ ] Display execution level in `ah info` output

---

## Phase 6: Governance [NOT STARTED]

- [ ] `SubmissionMode` enum (open, curated)
- [ ] `ReviewStatus` enum (pending, approved, rejected)
- [ ] Review fields: `submission_mode`, `review_status`, `reviewed_by`
- [ ] `ah pending` — List agents awaiting review
- [ ] `ah approve <name>` — Approve agent
- [ ] `ah reject <name> --reason "..."` — Reject with feedback

---

## Phase 7: Extended Metadata [NOT STARTED]

- [ ] Add fields: `license`, `tags`, `keywords`
- [ ] Inter-agent dependencies: `dependencies`, `conflicts`, `suggests`
- [ ] Search by tags/keywords
- [ ] Dependency resolution warnings

---

## Backlog / Future Ideas

- [ ] Download receipt signing for verified ratings
- [ ] Automated tests with pytest
- [ ] GitHub Actions for CI/CD attestations
- [ ] Multi-sig for high-value agents
- [ ] Web UI for browsing agents
- [ ] Agent Card (like Hugging Face model cards)

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Signing Algorithm | Ed25519 | Fast, small keys, modern |
| Key Storage | Client-side only | No server custody |
| ID Format | `ah:author/name[+fork]` | Clear lineage in ID |
| CLI Alias | `ah` | Faster typing |
| UI Style | No emojis, Rich colors | User preference |
| Popular Badge | >10 downloads | Low bar for testing |
| Rating Gate | Download receipt | Prevent spam |

---

## Testing

No automated tests. Manual testing:

```bash
cd /Users/griffenlee/Desktop/AgentHub
pip install -e .
ah --help
ah list
ah trust status
ah fork code-reviewer --name test
ah rate code-reviewer 5
```
