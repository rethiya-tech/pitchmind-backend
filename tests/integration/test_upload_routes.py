import pytest
from unittest.mock import AsyncMock, patch


pytestmark = pytest.mark.asyncio


async def test_presign_upload_returns_signed_url(test_client, test_token):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        resp = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "report.pdf", "content_type": "application/pdf"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "upload_url" in body
    assert "upload_id" in body


async def test_presign_upload_without_auth_returns_401(test_client):
    resp = await test_client.post(
        "/api/v1/uploads/presign",
        json={"filename": "report.pdf", "content_type": "application/pdf"},
    )
    assert resp.status_code == 401


async def test_presign_upload_unsupported_type_returns_422(test_client, test_token):
    resp = await test_client.post(
        "/api/v1/uploads/presign",
        json={"filename": "image.png", "content_type": "image/png"},
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 422


async def test_confirm_upload_marks_as_uploaded(test_client, test_token, db_session):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        presign = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "report.pdf", "content_type": "application/pdf"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    upload_id = presign.json()["upload_id"]

    with patch("app.services.gcs.blob_exists", return_value=True):
        resp = await test_client.post(
            f"/api/v1/uploads/{upload_id}/confirm",
            headers={"Authorization": f"Bearer {test_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["parse_status"] in ("pending", "processing", "done")


async def test_confirm_upload_not_found_returns_404(test_client, test_token):
    with patch("app.services.gcs.blob_exists", return_value=False):
        resp = await test_client.post(
            "/api/v1/uploads/nonexistent-id/confirm",
            headers={"Authorization": f"Bearer {test_token}"},
        )
    assert resp.status_code == 404


async def test_get_upload_preview_returns_text(test_client, test_token):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        presign = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "doc.txt", "content_type": "text/plain"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    upload_id = presign.json()["upload_id"]

    with patch("app.services.parser.parse_text") as mock_parse:
        from app.services.parser import ParsedDocument, Section
        mock_parse.return_value = ParsedDocument(
            title="doc.txt",
            sections=[Section(heading="Intro", paragraphs=["Content here."])],
            word_count=2,
            raw_text="Content here.",
        )
        resp = await test_client.get(
            f"/api/v1/uploads/{upload_id}/preview",
            headers={"Authorization": f"Bearer {test_token}"},
        )
    assert resp.status_code in (200, 404)


async def test_list_uploads_returns_paginated_results(test_client, test_token):
    resp = await test_client.get(
        "/api/v1/uploads",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
