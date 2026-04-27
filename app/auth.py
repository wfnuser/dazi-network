import base64
from datetime import datetime, timezone
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from fastapi import Request, HTTPException

from app.config import settings


class DIDAuthError(Exception):
    pass


def extract_pubkey_from_did_key(did: str) -> VerifyKey:
    """Extract Ed25519 public key from did:key identifier."""
    if not did.startswith("did:key:z"):
        raise DIDAuthError(f"Invalid did:key format: {did}")

    try:
        import base58

        # Remove "did:key:z" prefix — "z" is multibase base58btc prefix
        encoded = did[len("did:key:z"):]
        decoded = base58.b58decode(encoded)
        # First two bytes are multicodec prefix for ed25519-pub: 0xed 0x01
        if decoded[0:2] != b"\xed\x01":
            raise DIDAuthError("Not an Ed25519 did:key (wrong multicodec prefix)")
        pub_bytes = decoded[2:]
        return VerifyKey(pub_bytes)
    except Exception as e:
        if isinstance(e, DIDAuthError):
            raise
        raise DIDAuthError(f"Failed to decode did:key: {e}") from e


def build_signing_payload(body: str, timestamp: str) -> bytes:
    """Build the canonical payload to sign: timestamp + newline + body."""
    return f"{timestamp}\n{body}".encode()


def verify_did_signature(did: str, signature_b64: str, body: str, timestamp: str) -> bool:
    """Verify Ed25519 signature. Raises DIDAuthError on expired timestamp."""
    # Check timestamp freshness
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise DIDAuthError("Invalid timestamp format")

    now = datetime.now(timezone.utc)
    delta = abs((now - ts).total_seconds())
    if delta > settings.auth_timestamp_tolerance_seconds:
        raise DIDAuthError(
            f"Timestamp expired: {delta:.0f}s old (max {settings.auth_timestamp_tolerance_seconds}s)"
        )

    vk = extract_pubkey_from_did_key(did)
    payload = build_signing_payload(body, timestamp)
    signature = base64.b64decode(signature_b64)

    try:
        vk.verify(payload, signature)
        return True
    except BadSignatureError:
        return False


async def require_did_auth(request: Request) -> str:
    """FastAPI dependency: extract and verify DID auth from headers. Returns the DID."""
    did = request.headers.get("X-DID")
    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")

    if not did or not signature or not timestamp:
        raise HTTPException(
            status_code=401,
            detail={"error": "auth_failed", "message": "Missing X-DID, X-Signature, or X-Timestamp header"},
        )

    body = (await request.body()).decode()

    try:
        valid = verify_did_signature(did, signature, body, timestamp)
    except DIDAuthError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": "auth_failed", "message": str(e)},
        )

    if not valid:
        raise HTTPException(
            status_code=401,
            detail={"error": "auth_failed", "message": "Invalid signature"},
        )

    return did
