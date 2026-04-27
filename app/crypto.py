import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings


def _get_key() -> bytes:
    key_hex = settings.contact_encryption_key
    if not key_hex or len(key_hex) != 64:
        raise ValueError("DAZI_CONTACT_ENCRYPTION_KEY must be a 64-character hex string (32 bytes)")
    return bytes.fromhex(key_hex)


def encrypt_contact(plaintext: str) -> bytes:
    """Encrypt contact value with AES-256-GCM. Returns nonce(12) + ciphertext."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ct


def decrypt_contact(data: bytes) -> str:
    """Decrypt contact value. Input: nonce(12) + ciphertext."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = data[:12]
    ct = data[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()
