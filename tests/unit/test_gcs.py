import pytest
from unittest.mock import MagicMock, patch


def test_generate_upload_key_includes_user_id():
    from app.services.gcs import generate_upload_key
    key = generate_upload_key(user_id="user-123", filename="doc.pdf")
    assert "user-123" in key


def test_generate_upload_key_includes_filename():
    from app.services.gcs import generate_upload_key
    key = generate_upload_key(user_id="user-123", filename="report.pdf")
    assert "report.pdf" in key


def test_generate_upload_key_includes_uploads_prefix():
    from app.services.gcs import generate_upload_key
    key = generate_upload_key(user_id="user-123", filename="doc.pdf")
    assert key.startswith("uploads/")


def test_generate_pptx_key_includes_conversion_id():
    from app.services.gcs import generate_pptx_key
    key = generate_pptx_key(conversion_id="conv-456")
    assert "conv-456" in key


def test_generate_pptx_key_ends_with_pptx():
    from app.services.gcs import generate_pptx_key
    key = generate_pptx_key(conversion_id="conv-456")
    assert key.endswith(".pptx")


def test_generate_pptx_key_includes_exports_prefix():
    from app.services.gcs import generate_pptx_key
    key = generate_pptx_key(conversion_id="conv-456")
    assert key.startswith("exports/")


def test_get_signed_upload_url_calls_generate_signed_url():
    from app.services.gcs import get_signed_upload_url
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("app.services.gcs.storage.Client", return_value=mock_client):
        url = get_signed_upload_url(bucket="my-bucket", key="uploads/user/file.pdf")

    mock_blob.generate_signed_url.assert_called_once()
    assert url == "https://storage.googleapis.com/signed-url"


def test_get_signed_download_url_calls_generate_signed_url():
    from app.services.gcs import get_signed_download_url
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/dl-url"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("app.services.gcs.storage.Client", return_value=mock_client):
        url = get_signed_download_url(bucket="my-bucket", key="exports/conv.pptx")

    mock_blob.generate_signed_url.assert_called_once()
    assert url == "https://storage.googleapis.com/dl-url"


def test_upload_bytes_calls_upload_from_string():
    from app.services.gcs import upload_bytes
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("app.services.gcs.storage.Client", return_value=mock_client):
        upload_bytes(bucket="my-bucket", key="exports/conv.pptx",
                     data=b"fake-pptx-data",
                     content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")

    mock_blob.upload_from_string.assert_called_once()
