"""AES-256-GCM encryption for Etsy OAuth tokens.

Wire format: base64( nonce[12] + ciphertext + tag[16] ).
Key: ETSY_TOKEN_ENCRYPTION_KEY — 64 hex chars (32 bytes).
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_SIZE = 12


def _key() -> bytes:
    key = bytes.fromhex(settings.ETSY_TOKEN_ENCRYPTION_KEY)
    if len(key) != 32:
        raise ValueError("ETSY_TOKEN_ENCRYPTION_KEY must be 64 hex chars (32 bytes)")
    return key


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(token: str) -> str:
    raw = base64.b64decode(token)
    nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    plaintext = AESGCM(_key()).decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
