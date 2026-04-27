import base64
import pytest
from nacl.signing import SigningKey
import base58
from app.auth import (
    extract_pubkey_from_did_key,
    verify_did_signature,
    build_signing_payload,
    DIDAuthError,
)


def make_keypair():
    """Generate Ed25519 keypair and did:key."""
    sk = SigningKey.generate()
    vk = sk.verify_key
    pub_bytes = bytes(vk)
    # ed25519-pub multicodec prefix: 0xed 0x01
    prefixed = b"\xed\x01" + pub_bytes
    encoded = base58.b58encode(prefixed).decode()
    did = f"did:key:z{encoded}"
    return sk, vk, did


class TestExtractPubkey:
    def test_valid_did_key(self):
        _sk, vk, did = make_keypair()
        extracted = extract_pubkey_from_did_key(did)
        assert bytes(extracted) == bytes(vk)

    def test_invalid_prefix(self):
        with pytest.raises(DIDAuthError, match="Invalid did:key"):
            extract_pubkey_from_did_key("did:web:example.com")

    def test_malformed(self):
        with pytest.raises(DIDAuthError):
            extract_pubkey_from_did_key("not-a-did")


class TestBuildSigningPayload:
    def test_payload_format(self):
        body = '{"hello": "world"}'
        ts = "2026-04-27T12:00:00Z"
        payload = build_signing_payload(body, ts)
        assert payload == f"{ts}\n{body}".encode()

    def test_empty_body(self):
        ts = "2026-04-27T12:00:00Z"
        payload = build_signing_payload("", ts)
        assert payload == f"{ts}\n".encode()


class TestVerifySignature:
    def test_valid_signature(self):
        from datetime import datetime, timezone

        sk, vk, did = make_keypair()
        body = '{"intent": "find dazi"}'
        ts = datetime.now(timezone.utc).isoformat()
        payload = build_signing_payload(body, ts)
        signature = sk.sign(payload).signature
        sig_b64 = base64.b64encode(signature).decode()

        assert verify_did_signature(did, sig_b64, body, ts) is True

    def test_wrong_signature(self):
        from datetime import datetime, timezone

        _sk, _vk, did = make_keypair()
        body = '{"intent": "find dazi"}'
        ts = datetime.now(timezone.utc).isoformat()
        fake_sig = base64.b64encode(b"\x00" * 64).decode()

        assert verify_did_signature(did, fake_sig, body, ts) is False

    def test_tampered_body(self):
        from datetime import datetime, timezone

        sk, _vk, did = make_keypair()
        body = '{"intent": "find dazi"}'
        ts = datetime.now(timezone.utc).isoformat()
        payload = build_signing_payload(body, ts)
        signature = sk.sign(payload).signature
        sig_b64 = base64.b64encode(signature).decode()

        tampered = '{"intent": "hack"}'
        assert verify_did_signature(did, sig_b64, tampered, ts) is False
