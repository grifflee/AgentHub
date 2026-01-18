"""
Cryptographic signing for AgentHub manifests.

This module provides Ed25519 signing and verification for agent manifests,
enabling trust and provenance verification as described in the AgentHub paper (§3.2.5).

Usage:
    # Generate keypair (one-time setup)
    from agenthub.signing import generate_keypair, save_keypair
    private_key, public_key = generate_keypair()
    save_keypair(private_key, public_key)
    
    # Sign a manifest
    from agenthub.signing import sign_manifest_file
    sign_manifest_file(Path("my-agent.yaml"))
    
    # Verify a signature
    from agenthub.signing import verify_manifest_file
    is_valid = verify_manifest_file(Path("my-agent.yaml"))
"""

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import yaml

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    Ed25519PrivateKey = None
    Ed25519PublicKey = None


def get_agenthub_dir() -> Path:
    """Get the AgentHub config directory (~/.agenthub)."""
    agenthub_dir = Path.home() / ".agenthub"
    agenthub_dir.mkdir(exist_ok=True)
    return agenthub_dir


def get_keys_dir() -> Path:
    """Get the keys directory (~/.agenthub/keys)."""
    keys_dir = get_agenthub_dir() / "keys"
    keys_dir.mkdir(exist_ok=True)
    return keys_dir


def check_cryptography_available() -> None:
    """Raise an error if cryptography library is not installed."""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError(
            "The 'cryptography' library is required for signing.\n"
            "Install it with: pip install cryptography>=41.0"
        )


# =============================================================================
# Key Generation
# =============================================================================

def generate_keypair() -> Tuple[bytes, bytes]:
    """
    Generate a new Ed25519 keypair.
    
    Returns:
        Tuple of (private_key_pem, public_key_pem) as bytes
    """
    check_cryptography_available()
    
    # Generate private key
    private_key = Ed25519PrivateKey.generate()
    
    # Serialize private key to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Get public key and serialize
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem, public_pem


def save_keypair(private_pem: bytes, public_pem: bytes) -> Path:
    """
    Save a keypair to ~/.agenthub/keys/.
    
    Args:
        private_pem: Private key in PEM format
        public_pem: Public key in PEM format
        
    Returns:
        Path to keys directory
    """
    keys_dir = get_keys_dir()
    
    private_path = keys_dir / "private.pem"
    public_path = keys_dir / "public.pem"
    
    # Write private key with restricted permissions
    private_path.write_bytes(private_pem)
    private_path.chmod(0o600)  # Read/write for owner only
    
    # Write public key
    public_path.write_bytes(public_pem)
    
    return keys_dir


def load_private_key() -> "Ed25519PrivateKey":
    """Load the private key from ~/.agenthub/keys/private.pem."""
    check_cryptography_available()
    
    private_path = get_keys_dir() / "private.pem"
    
    if not private_path.exists():
        raise FileNotFoundError(
            f"Private key not found at {private_path}\n"
            "Run 'agenthub keygen' to generate a keypair."
        )
    
    private_pem = private_path.read_bytes()
    return serialization.load_pem_private_key(private_pem, password=None)


def load_public_key() -> "Ed25519PublicKey":
    """Load the public key from ~/.agenthub/keys/public.pem."""
    check_cryptography_available()
    
    public_path = get_keys_dir() / "public.pem"
    
    if not public_path.exists():
        raise FileNotFoundError(
            f"Public key not found at {public_path}\n"
            "Run 'agenthub keygen' to generate a keypair."
        )
    
    public_pem = public_path.read_bytes()
    return serialization.load_pem_public_key(public_pem)


def has_keypair() -> bool:
    """Check if a keypair exists."""
    keys_dir = get_keys_dir()
    return (keys_dir / "private.pem").exists() and (keys_dir / "public.pem").exists()


# =============================================================================
# Signing
# =============================================================================

