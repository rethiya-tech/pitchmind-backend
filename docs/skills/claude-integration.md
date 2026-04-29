# Claude Integration Skill

## Model
Always: claude-sonnet-4

## System prompt (use exactly)
```
You are a professional presentation generator. Convert the provided
document into a structured slide deck.

OUTPUT FORMAT: Respond with ONLY valid JSON. No markdown fences,
no explanation. Start with { and end with }.

JSON schema:
{
  "slides": [
    {
      "layout": "hero|bullets|two_column|data_table",
      "title": "string — maximum 10 words",
      "bullets": ["string — maximum 15 words each"],
      "speaker_notes": "string — 50 to 150 words"
    }
  ]
}

RULES:
1. First slide MUST be hero layout (presentation title)
2. Second slide MUST be bullets layout (agenda)
3. Title: strictly maximum 10 words
4. Bullets: minimum 3, maximum 6 per slide
5. Each bullet: maximum 15 words
6. Speaker notes: 50-150 words
7. Style: {STYLE}
8. Audience: {AUDIENCE_LEVEL}
9. Total slides: approximately {SLIDE_COUNT}
```

## Calling Claude
```python
system = SYSTEM_PROMPT.format(
    STYLE=settings.style,
    AUDIENCE_LEVEL=settings.audience_level,
    SLIDE_COUNT=settings.slide_count)
result, tokens = await call_claude(system, doc_text)
```

## Validation after parse
```python
def validate_slides(raw: dict) -> list[dict]:
    slides = raw.get("slides", [])
    out = []
    for s in slides:
        title = " ".join(s.get("title","").split()[:10])
        bullets = [" ".join(b.split()[:15]) for b in s.get("bullets",[])][:6]
        while len(bullets) < 3:
            bullets.append("Key point")
        out.append({
            "layout": s.get("layout","bullets"),
            "title": title,
            "bullets": bullets,
            "speaker_notes": (s.get("speaker_notes",""))[:800]
        })
    return out
```

## Cost tracking
After call: conversion.tokens_used += input_tokens + output_tokens
Admin metrics: SUM(tokens_used) * 0.000003 = cost in USD
