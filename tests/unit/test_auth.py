import pytest
from datetime import timedelta


def test_hash_password_returns_hash():
    from app.core.security import hash_password
    result = hash_password("mypassword")
    assert result != "mypassword"
    assert len(result) > 20


def test_verify_correct_password():
    from app.core.security import hash_password, verify_password
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_wrong_password_fails():
    from app.core.security import hash_password, verify_password
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token_contains_user_id():
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"user_id": "abc123", "role": "user", "email": "x@x.com"})
    payload = decode_access_token(token)
    assert payload["user_id"] == "abc123"


def test_create_access_token_contains_role():
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"user_id": "abc123", "role": "admin", "email": "x@x.com"})
    payload = decode_access_token(token)
    assert payload["role"] == "admin"


def test_decode_valid_token_returns_payload():
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"user_id": "test-id", "role": "user", "email": "t@t.com"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["user_id"] == "test-id"


def test_decode_expired_token_returns_none():
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token(
        {"user_id": "test-id", "role": "user", "email": "t@t.com"},
        expires_delta=timedelta(seconds=-1)
    )
    assert decode_access_token(token) is None


def test_decode_invalid_token_returns_none():
    from app.core.security import decode_access_token
    assert decode_access_token("not.a.valid.token") is None


def test_decode_tampered_token_returns_none():
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"user_id": "test-id", "role": "user", "email": "t@t.com"})
    tampered = token[:-5] + "XXXXX"
    assert decode_access_token(tampered) is None