def get_signable_content(manifest_data: dict) -> str:
    """
    Get the canonical content to sign from a manifest.
    
    Excludes signature-related fields to allow verification after signing.
    Uses JSON for deterministic serialization.
    
    Args:
        manifest_data: Parsed manifest dictionary
        
    Returns:
        Canonical string representation for signing
    """
    # Fields to exclude from signature (they're added after signing)
    exclude_fields = {"signature", "public_key", "signed_at"}
    
    # Create a copy without signature fields
    signable = {k: v for k, v in manifest_data.items() if k not in exclude_fields}
    
    # Use JSON with sorted keys for deterministic output
    return json.dumps(signable, sort_keys=True, default=str)


def sign_content(content: str, private_key: "Ed25519PrivateKey") -> str:
    """
    Sign content with a private key.
    
    Args:
        content: String content to sign
        private_key: Ed25519 private key
        
    Returns:
        Base64-encoded signature
    """
    signature_bytes = private_key.sign(content.encode("utf-8"))
    return base64.b64encode(signature_bytes).decode("ascii")


def get_public_key_base64(public_key: "Ed25519PublicKey") -> str:
    """Get the base64-encoded raw public key bytes."""
    raw_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return base64.b64encode(raw_bytes).decode("ascii")


def sign_manifest_file(manifest_path: Path) -> dict:
    """
    Sign a manifest file in-place.
    
    Adds signature, public_key, and signed_at fields to the manifest.
    
    Args:
        manifest_path: Path to the YAML manifest file
        
    Returns:
        The updated manifest data
    """
    check_cryptography_available()
    
    # Load the manifest
    with open(manifest_path, "r") as f:
        manifest_data = yaml.safe_load(f)
    
    # Load keys
    private_key = load_private_key()
    public_key = private_key.public_key()
    
    # Get content to sign (excluding existing signature fields)
    signable_content = get_signable_content(manifest_data)
    
    # Sign the content
    signature = sign_content(signable_content, private_key)
    
    # Add signature fields to manifest
    manifest_data["signature"] = signature
    manifest_data["public_key"] = get_public_key_base64(public_key)
    manifest_data["signed_at"] = datetime.now(timezone.utc).isoformat()
    
    # Write back to file
    with open(manifest_path, "w") as f:
        yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
    
    return manifest_data


# =============================================================================
# Verification
# =============================================================================

def verify_signature(content: str, signature_b64: str, public_key_b64: str) -> bool:
    """
    Verify a signature against content.
    
    Args:
        content: The original signed content
        signature_b64: Base64-encoded signature
        public_key_b64: Base64-encoded raw public key
        
    Returns:
        True if valid, False otherwise
    """
    check_cryptography_available()
    
    try:
        # Decode signature and public key
        signature_bytes = base64.b64decode(signature_b64)
        public_key_bytes = base64.b64decode(public_key_b64)
        
        # Reconstruct public key from raw bytes
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        
        # Verify (raises InvalidSignature on failure)
        public_key.verify(signature_bytes, content.encode("utf-8"))
        return True
        
    except Exception:
        return False


def verify_manifest_file(manifest_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Verify a signed manifest file.
    
    Args:
        manifest_path: Path to the YAML manifest file
        
    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, "reason")
    """
    # Load the manifest
    with open(manifest_path, "r") as f:
        manifest_data = yaml.safe_load(f)
    
    # Check for signature fields
    signature = manifest_data.get("signature")
    public_key = manifest_data.get("public_key")
    
    if not signature:
        return False, "Manifest is not signed (no signature field)"
    
    if not public_key:
        return False, "Manifest is missing public_key field"
    
    # Get the content that was signed
    signable_content = get_signable_content(manifest_data)
    
    # Verify
    if verify_signature(signable_content, signature, public_key):
        return True, None
    else:
        return False, "Signature verification failed - manifest may have been tampered with"


def verify_manifest_data(manifest_data: dict) -> Tuple[bool, Optional[str]]:
    """
    Verify a manifest from a dictionary (already parsed).
    
    Args:
        manifest_data: Parsed manifest dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    signature = manifest_data.get("signature")
    public_key = manifest_data.get("public_key")
    
    if not signature:
        return False, "Manifest is not signed"
    
    if not public_key:
        return False, "Missing public key"
    
    signable_content = get_signable_content(manifest_data)
    
    if verify_signature(signable_content, signature, public_key):
        return True, None
    else:
        return False, "Invalid signature"


