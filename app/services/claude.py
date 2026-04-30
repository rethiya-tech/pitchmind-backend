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
      "bullets": ["string"],
      "speaker_notes": "string — 50 to 150 words"
    }}
  ]
}}

LAYOUT SELECTION — choose based on slide content:
- hero: ONLY the first slide. Large title + subtitle. bullets[0] = subtitle/tagline.
- data_table: when content has metrics, statistics, specifications, key-value data, feature lists with values, or any structured label-value information. Format EVERY bullet as "Label: Value" (e.g. "Total Users: 1,200", "Revenue: $5.2M", "Status: Completed"). Minimum 4 rows.
- two_column: when comparing two things side-by-side — pros vs cons, before vs after, features vs benefits, two phases, two teams, two options. First half of bullets = left column, second half = right column. Use equal numbers of bullets on each side.
- bullets: all other content — processes, steps, explanations, descriptions, narrative content.

RULES:
1. First slide MUST be hero layout
2. Use data_table for at least 1-2 slides if document has any metrics or structured data
3. Use two_column for at least 1 slide if document has comparisons or two-sided content
4. Title: strictly maximum 10 words
5. Bullets: minimum 3, maximum 6 per slide (for data_table: minimum 4, maximum 7)
6. Each bullet: maximum 15 words
7. Speaker notes: 50-150 words
8. Style: {STYLE}
9. Audience: {AUDIENCE_LEVEL}
10. Total slides: approximately {SLIDE_COUNT}\
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
    # Pitch deck structure with editable placeholder text
    deck = [
        {
            "layout": "hero",
            "title": "Your Presentation Title",
            "bullets": ["Add your tagline or subtitle here"],
            "speaker_notes": "Opening slide. Replace the title and tagline with your own content.",
        },
        {
            "layout": "bullets",
            "title": "The Problem",
            "bullets": ["Describe the problem you are solving", "Who is affected and how", "Current solutions fall short because…"],
            "speaker_notes": "Explain the pain point clearly. Make the audience feel the urgency.",
        },
        {
            "layout": "bullets",
            "title": "Our Solution",
            "bullets": ["State your solution in one sentence", "Key differentiator vs alternatives", "Why now is the right time"],
            "speaker_notes": "Present your solution simply and confidently.",
        },
        {
            "layout": "data_table",
            "title": "Market Opportunity",
            "bullets": ["Total Addressable Market: $X billion", "Serviceable Market: $X million", "Target Segment: Describe here", "Growth Rate: X% annually"],
            "speaker_notes": "Back up your market size with credible data sources.",
        },
        {
            "layout": "bullets",
            "title": "Business Model",
            "bullets": ["Revenue stream: how you make money", "Pricing model: subscription / per-use / etc.", "Unit economics: LTV vs CAC"],
            "speaker_notes": "Be specific about how revenue flows in.",
        },
        {
            "layout": "two_column",
            "title": "Traction & Milestones",
            "bullets": ["Users / customers to date", "Revenue or ARR", "Key partnerships signed", "Next milestone target"],
            "speaker_notes": "Show momentum. Numbers build credibility.",
        },
        {
            "layout": "bullets",
            "title": "The Team",
            "bullets": ["Founder name — role and background", "Co-founder name — role and background", "Key advisor — relevant expertise"],
            "speaker_notes": "Investors back people. Highlight why this team wins.",
        },
        {
            "layout": "data_table",
            "title": "Financial Projections",
            "bullets": ["Year 1 Revenue: $X", "Year 2 Revenue: $X", "Year 3 Revenue: $X", "Break-even: Month X"],
            "speaker_notes": "Show a credible growth path. Explain key assumptions.",
        },
        {
            "layout": "bullets",
            "title": "The Ask",
            "bullets": ["Raising: $X at $Y valuation", "Use of funds: product / sales / hiring", "Timeline: close by [date]"],
            "speaker_notes": "Be clear and confident about what you need and why.",
        },
        {
            "layout": "hero",
            "title": "Thank You",
            "bullets": ["your@email.com  ·  yourwebsite.com"],
            "speaker_notes": "Leave contact details. Invite questions.",
        },
    ]
    return {"slides": deck[:n]}, 0


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
            max_output_tokens=_tokens_for_slides(system),
        ),
    )
    text = strip_fences(response.text.strip())
    result = json.loads(text)
    tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
    return result, tokens


def _tokens_for_slides(system: str) -> int:
    m = re.search(r"approximately (\d+)", system)
    n = int(m.group(1)) if m else 10
    # ~400 tokens per slide (title + bullets + speaker_notes + JSON overhead)
    return min(8192, max(4096, n * 400))


async def _call_anthropic(system: str, user_message: str) -> tuple[dict, int]:
    from anthropic import AsyncAnthropic
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=_tokens_for_slides(system),
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
