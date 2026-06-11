from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("TestPass123!")
    assert hashed != "TestPass123!"
    assert verify_password("TestPass123!", hashed)
    assert not verify_password("WrongPass123!", hashed)


def test_access_token_roundtrip():
    token, expires = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token, expires = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"


def test_decode_invalid_token_returns_empty():
    assert decode_token("not-a-jwt") == {}


def test_hash_token_is_deterministic_sha256():
    assert hash_token("abc") == hash_token("abc")
    assert len(hash_token("abc")) == 64
