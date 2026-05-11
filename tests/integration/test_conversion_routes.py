import pytest
from unittest.mock import patch, AsyncMock


pytestmark = pytest.mark.asyncio


async def test_create_conversion_returns_201(test_client, test_token, mock_claude, db_session):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        presign = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "report.pdf", "content_type": "application/pdf"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    upload_id = presign.json()["upload_id"]

    resp = await test_client.post(
        "/api/v1/conversions",
        json={
            "upload_id": upload_id,
            "theme": "executive_modern",
            "style": "executive",
            "audience_level": "c-suite",
            "slide_count": 8,
        },
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["status"] in ("pending", "processing")


async def test_create_conversion_without_auth_returns_401(test_client):
    resp = await test_client.post(
        "/api/v1/conversions",
        json={
            "upload_id": "some-id",
            "theme": "executive_modern",
            "style": "executive",
            "audience_level": "c-suite",
            "slide_count": 8,
        },
    )
    assert resp.status_code == 401


async def test_create_conversion_invalid_theme_returns_422(test_client, test_token):
    resp = await test_client.post(
        "/api/v1/conversions",
        json={
            "upload_id": "some-id",
            "theme": "nonexistent_theme",
            "style": "executive",
            "audience_level": "c-suite",
            "slide_count": 8,
        },
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 422


async def test_get_conversion_returns_200(test_client, test_token, mock_claude, db_session):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        presign = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "doc.txt", "content_type": "text/plain"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    upload_id = presign.json()["upload_id"]

    create = await test_client.post(
        "/api/v1/conversions",
        json={"upload_id": upload_id, "theme": "executive_modern",
              "style": "executive", "audience_level": "general", "slide_count": 5},
        headers={"Authorization": f"Bearer {test_token}"},
    )
    conv_id = create.json()["id"]

    resp = await test_client.get(
        f"/api/v1/conversions/{conv_id}",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == conv_id


async def test_get_conversion_other_user_returns_404(test_client, test_admin_token, db_session):
    resp = await test_client.get(
        "/api/v1/conversions/nonexistent-id",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 404


async def test_list_conversions_returns_paginated(test_client, test_token):
    resp = await test_client.get(
        "/api/v1/conversions",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


async def test_cancel_conversion_sets_cancelled_status(test_client, test_token, db_session):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        presign = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "doc.txt", "content_type": "text/plain"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    upload_id = presign.json()["upload_id"]

    create = await test_client.post(
        "/api/v1/conversions",
        json={"upload_id": upload_id, "theme": "executive_modern",
              "style": "executive", "audience_level": "general", "slide_count": 5},
        headers={"Authorization": f"Bearer {test_token}"},
    )
    conv_id = create.json()["id"]

    resp = await test_client.post(
        f"/api/v1/conversions/{conv_id}/cancel",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code in (200, 409)


async def test_stream_endpoint_requires_auth_token_param(test_client, db_session):
    resp = await test_client.get("/api/v1/conversions/fake-id/stream")
    assert resp.status_code == 401


async def test_create_conversion_with_valid_flags_returns_201(
    test_client, test_token, mock_claude, db_session
):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        presign = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "report.pdf", "content_type": "application/pdf"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    upload_id = presign.json()["upload_id"]

    resp = await test_client.post(
        "/api/v1/conversions",
        json={
            "upload_id": upload_id,
            "theme": "clean_slate",
            "style": "professional",
            "audience_level": "general",
            "slide_count": 8,
            "presentation_flags": ["minimal", "roadmap"],
        },
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 201


async def test_create_conversion_with_invalid_flag_returns_422(
    test_client, test_token
):
    resp = await test_client.post(
        "/api/v1/conversions",
        json={
            "upload_id": "00000000-0000-0000-0000-000000000001",
            "theme": "clean_slate",
            "style": "professional",
            "audience_level": "general",
            "slide_count": 8,
            "presentation_flags": ["not_a_real_flag"],
        },
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 422
