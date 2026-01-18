# AgentHub Implementation Plan

> **Single source of truth for all development on AgentHub.**
> Last updated: 2026-01-18 (Phase 2.6 Trusted Verifier Registry complete)

---

## Project Overview

AgentHub is a **registry for sharing AI agents** — like npm for JavaScript or PyPI for Python, but for autonomous AI agents.

| Requirement | Description |
|------------|-------------|
| Capability Clarity | Machine-readable manifests with capabilities, permissions, protocols |
| Evidence & Verification | Behavioral testing, not just self-description |
| Lifecycle Transparency | States: active, deprecated, retired, revoked with timestamps |
| Ecosystem Interoperability | MCP, A2A protocol support, cross-registry linking |
| Openness & Governance | Hybrid model: open submissions with vetting for high-risk agents |
| Trust & Security | Signed manifests, SLSA attestations, zero-trust model |
| Discovery | Two-stage: search-based retrieval + agent interviewing |
| Quality Signals | Ratings, downloads, badges, evidence freshness |

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
│   ├── help.py            # Help utilities
│   ├── discovery.py       # Search infrastructure (Phase 8)
│   ├── interviewer.py     # LLM-based agent evaluation (Phase 8)
│   └── evidence.py        # Evidence pipelines (Phase 9)
├── server/                # Flask API (optional remote mode)
│   ├── app.py             # REST endpoints
│   └── models.py          # SQLAlchemy models
├── examples/              # Sample manifests
├── docs/                  # HTML documentation
├── .agent/workflows/      # Agent rules (onboarding.md)
└── .cursor/rules/         # Cursor agent onboarding rules
```

**Two operating modes:**
- **Local mode** (default): SQLite at `~/.agenthub/registry.db`
- **Remote mode**: Set `AGENTHUB_API_URL` to use hosted server

---

## Implementation Order & Dependencies

**Recommended sequence:**
1. **Phases 1-5** (Core, Trust, Server, UX, Quality) - Can be done immediately
2. **Phase 6** (Governance) - Can be done without server
3. **Phase 7** (Extended Metadata) - Can be done without server
4. **Phase 9** (Evidence & Verification) - Can be done without server
5. **Phase 10** (Interoperability) - Can be done without server
6. **Phase 11** (Security Hardening) - Can be done without server
7. **Phase 8** (Discovery & Recommendation) - **Requires server with local LLM**

**Why Phase 8 last:**
- Requires cloud server infrastructure
- Needs local model deployment (Ollama/vLLM)
- Can build Stage 1 (search) without LLM, but Stage 2 (interviewer) needs model
- Other phases provide foundation (evidence, badges) that enhance discovery

**While waiting for server:**
- Build Stage 1 search infrastructure (BM25 + semantic embeddings)
- Mock Stage 2 interviewer for testing
- Work on other phases that don't require server

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

## Phase 2.5: SLSA Attestations [COMPLETE]

SLSA-style attestations for verifiable evidence about agents.

- [x] `AttestationType` enum (build, test, security, review, registry)
- [x] `Attestation` model with verifier, statement, signature
- [x] `attestations: list[Attestation]` field in manifest
- [x] `ah trust attest <manifest>` — Add signed attestation to manifest
- [x] `ah trust verify-attestations <manifest>` — Verify all attestations
- [x] `sign_attestation()` and `verify_attestation()` functions in signing.py
- [x] CI/CD integration example: `examples/github-actions-attestation.yaml`

---

## Phase 2.6: Trusted Verifier Registry [COMPLETE]

**Problem:** Currently, attestations prove WHO made a claim, but not that the signer is a TRUSTED verifier. A malicious author could sign their own "tests passed" attestation.

**Solution:** A registry of known, trusted verifier public keys. Verification checks if the attestation's `public_key` belongs to a recognized verifier.

### Two Approaches to GitHub Actions Verification

| Aspect | Approach 1: Your Own Key | Approach 2: Sigstore/OIDC |
|--------|--------------------------|---------------------------|
| Setup | Store keypair in GitHub Secrets | Keyless! Uses GitHub's OIDC |
| Key management | You manage private key | No private key needed |
| Trust anchor | Your public key | GitHub's OIDC identity |
| Verification | Check against your key | Query Sigstore/Rekor |
| Auditability | Manual | Built-in transparency log |
| Status | ✅ Example exists | ❌ Not implemented |

### Approach 1: Author's Keypair in GitHub Secrets (Current)

Already implemented in `examples/github-actions-attestation.yaml`:

```yaml
# Author stores THEIR private key in GitHub Secrets
- name: Set up signing keys
  run: |
    echo "${{ secrets.AGENTHUB_PRIVATE_KEY }}" > ~/.agenthub/keys/private.pem

