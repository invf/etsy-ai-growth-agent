import base64

import pytest
from cryptography.exceptions import InvalidTag

from app.core.encryption import encrypt, decrypt


def test_roundtrip():
    secret = "etsy-access-token-abc123"
    assert decrypt(encrypt(secret)) == secret


def test_ciphertext_differs_from_plaintext_and_is_nondeterministic():
    secret = "same-input"
    first, second = encrypt(secret), encrypt(secret)
    assert secret not in first
    # Random nonce => same plaintext encrypts differently every time
    assert first != second


def test_tampered_ciphertext_rejected():
    token = encrypt("secret")
    raw = bytearray(base64.b64decode(token))
    raw[-1] ^= 0xFF
    tampered = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(InvalidTag):
        decrypt(tampered)
