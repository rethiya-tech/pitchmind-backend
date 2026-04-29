import pytest


pytestmark = pytest.mark.asyncio


async def test_register_new_user_returns_201(test_client, db_session):
    resp = await test_client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "SecurePass123!",
        "name": "New User",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert "id" in body


async def test_register_duplicate_email_returns_409(test_client, test_user):
    resp = await test_client.post("/api/v1/auth/register", json={
        "email": test_user.email,
        "password": "SecurePass123!",
        "name": "Dupe",
    })
    assert resp.status_code == 409


async def test_register_missing_email_returns_422(test_client):
    resp = await test_client.post("/api/v1/auth/register", json={
        "password": "SecurePass123!",
        "name": "No Email",
    })
    assert resp.status_code == 422


async def test_register_weak_password_returns_422(test_client):
    resp = await test_client.post("/api/v1/auth/register", json={
        "email": "weak@example.com",
        "password": "123",
        "name": "Weak",
    })
    assert resp.status_code == 422


async def test_login_valid_credentials_returns_access_token(test_client, test_user):
    resp = await test_client.post("/api/v1/auth/login", data={
        "username": test_user.email,
        "password": "testpassword",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_sets_refresh_cookie(test_client, test_user):
    resp = await test_client.post("/api/v1/auth/login", data={
        "username": test_user.email,
        "password": "testpassword",
    })
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password_returns_401(test_client, test_user):
    resp = await test_client.post("/api/v1/auth/login", data={
        "username": test_user.email,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(test_client):
    resp = await test_client.post("/api/v1/auth/login", data={
        "username": "nobody@example.com",
        "password": "password123",
    })
    assert resp.status_code == 401


async def test_refresh_with_valid_cookie_returns_new_token(test_client, test_user):
    login = await test_client.post("/api/v1/auth/login", data={
        "username": test_user.email,
        "password": "testpassword",
    })
    assert login.status_code == 200
    resp = await test_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_refresh_without_cookie_returns_401(test_client):
    resp = await test_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_logout_clears_refresh_cookie(test_client, test_user):
    await test_client.post("/api/v1/auth/login", data={
        "username": test_user.email,
        "password": "testpassword",
    })
    resp = await test_client.post("/api/v1/auth/logout")
    assert resp.status_code == 200


async def test_get_me_with_valid_token_returns_user(test_client, test_token, test_user):
    resp = await test_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == test_user.email


async def test_get_me_without_token_returns_401(test_client):
    resp = await test_client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_get_me_with_invalid_token_returns_401(test_client):
    resp = await test_client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401