# GitHub Actions signs with author's key
- name: Add test attestation
  run: |
    ah trust attest my-agent.yaml --type test --statement "Tests passed" --verifier "github-actions"
```

**Trust model:** Users trust the AUTHOR's public key. GitHub just runs the tests.

### Approach 2: Sigstore/Fulcio Keyless Signing (Production-Grade)

GitHub's native Artifact Attestations use **Sigstore** for keyless signing via OIDC tokens:

```yaml
# No private key needed! GitHub's OIDC proves identity
- name: Attest Build Provenance
  uses: actions/attest-build-provenance@v1
  with:
    subject-path: 'dist/*'
```

**How it works:**
1. GitHub generates an OIDC token proving: "This is workflow X in repo Y"
2. Sigstore's Fulcio CA issues a short-lived certificate for that identity
3. Attestation is signed with ephemeral key, recorded in Rekor transparency log
4. Verifiers check Rekor: "Did GitHub Actions really produce this?"

**OIDC Identity format:**
```
https://github.com/owner/repo/.github/workflows/ci.yml@refs/heads/main
```

### Conceptual Implementation: Trusted Verifier Registry

```python
# signing.py - Trusted verifier registry
TRUSTED_VERIFIERS = {
    # Verifier name → expected public key (base64)
    "github-actions": "base64-encoded-github-public-key",
    "gitlab-ci": "base64-encoded-gitlab-key",
    "security-auditor-xyz": "base64-encoded-auditor-key",
    "agenthub-registry": "base64-encoded-registry-key",
}

def verify_attestation_trusted(attestation: dict) -> Tuple[bool, Optional[str], bool]:
    """
    Verify attestation signature AND check if signer is trusted.
    
    Returns:
        (is_valid, error_message, is_trusted_verifier)
    """
    # First, verify cryptographic signature
    is_valid, error = verify_attestation(attestation)
    if not is_valid:
        return False, error, False
    
    # Check if verifier is in trusted registry
    verifier = attestation.get("verifier")
    public_key = attestation.get("public_key")
    
    if verifier in TRUSTED_VERIFIERS:
        expected_key = TRUSTED_VERIFIERS[verifier]
        if public_key == expected_key:
            return True, None, True  # Trusted verifier
        else:
            return True, "Signature valid but key doesn't match known verifier", False
    
    return True, None, False  # Valid but unknown verifier
```

### Conceptual Implementation: Sigstore Verification

```python
# signing.py - Sigstore/GitHub OIDC verification
def verify_github_oidc_attestation(attestation: dict) -> Tuple[bool, Optional[str]]:
    """
    Verify attestation signed by GitHub Actions using Sigstore.
    
    Checks:
    1. Signature is valid in Sigstore
    2. OIDC identity matches expected repo/workflow
    3. Entry exists in Rekor transparency log
    """
    from sigstore.verify import Verifier
    from sigstore.verify.policy import Identity
    
    oidc_identity = attestation.get("oidc_identity")
    # e.g., "https://github.com/owner/repo/.github/workflows/ci.yml@refs/heads/main"
    
    signature = attestation.get("sigstore_signature")
    certificate = attestation.get("sigstore_certificate")
    
    verifier = Verifier.production()
    
    # Verify the signature came from the claimed GitHub workflow
    identity = Identity(
        identity=oidc_identity,
        issuer="https://token.actions.githubusercontent.com"
    )
    
    try:
        verifier.verify(
            input_=attestation["statement"].encode(),
            signature=base64.b64decode(signature),
            certificate=certificate,
            identity=identity
        )
        return True, None
    except Exception as e:
        return False, f"Sigstore verification failed: {e}"
