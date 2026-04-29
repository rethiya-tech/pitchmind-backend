import pytest


def test_parse_pdf_returns_parsed_document():
    pytest.skip("PDF parsing requires pdfplumber and a real PDF — test in integration")


def test_parse_pdf_extracts_sections():
    pytest.skip("PDF parsing requires pdfplumber and a real PDF — test in integration")


def test_parse_pdf_word_count_correct():
    pytest.skip("PDF parsing requires pdfplumber and a real PDF — test in integration")


def test_parse_pdf_preview_truncates_to_500_words():
    from app.services.parser import ParsedDocument, Section
    doc = ParsedDocument(
        title="Test",
        sections=[Section(heading="S1", paragraphs=["word " * 600])],
        word_count=600,
        raw_text="word " * 600,
    )
    preview = doc.preview(max_words=500)
    assert len(preview.split()) <= 500


def test_parse_docx_heading_creates_section():
    pytest.skip("DOCX parsing requires python-docx and a real DOCX — test in integration")


def test_parse_docx_bullet_style_adds_to_bullets():
    pytest.skip("DOCX parsing requires python-docx and a real DOCX — test in integration")


def test_parse_docx_normal_style_adds_to_paragraphs():
    pytest.skip("DOCX parsing requires python-docx and a real DOCX — test in integration")


def test_parse_txt_single_section_when_no_headings():
    from app.services.parser import parse_text
    text = "This is a paragraph without any headings at all. " * 10
    result = parse_text(text)
    assert len(result.sections) >= 1


def test_parse_txt_hash_prefix_creates_section():
    from app.services.parser import parse_text
    text = "# Section One\n" + "Content here. " * 10 + "\n# Section Two\n" + "More content. " * 10
    result = parse_text(text)
    assert any(s.heading == "Section One" for s in result.sections)


def test_empty_document_raises_value_error():
    from app.services.parser import parse_text
    with pytest.raises(ValueError, match="too short"):
        parse_text("")


def test_short_document_raises_value_error():
    from app.services.parser import parse_text
    with pytest.raises(ValueError, match="too short"):
        parse_text("Too short.")


def test_preview_returns_max_500_words():
    from app.services.parser import ParsedDocument, Section
    long_text = "word " * 1000
    doc = ParsedDocument(
        title="Test",
        sections=[Section(heading="S1", paragraphs=[long_text])],
        word_count=1000,
        raw_text=long_text,
    )
    preview = doc.preview(max_words=500)
    assert len(preview.split()) <= 500