# =============================================================================
# Attestation Signing & Verification
# =============================================================================

def get_attestation_signable_content(attestation_data: dict) -> str:
    """
    Get the canonical content to sign for an attestation.
    
    Excludes signature field to allow verification after signing.
    
    Args:
        attestation_data: Attestation dictionary
        
    Returns:
        Canonical string representation for signing
    """
    # Fields to exclude from signature
    exclude_fields = {"signature", "public_key"}
    
    # Create a copy without signature fields
    signable = {k: v for k, v in attestation_data.items() if k not in exclude_fields}
    
    # Use JSON with sorted keys for deterministic output
    return json.dumps(signable, sort_keys=True, default=str)


def sign_attestation(
    attestation_type: str,
    verifier: str,
    statement: str,
    verifier_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> dict:
    """
    Create and sign a new attestation.
    
    Args:
        attestation_type: Type of attestation (build, test, security, review, registry)
        verifier: Name of entity creating the attestation
        statement: Human-readable statement of what was verified
        verifier_id: Optional URI or identifier for the verifier
        metadata: Optional additional metadata
        
    Returns:
        Signed attestation dictionary ready to add to manifest
    """
    check_cryptography_available()
    
    # Load keys
    private_key = load_private_key()
    public_key = private_key.public_key()
    
    # Build attestation
    attestation = {
        "type": attestation_type,
        "verifier": verifier,
        "statement": statement,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if verifier_id:
        attestation["verifier_id"] = verifier_id
    
    if metadata:
        attestation["metadata"] = metadata
    
    # Get content to sign
    signable_content = get_attestation_signable_content(attestation)
    
    # Sign
    attestation["signature"] = sign_content(signable_content, private_key)
    attestation["public_key"] = get_public_key_base64(public_key)
    
    return attestation


def verify_attestation(attestation_data: dict) -> Tuple[bool, Optional[str]]:
    """
    Verify a single attestation's signature.
    
    Args:
        attestation_data: Attestation dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    signature = attestation_data.get("signature")
    public_key = attestation_data.get("public_key")
    
    if not signature:
        return False, "Attestation is not signed"
    
    if not public_key:
        return False, "Attestation missing public_key"
    
    signable_content = get_attestation_signable_content(attestation_data)
    
    if verify_signature(signable_content, signature, public_key):
        return True, None
    else:
        return False, "Attestation signature invalid"


def add_attestation_to_manifest(manifest_path: Path, attestation: dict) -> dict:
    """
    Add a signed attestation to a manifest file.
    
    Args:
        manifest_path: Path to the YAML manifest file
        attestation: Signed attestation dictionary
        
    Returns:
        Updated manifest data
    """
    # Load the manifest
    with open(manifest_path, "r") as f:
        manifest_data = yaml.safe_load(f)
    
    # Initialize attestations list if not present
    if "attestations" not in manifest_data:
        manifest_data["attestations"] = []
    
    # Add the attestation
    manifest_data["attestations"].append(attestation)
    
    # Write back to file
    with open(manifest_path, "w") as f:
        yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
    
    return manifest_data


def verify_all_attestations(manifest_data: dict) -> list[Tuple[int, bool, Optional[str]]]:
    """
    Verify all attestations in a manifest.

    Args:
        manifest_data: Parsed manifest dictionary

    Returns:
        List of (index, is_valid, error_message) tuples for each attestation
    """
    attestations = manifest_data.get("attestations", [])
    results = []

    for i, attestation in enumerate(attestations):
        is_valid, error = verify_attestation(attestation)
        results.append((i, is_valid, error))

    return results


# =============================================================================
# Trusted Verifier Registry
# =============================================================================

def get_trusted_verifiers_path() -> Path:
    """Get the path to the trusted verifiers config file."""
    return get_agenthub_dir() / "trusted-verifiers.yaml"


def load_trusted_verifiers() -> dict[str, dict]:
    """
    Load trusted verifiers from config file.

    Returns:
        Dictionary of verifier_name -> {public_key, added_at, description}
    """
    path = get_trusted_verifiers_path()

    if not path.exists():
        return {}

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    return data.get("verifiers", {})


def save_trusted_verifiers(verifiers: dict) -> None:
    """
    Save trusted verifiers to config file.

    Args:
        verifiers: Dictionary of verifier_name -> {public_key, added_at, description}
    """
    path = get_trusted_verifiers_path()

    data = {"verifiers": verifiers}

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def add_trusted_verifier(name: str, public_key: str, description: str = "") -> None:
    """
    Add a trusted verifier to the registry.

    Args:
        name: Unique name for the verifier (e.g., "github-actions")
        public_key: Base64-encoded public key
        description: Optional description of the verifier
    """
    verifiers = load_trusted_verifiers()

    verifiers[name] = {
        "public_key": public_key,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "description": description,
    }

    save_trusted_verifiers(verifiers)


def remove_trusted_verifier(name: str) -> bool:
    """
    Remove a trusted verifier from the registry.

    Args:
        name: Name of the verifier to remove

    Returns:
        True if removed, False if not found
    """
    verifiers = load_trusted_verifiers()

    if name not in verifiers:
        return False

    del verifiers[name]
    save_trusted_verifiers(verifiers)
    return True


def is_trusted_verifier(verifier_name: str, public_key: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a verifier is in the trusted registry.

    Args:
        verifier_name: Name of the verifier
        public_key: Base64-encoded public key from the attestation

    Returns:
        Tuple of (is_trusted, matched_name)
        If trusted: (True, "name-in-registry")
        If not trusted: (False, None)
    """
    verifiers = load_trusted_verifiers()

    # First check if the verifier name matches
    if verifier_name in verifiers:
        if verifiers[verifier_name]["public_key"] == public_key:
            return True, verifier_name

    # Also check if any verifier has this public key (name may differ)
    for name, data in verifiers.items():
        if data["public_key"] == public_key:
            return True, name

    return False, None


def verify_attestation_trusted(attestation_data: dict) -> Tuple[bool, Optional[str], bool, Optional[str]]:
    """
    Verify attestation signature AND check if signer is trusted.

    Args:
        attestation_data: Attestation dictionary

    Returns:
        Tuple of (is_valid, error_message, is_trusted, trusted_verifier_name)
        - is_valid: True if signature is cryptographically valid
        - error_message: Error description if invalid, None otherwise
        - is_trusted: True if verifier is in trusted registry
        - trusted_verifier_name: Name of matched trusted verifier, or None
    """
    # First verify cryptographic signature
    is_valid, error = verify_attestation(attestation_data)

    if not is_valid:
        return False, error, False, None

    # Check if verifier is trusted
    verifier_name = attestation_data.get("verifier", "")
    public_key = attestation_data.get("public_key", "")

    is_trusted, matched_name = is_trusted_verifier(verifier_name, public_key)

    return True, None, is_trusted, matched_name


def verify_all_attestations_trusted(manifest_data: dict) -> list[Tuple[int, bool, Optional[str], bool, Optional[str]]]:
    """
    Verify all attestations in a manifest with trust status.

    Args:
        manifest_data: Parsed manifest dictionary

    Returns:
        List of (index, is_valid, error_message, is_trusted, trusted_name) tuples
    """
    attestations = manifest_data.get("attestations", [])
    results = []

    for i, attestation in enumerate(attestations):
        is_valid, error, is_trusted, trusted_name = verify_attestation_trusted(attestation)
        results.append((i, is_valid, error, is_trusted, trusted_name))

    return results
