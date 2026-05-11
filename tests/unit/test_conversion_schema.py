import pytest
from pydantic import ValidationError


def _valid_body(**overrides):
    base = {"upload_id": "00000000-0000-0000-0000-000000000001"}
    return {**base, **overrides}


def test_presentation_flags_defaults_to_empty():
    from app.schemas.conversion import ConversionCreate
    body = ConversionCreate(**_valid_body())
    assert body.presentation_flags == []


def test_presentation_flags_accepts_valid_flags():
    from app.schemas.conversion import ConversionCreate
    body = ConversionCreate(**_valid_body(presentation_flags=["minimal", "roadmap"]))
    assert set(body.presentation_flags) == {"minimal", "roadmap"}


def test_presentation_flags_rejects_unknown_flag():
    from app.schemas.conversion import ConversionCreate
    with pytest.raises(ValidationError) as exc_info:
        ConversionCreate(**_valid_body(presentation_flags=["invalid_flag"]))
    assert "Invalid flags" in str(exc_info.value)


def test_presentation_flags_deduplicates():
    from app.schemas.conversion import ConversionCreate
    body = ConversionCreate(**_valid_body(presentation_flags=["minimal", "minimal", "roadmap"]))
    assert len(body.presentation_flags) == 2
    assert set(body.presentation_flags) == {"minimal", "roadmap"}


def test_presentation_flags_accepts_all_three_valid_values():
    from app.schemas.conversion import ConversionCreate
    body = ConversionCreate(**_valid_body(
        presentation_flags=["minimal", "roadmap", "data_focus"]
    ))
    assert set(body.presentation_flags) == {"minimal", "roadmap", "data_focus"}
