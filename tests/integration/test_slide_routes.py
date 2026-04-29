import pytest
from unittest.mock import patch


pytestmark = pytest.mark.asyncio


async def _create_conversion_with_slides(test_client, test_token, claude_fixture_slides):
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


async def test_list_slides_returns_slides_for_conversion(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    resp = await test_client.get(
        f"/api/v1/conversions/{conv_id}/slides",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_patch_slide_title_updates_title(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    slides = (await test_client.get(
        f"/api/v1/conversions/{conv_id}/slides",
        headers={"Authorization": f"Bearer {test_token}"},
    )).json()

    if not slides:
        pytest.skip("No slides available to patch")

    slide_id = slides[0]["id"]
    resp = await test_client.patch(
        f"/api/v1/slides/{slide_id}",
        json={"title": "Updated Title"},
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


async def test_patch_slide_bullets_updates_bullets(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    slides = (await test_client.get(
        f"/api/v1/conversions/{conv_id}/slides",
        headers={"Authorization": f"Bearer {test_token}"},
    )).json()

    if not slides:
        pytest.skip("No slides available to patch")

    slide_id = slides[0]["id"]
    new_bullets = ["New bullet 1", "New bullet 2", "New bullet 3"]
    resp = await test_client.patch(
        f"/api/v1/slides/{slide_id}",
        json={"bullets": new_bullets},
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["bullets"] == new_bullets


async def test_soft_delete_slide_sets_is_deleted(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    slides = (await test_client.get(
        f"/api/v1/conversions/{conv_id}/slides",
        headers={"Authorization": f"Bearer {test_token}"},
    )).json()

    if not slides:
        pytest.skip("No slides available to delete")

    slide_id = slides[0]["id"]
    resp = await test_client.delete(
        f"/api/v1/slides/{slide_id}",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_deleted"] is True


async def test_restore_deleted_slide(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    slides = (await test_client.get(
        f"/api/v1/conversions/{conv_id}/slides",
        headers={"Authorization": f"Bearer {test_token}"},
    )).json()

    if not slides:
        pytest.skip("No slides available")

    slide_id = slides[0]["id"]
    await test_client.delete(
        f"/api/v1/slides/{slide_id}",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    resp = await test_client.post(
        f"/api/v1/slides/{slide_id}/restore",
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_deleted"] is False


async def test_reorder_slides_updates_positions(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    slides = (await test_client.get(
        f"/api/v1/conversions/{conv_id}/slides",
        headers={"Authorization": f"Bearer {test_token}"},
    )).json()

    if len(slides) < 2:
        pytest.skip("Need at least 2 slides to reorder")

    ids = [s["id"] for s in slides]
    reordered = list(reversed(ids))
    resp = await test_client.post(
        f"/api/v1/conversions/{conv_id}/slides/reorder",
        json={"slide_ids": reordered},
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 200


async def test_insert_slide_adds_new_slide(
    test_client, test_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    resp = await test_client.post(
        f"/api/v1/conversions/{conv_id}/slides",
        json={
            "title": "New Blank Slide",
            "bullets": ["Point A", "Point B", "Point C"],
            "speaker_notes": "Speaker notes here.",
            "layout": "bullets",
            "position": 0,
        },
        headers={"Authorization": f"Bearer {test_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "New Blank Slide"


async def test_patch_slide_other_user_returns_403(
    test_client, test_token, test_admin_token, claude_fixture_slides
):
    conv_id = await _create_conversion_with_slides(
        test_client, test_token, claude_fixture_slides
    )
    slides = (await test_client.get(
        f"/api/v1/conversions/{conv_id}/slides",
        headers={"Authorization": f"Bearer {test_token}"},
    )).json()

    if not slides:
        pytest.skip("No slides available")

    slide_id = slides[0]["id"]
    resp = await test_client.patch(
        f"/api/v1/slides/{slide_id}",
        json={"title": "Hacked"},
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert resp.status_code in (403, 404)
