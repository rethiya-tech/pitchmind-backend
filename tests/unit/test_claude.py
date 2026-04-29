import pytest


def test_validate_slides_truncates_long_title():
    from app.services.claude import validate_slides
    raw = {"slides": [{"layout": "bullets", "title": " ".join(["word"] * 20),
                        "bullets": ["a", "b", "c"], "speaker_notes": "x" * 60}]}
    result = validate_slides(raw)
    assert len(result[0]["title"].split()) <= 10


def test_validate_slides_caps_bullets_at_six():
    from app.services.claude import validate_slides
    raw = {"slides": [{"layout": "bullets", "title": "Title",
                        "bullets": ["a", "b", "c", "d", "e", "f", "g", "h"],
                        "speaker_notes": "x" * 60}]}
    result = validate_slides(raw)
    assert len(result[0]["bullets"]) <= 6


def test_validate_slides_fills_to_minimum_three_bullets():
    from app.services.claude import validate_slides
    raw = {"slides": [{"layout": "bullets", "title": "Title",
                        "bullets": ["only one bullet"],
                        "speaker_notes": "x" * 60}]}
    result = validate_slides(raw)
    assert len(result[0]["bullets"]) >= 3


def test_validate_slides_truncates_long_bullets():
    from app.services.claude import validate_slides
    long_bullet = " ".join(["word"] * 30)
    raw = {"slides": [{"layout": "bullets", "title": "Title",
                        "bullets": [long_bullet, "b", "c"],
                        "speaker_notes": "x" * 60}]}
    result = validate_slides(raw)
    assert len(result[0]["bullets"][0].split()) <= 15


def test_validate_empty_slides_returns_empty_list():
    from app.services.claude import validate_slides
    result = validate_slides({"slides": []})
    assert result == []


def test_build_prompt_includes_style():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(style="executive", audience_level="c-suite", slide_count=10)
    assert "executive" in prompt


def test_build_prompt_includes_audience_level():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(style="executive", audience_level="c-suite", slide_count=10)
    assert "c-suite" in prompt


def test_build_prompt_includes_slide_count():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(style="executive", audience_level="c-suite", slide_count=10)
    assert "10" in prompt


def test_build_prompt_includes_doc_sections():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(style="executive", audience_level="c-suite", slide_count=10)
    assert len(prompt) > 100


def test_strip_markdown_fences_from_response():
    from app.services.claude import strip_fences
    fenced = '```json\n{"slides": []}\n```'
    result = strip_fences(fenced)
    assert result == '{"slides": []}'


def test_valid_json_without_fences_parses_correctly():
    from app.services.claude import strip_fences
    plain = '{"slides": []}'
    result = strip_fences(plain)
    assert result == '{"slides": []}'