```

### Tasks: Basic Trusted Verifiers

- [x] Trusted verifier registry in `~/.agenthub/trusted-verifiers.yaml`
- [x] `verify_attestation_trusted()` function in `signing.py`
- [x] `ah trust verify-attestations --strict` flag (fail if verifier not trusted)
- [x] Display trust level in output: "✓ Valid (Trusted: github-actions)" vs "✓ Valid (Unknown verifier)"
- [x] CLI command: `ah trust add-verifier <name> <public-key> -d "description"`
- [x] CLI command: `ah trust list-verifiers`
- [x] CLI command: `ah trust remove-verifier <name>`

### Tasks: Sigstore/GitHub OIDC Integration

- [ ] Add `sigstore` Python library as optional dependency
- [ ] New attestation fields: `oidc_identity`, `sigstore_signature`, `sigstore_certificate`
- [ ] `verify_github_oidc_attestation()` function
- [ ] `ah trust attest --sigstore` flag for keyless signing
- [ ] `ah trust verify-attestations --check-rekor` flag to query transparency log
- [ ] GitHub Actions example using `actions/attest-build-provenance@v1`
- [ ] Map GitHub's SLSA provenance format to AgentHub attestation schema

### Tasks: Key Distribution & Transparency

- [ ] Fetch trusted keys from AgentHub server
- [ ] Certificate transparency log for verifier key changes
- [ ] Rekor log verification for Sigstore attestations

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
- [x] Auto-compute "popular" badge at >10 downloads
- [x] Display execution level in `ah info` output

### Agent Update & Version History [COMPLETE]

- [x] `version_history` table for tracking previous versions
- [x] `bump_version()` utility (major/minor/patch increments)
- [x] `update_agent()` database function with history preservation
- [x] `get_version_history()` to retrieve version history
- [x] `ah publish update <name> --bump patch` — Auto-increment version
- [x] `ah publish update <name> --manifest <file>` — Update from manifest
- [x] `ah publish update <name> -m <file> -b minor` — Combined update
- [x] `ah publish history <name>` — View version history

---

## Phase 6: Governance [NOT STARTED]

Hybrid governance model: open submissions with vetting for high-risk agents.

- [ ] `SubmissionMode` enum (open, curated)
- [ ] `ReviewStatus` enum (pending, approved, rejected)
- [ ] Review fields: `submission_mode`, `review_status`, `reviewed_by`
- [ ] `ah pending` — List agents awaiting review
- [ ] `ah approve <name>` — Approve agent
- [ ] `ah reject <name> --reason "..."` — Reject with feedback
- [ ] Auditable logs of publication/revocation decisions
- [ ] Community-driven policy for dispute resolution

---

## Phase 7: Extended Metadata [NOT STARTED]

- [ ] Add fields: `license`, `tags`, `keywords`
- [ ] Inter-agent dependencies: `dependencies`, `conflicts`, `suggests`
- [ ] Search by tags/keywords
- [ ] Dependency resolution warnings

---

## Phase 8: Discovery & Recommendation [NOT STARTED]

**⚠️ Implementation Priority: LAST**  
This phase requires server infrastructure with local LLM deployment. Implement after other phases are complete, or when cloud server access is available.

Two-stage discovery pipeline based on research paper methodology.

### Stage 1: Search-Based Retrieval
- [ ] `discovery.py` module for search infrastructure
- [ ] BM25 lexical search on agent metadata
- [ ] Semantic search using embeddings (text-embedding-ada-002 or local model)
- [ ] Hybrid scoring: `α * Semantic + (1-α) * BM25` (default α=0.5)
- [ ] `ah browse search --query "..."` — Hybrid search by capability description

### Stage 2: Agent Interviewer
- [ ] `interviewer.py` module for LLM-based agent evaluation
- [ ] Structured interview prompt requesting:
  - Task Understanding
  - Relevant Capabilities
  - Proposed Approach
  - Micro-Demonstration (behavioral evidence)
  - Limitations (self-reported)
- [ ] LLM-as-Judge scoring rubric:
  | Criterion | Weight |
  |-----------|--------|
  | Understanding | 0.15 |
  | Capabilities | 0.15 |
  | Approach | 0.20 |
  | Micro-Demo | 0.40 |
  | Limitations | 0.10 |
- [ ] `ah browse interview <agent> --task "..."` — Interview single agent
- [ ] `ah browse recommend --task "..."` — Full pipeline: search → interview → rank

### Metrics & Evaluation
- [ ] Precision@1 tracking
- [ ] Recall@3 tracking
- [ ] Latency monitoring
- [ ] Benchmark dataset for discovery evaluation

### Deployment Requirements

**Server Infrastructure:**
- Cloud server with CPU/GPU access (required for Stage 2 interviewer)
- Local model deployment (no API credits needed)

**Model Deployment Options:**
1. **Ollama** (easiest):
   ```bash
   # On server
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull llama3.1:8b  # or qwen2.5:7b
   ollama serve  # Runs on port 11434
   ```

2. **vLLM** (faster inference):
   ```bash
   pip install vllm
   python -m vllm.entrypoints.openai.api_server \
     --model meta-llama/Llama-3.1-8B-Instruct
   ```

**Architecture:**
- Stage 1 (Search) can run on any server (lightweight, no LLM needed)
- Stage 2 (Interviewer) requires local LLM on server
- Flask API (`server/app.py`) calls local model via `localhost`
- Users' CLI commands hit server, model runs server-side

**Development Alternatives (while waiting for server):**
- Mock interviewer with dummy scores for testing
- Build Stage 1 search infrastructure first (no LLM needed)
- Work on other phases (evidence, badges, etc.)

---

## Phase 9: Evidence & Verification [NOT STARTED]

Move beyond self-description to behavioral verification.

### Evidence Pipelines
- [ ] `evidence.py` module for evidence management
- [ ] Evidence record schema linking claims to traces/benchmark runs
- [ ] Re-executable (idempotent) evidence pipelines
- [ ] `ah trust add-evidence <agent> --type benchmark --url "..."`
- [ ] Evidence freshness tracking (stale evidence warnings)

### Behavioral Testing
- [ ] Micro-task execution framework
- [ ] Sandbox environment for agent capability testing
- [ ] `ah trust test <agent> --task "..."` — Run behavioral verification
- [ ] Store test results as attestations

### Badges System
- [ ] `verified` badge — Passes behavioral tests
- [ ] `popular` badge — >10 downloads (existing)
- [ ] `security-audited` badge — Has security attestation
- [ ] `well-documented` badge — Documentation completeness score
- [ ] Auto-compute badges based on evidence

---

## Phase 10: Interoperability [NOT STARTED]

Cross-ecosystem portability and protocol support.

### Protocol Adapters
- [ ] A2A AgentCard import/export
- [ ] MCP tool descriptor mapping
- [ ] Protocol extensions field in manifest

### Cross-Registry Integration
- [ ] Purl-style identifiers for external references
- [ ] Links to npm/PyPI dependencies
- [ ] Links to HuggingFace models
- [ ] `external_refs` field: `[{type: "pypi", name: "langchain", version: "0.1.0"}]`

### AIBOM Support
- [ ] AI Bill of Materials schema (SPDX 3.0 compatible)
- [ ] Model provenance tracking
- [ ] Dataset lineage
- [ ] `ah export-aibom <agent>` — Generate AIBOM

### ANS Integration (Future)
- [ ] Agent Name Service compatibility
- [ ] DNS-style resolution: `agent.example.com` → AgentHub entry
- [ ] Certificate-based agent authentication

---

## Phase 11: Security Hardening [NOT STARTED]

Zero-trust security model for autonomous agent ecosystems.

### Runtime Security
- [ ] Permission enforcement at runtime
- [ ] I/O behavior validation
- [ ] Privilege separation for high-risk operations
- [ ] Tool squatting detection

### Attack Mitigation
- [ ] Typosquatting detection (name similarity scoring)
- [ ] Prompt injection defense patterns
- [ ] Account compromise detection
- [ ] Malicious update detection (behavioral drift)

### Privacy Protection
- [ ] Data handling declarations in manifest
- [ ] Privacy-preserving audit pipelines
- [ ] Sensitive data leak detection

---

## Backlog / Future Ideas

- [ ] Download receipt signing for verified ratings
- [ ] Automated tests with pytest
- [ ] GitHub Actions for CI/CD attestations
- [ ] Multi-sig for high-value agents
- [ ] Web UI for browsing agents
- [ ] Agent Card (like Hugging Face model cards)
- [ ] Federated registry mirrors
- [ ] Decentralized governance experiments
- [ ] Agent-make-agent pattern support
- [ ] Real-time agent health monitoring

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
| Discovery | Two-stage (search → interview) | Balance speed with accuracy |
| Search Ranking | Hybrid (BM25 + semantic) | Best of lexical + meaning |
| Interview Weight | Micro-demo = 40% | Behavioral evidence > claims |
| Evidence Model | Re-executable pipelines | Verifiable, not just stated |
| Security Model | Zero-trust | Agents are untrusted by default |
| LLM Deployment | Local model on server (Ollama/vLLM) | No API costs, full control |

---

## Research Foundation

This project is informed by academic research on agent registries:

| Paper | Focus | Key Concepts |
|-------|-------|--------------|
| `2ndagentpaper` | Discovery & Recommendation | Two-stage ranking, Agent Interviewer, LLM-as-Judge |
| `agenthubdetails` | Research Agenda | Capability clarity, lifecycle transparency, governance |

See `/Users/griffenlee/Desktop/AgentHub/2ndagentpaper` and `agenthubdetails` for full papers.

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

# Version update testing
ah publish update my-agent --bump patch
ah publish update my-agent --manifest updated-agent.yaml
ah publish history my-agent
```
