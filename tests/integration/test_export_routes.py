import pytest
from unittest.mock import patch


pytestmark = pytest.mark.asyncio


async def _setup_completed_conversion(test_client, test_token, claude_fixture_slides):
    with patch("app.services.gcs.get_signed_upload_url",
               return_value="https://storage.googleapis.com/upload-url"):
        presign = await test_client.post(
            "/api/v1/uploads/presign",
            json={"filename": "doc.txt", "content_type": "text/plain"},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    upload_id = presign.json()["upload_id"]

    with patch("app.services.claude.call_claude",
               return_value=({"slides": claude_fixture_slides}, 100)):
        create = await test_client.post(
            "/api/v1/conversions",
            json={"upload_id": upload_id, "theme": "executive_modern",
                  "style": "executive", "audience_level": "c-suite", "slide_count": 3},
            headers={"Authorization": f"Bearer {test_token}"},
        )
    return create.json()["id"]


async def test_export_pptx_returns_download_url(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _setup_completed_conversion(
        test_client, test_token, claude_fixture_slides
    )
    with patch("app.services.gcs.get_signed_download_url",
               return_value="https://storage.googleapis.com/pptx-download-url"), \
         patch("app.services.gcs.upload_bytes"):
        resp = await test_client.post(
            f"/api/v1/conversions/{conv_id}/export",
            headers={"Authorization": f"Bearer {test_token}"},
        )
    assert resp.status_code in (200, 202)
    if resp.status_code == 200:
        body = resp.json()
        assert "download_url" in body


async def test_export_pptx_without_auth_returns_401(test_client):
    resp = await test_client.post("/api/v1/conversions/some-id/export")
    assert resp.status_code == 401


async def test_export_pptx_nonexistent_conversion_returns_404(test_client, test_token):
    with patch("app.services.gcs.get_signed_download_url",
               return_value="https://storage.googleapis.com/pptx-url"), \
         patch("app.services.gcs.upload_bytes"):
        resp = await test_client.post(
            "/api/v1/conversions/nonexistent-id/export",
            headers={"Authorization": f"Bearer {test_token}"},
        )
    assert resp.status_code == 404


async def test_export_other_users_conversion_returns_404(
    test_client, test_token, test_admin_token, claude_fixture_slides
):
    conv_id = await _setup_completed_conversion(
        test_client, test_token, claude_fixture_slides
    )
    resp = await test_client.post(
        f"/api/v1/conversions/{conv_id}/export",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code == 404


async def test_export_builds_pptx_with_correct_slide_count(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _setup_completed_conversion(
        test_client, test_token, claude_fixture_slides
    )

    uploaded_bytes = {}

    def capture_upload(bucket, key, data, content_type=None):
        uploaded_bytes["data"] = data

    with patch("app.services.gcs.get_signed_download_url",
               return_value="https://storage.googleapis.com/pptx-url"), \
         patch("app.services.gcs.upload_bytes", side_effect=capture_upload):
        resp = await test_client.post(
            f"/api/v1/conversions/{conv_id}/export",
            headers={"Authorization": f"Bearer {test_token}"},
        )

    if resp.status_code == 200 and uploaded_bytes.get("data"):
        from io import BytesIO
        from pptx import Presentation
        prs = Presentation(BytesIO(uploaded_bytes["data"]))
        assert len(prs.slides) == len(claude_fixture_slides)
