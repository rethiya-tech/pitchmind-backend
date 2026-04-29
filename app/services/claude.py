import json
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

SYSTEM_PROMPT_TEMPLATE = """\
You are a professional presentation generator. Convert the provided document into a structured slide deck.

OUTPUT FORMAT: Respond with ONLY valid JSON. No markdown fences, no explanation. Start with {{ and end with }}.

JSON schema:
{{
  "slides": [
    {{
      "layout": "hero|bullets|two_column|data_table",
      "title": "string — maximum 10 words",
      "bullets": ["string — maximum 15 words each"],
      "speaker_notes": "string — 50 to 150 words"
    }}
  ]
}}

RULES:
1. First slide MUST be hero layout (presentation title)
2. Second slide MUST be bullets layout (agenda)
3. Title: strictly maximum 10 words
4. Bullets: minimum 3, maximum 6 per slide
5. Each bullet: maximum 15 words
6. Speaker notes: 50-150 words
7. Style: {STYLE}
8. Audience: {AUDIENCE_LEVEL}
9. Total slides: approximately {SLIDE_COUNT}\
"""


def build_system_prompt(style: str, audience_level: str, slide_count: int) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        STYLE=style,
        AUDIENCE_LEVEL=audience_level,
        SLIDE_COUNT=slide_count,
    )


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


def validate_slides(raw: dict) -> list[dict]:
    slides = raw.get("slides", [])
    out = []
    for s in slides:
        title = " ".join(s.get("title", "").split()[:10])
        bullets = [" ".join(b.split()[:15]) for b in s.get("bullets", [])][:6]
        while len(bullets) < 3:
            bullets.append("Key point")
        out.append({
            "layout": s.get("layout", "bullets"),
            "title": title,
            "bullets": bullets,
            "speaker_notes": (s.get("speaker_notes", "") or "")[:800],
        })
    return out


def _is_placeholder_anthropic_key(key: str) -> bool:
    return not key or "placeholder" in key.lower() or not key.startswith("sk-ant-")


def _stub_slides(system: str, slide_count: int) -> tuple[dict, int]:
    m = re.search(r"approximately (\d+)", system)
    n = int(m.group(1)) if m else slide_count
    slides = [
        {
            "layout": "hero",
            "title": "Presentation Title",
            "bullets": ["Subtitle or tagline goes here", "Generated in development mode", "Add a real API key for AI generation"],
            "speaker_notes": "This is the opening slide. Welcome the audience and introduce the main topic. Provide context for why this presentation matters and what the audience will learn.",
        }
    ]
    section_titles = [
        "Executive Summary", "Key Findings", "Market Overview",
        "Strategic Recommendations", "Implementation Plan",
        "Financial Projections", "Risk Assessment", "Next Steps",
        "Conclusion", "Questions & Discussion",
    ]
    for i in range(1, n):
        title = section_titles[(i - 1) % len(section_titles)]
        slides.append({
            "layout": "bullets" if i % 3 != 0 else "two_column",
            "title": title,
            "bullets": [f"Key insight {j + 1} related to {title.lower()}" for j in range(4)],
            "speaker_notes": f"Discuss the details of {title.lower()}. Provide supporting data and context. Engage the audience with relevant examples.",
        })
    return {"slides": slides[:n]}, 0


async def _call_gemini(system: str, user_message: str) -> tuple[dict, int]:
    from google import genai
    from google.genai import types
    settings = get_settings()
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await client.aio.models.generate_content(
        model="gemini-flash-latest",
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=4096,
        ),
    )
    text = strip_fences(response.text.strip())
    result = json.loads(text)
    tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
    return result, tokens


async def _call_anthropic(system: str, user_message: str) -> tuple[dict, int]:
    from anthropic import AsyncAnthropic
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    text = strip_fences(response.content[0].text.strip())
    result = json.loads(text)
    tokens = response.usage.input_tokens + response.usage.output_tokens
    return result, tokens


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
async def call_claude(system: str, user_message: str) -> tuple[dict, int]:
    settings = get_settings()

    if settings.GEMINI_API_KEY:
        return await _call_gemini(system, user_message)

    if not _is_placeholder_anthropic_key(settings.ANTHROPIC_API_KEY):
        return await _call_anthropic(system, user_message)

    # No real API key — use stub slides for development
    m = re.search(r"approximately (\d+)", system)
    n = int(m.group(1)) if m else 8
    return _stub_slides(system, n)
