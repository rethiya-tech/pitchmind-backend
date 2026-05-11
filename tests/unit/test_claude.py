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


def test_build_prompt_no_flags_has_no_format_overrides():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(style="professional", audience_level="general", slide_count=10)
    assert "FORMAT OVERRIDES" not in prompt


def test_build_prompt_minimal_flag_injects_instruction():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(
        style="professional", audience_level="general", slide_count=10,
        presentation_flags=["minimal"]
    )
    assert "FORMAT OVERRIDES" in prompt
    assert "Max 3 bullets per slide" in prompt


def test_build_prompt_roadmap_flag_injects_instruction():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(
        style="professional", audience_level="general", slide_count=10,
        presentation_flags=["roadmap"]
    )
    assert "FORMAT OVERRIDES" in prompt
    assert "timeline" in prompt.lower()


def test_build_prompt_data_focus_flag_injects_instruction():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(
        style="professional", audience_level="general", slide_count=10,
        presentation_flags=["data_focus"]
    )
    assert "FORMAT OVERRIDES" in prompt
    assert "big_stat" in prompt


def test_build_prompt_multiple_flags_injects_all_instructions():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(
        style="professional", audience_level="general", slide_count=10,
        presentation_flags=["minimal", "roadmap", "data_focus"]
    )
    assert "Max 3 bullets per slide" in prompt
    assert "timeline" in prompt.lower()
    assert "big_stat" in prompt


def test_build_prompt_empty_flags_has_no_format_overrides():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(
        style="professional", audience_level="general", slide_count=10,
        presentation_flags=[]
    )
    assert "FORMAT OVERRIDES" not in prompt


def test_build_prompt_unknown_flag_is_silently_ignored():
    from app.services.claude import build_system_prompt
    prompt = build_system_prompt(
        style="professional", audience_level="general", slide_count=10,
        presentation_flags=["not_a_real_flag"]
    )
    assert "FORMAT OVERRIDES" not in prompt
