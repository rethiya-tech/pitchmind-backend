import pytest


pytestmark = pytest.mark.asyncio


async def test_admin_metrics_returns_200(test_client, test_admin_token):
    resp = await test_client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "total_users" in body
    assert "total_conversions" in body


async def test_admin_metrics_non_admin_returns_403(test_client, test_token):
    resp = await test_client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 403


async def test_admin_metrics_unauthenticated_returns_401(test_client):
    resp = await test_client.get("/api/v1/admin/metrics")
    assert resp.status_code == 401


async def test_admin_list_users_returns_paginated(test_client, test_admin_token):
    resp = await test_client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


async def test_admin_list_users_non_admin_returns_403(test_client, test_token):
    resp = await test_client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 403


async def test_admin_list_users_pagination_params(test_client, test_admin_token):
    resp = await test_client.get(
        "/api/v1/admin/users?page=1&page_size=5",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 200


async def test_admin_audit_log_returns_200(test_client, test_admin_token):
    resp = await test_client.get(
        "/api/v1/admin/audit-log",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body


async def test_admin_audit_log_non_admin_returns_403(test_client, test_token):
    resp = await test_client.get(
        "/api/v1/admin/audit-log",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 403


async def test_admin_get_user_by_id_returns_user(
    test_client, test_admin_token, test_user
):
    resp = await test_client.get(
        f"/api/v1/admin/users/{test_user.id}",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == test_user.email


async def test_admin_get_nonexistent_user_returns_404(test_client, test_admin_token):
    resp = await test_client.get(
        "/api/v1/admin/users/nonexistent-uuid",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 404


async def test_admin_suspend_user_updates_is_active(
    test_client, test_admin_token, test_user
):
    resp = await test_client.patch(
        f"/api/v1/admin/users/{test_user.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_admin_cannot_suspend_self(test_client, test_admin_token, test_admin):
    resp = await test_client.patch(
        f"/api/v1/admin/users/{test_admin.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code in (400, 409)
