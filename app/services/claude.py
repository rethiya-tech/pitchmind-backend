import json
import logging
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

_log = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are a professional presentation generator. Convert the provided document into a structured slide deck.

OUTPUT FORMAT: Respond with ONLY valid JSON. No markdown fences, no explanation. Start with {{ and end with }}.

JSON schema:
{{
  "slides": [
    {{
      "layout": "hero|bullets|two_column|data_table|timeline|big_stat|process|quote",
      "title": "string — maximum 10 words",
      "bullets": ["string"],
      "speaker_notes": "string — 50 to 150 words"
    }}
  ]
}}

LAYOUT SELECTION — choose based on slide content:
- hero: ONLY the first slide. Large title + subtitle. bullets[0] = subtitle/tagline.
- data_table: detailed metrics tables with 4+ rows. Format EVERY bullet as "Label: Value" (e.g. "Revenue: $5.2M", "Status: Completed").
- two_column: comparing two things. Column headers are set by "## Header" bullets. Format: ["## Left Header", "point 1", "point 2", "## Right Header", "point 3", "point 4"]. Equal content bullets per side.
- timeline: phases, stages, milestones, or sequences. Format EVERY bullet as "Phase: Description" (e.g. "Q1: Market research completed"). Min 3, max 6 items.
- big_stat: 2–3 key metrics worth highlighting with large numbers. Format EVERY bullet as "Label: Value" (e.g. "Revenue Growth: +47%"). Use EXACTLY 2 or 3 bullets.
- process: workflows, procedures, numbered steps. Each bullet = one step. Min 3, max 5 steps.
- quote: notable quote, testimonial, or key statement. bullets[0] = quote text, bullets[1] = attribution/source. Max 2 bullets.
- bullets: all other content — explanations, descriptions, narrative points.

RULES:
1. First slide MUST be hero layout
2. Use timeline for any sequence/phases content when present
3. Use big_stat to spotlight 2–3 key metrics (striking visual impact)
4. Use process for any workflow or step-by-step content
5. Use data_table for detailed metric tables (4+ rows)
6. Use two_column for comparisons and two-sided content
7. Title: strictly maximum 10 words
8. Per-layout bullet counts:
   - hero: 1–2 bullets (subtitle/tagline)
   - bullets, two_column: min 3, max 6
   - data_table: min 4, max 7
   - timeline: min 3, max 6 (format: "Phase: Description")
   - big_stat: exactly 2 or 3 (format: "Label: Value")
   - process: min 3, max 5
   - quote: 1–2 bullets (quote then optional attribution)
9. Each bullet: maximum 15 words
10. Speaker notes: 50-150 words
11. Style: {STYLE}
12. Audience: {AUDIENCE_LEVEL}
13. Total slides: approximately {SLIDE_COUNT}\
"""


_FLAG_INSTRUCTIONS: dict[str, str] = {
    "minimal": (
        "Max 3 bullets per slide. Prefer `hero` and `bullets` layouts. "
        "Avoid `data_table`, `timeline`, and `two_column` unless the content "
        "is exclusively about data or comparisons."
    ),
    "roadmap": (
        "Include exactly one `timeline` layout slide showing key phases, "
        "milestones, or a project roadmap derived from the document."
    ),
    "data_focus": (
        "When the document contains numbers or metrics, prefer `big_stat` "
        "and `data_table` layouts. Aim for at least 2 data-oriented slides."
    ),
}


def build_system_prompt(
    style: str,
    audience_level: str,
    slide_count: int,
    presentation_flags: list[str] = [],
) -> str:
    base = SYSTEM_PROMPT_TEMPLATE.format(
        STYLE=style,
        AUDIENCE_LEVEL=audience_level,
        SLIDE_COUNT=slide_count,
    )
    active_flags = [f for f in presentation_flags if f in _FLAG_INSTRUCTIONS]
    if not active_flags:
        return base
    overrides = "\n\nFORMAT OVERRIDES (apply on top of all rules above):\n"
    for flag in active_flags:
        overrides += f"- {_FLAG_INSTRUCTIONS[flag]}\n"
    return base + overrides


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
        layout = s.get("layout", "bullets")
        bullets_raw = [" ".join(b.split()[:15]) for b in s.get("bullets", [])]

        if layout == "data_table":
            bullets = bullets_raw[:7]
            while len(bullets) < 4:
                bullets.append(f"Key metric {len(bullets) + 1}: Value")
        elif layout == "big_stat":
            bullets = bullets_raw[:3]
            while len(bullets) < 2:
                bullets.append(f"Metric {len(bullets) + 1}: Value")
        elif layout == "process":
            bullets = bullets_raw[:5]
            while len(bullets) < 3:
                bullets.append(f"Step {len(bullets) + 1}")
        elif layout == "timeline":
            bullets = bullets_raw[:6]
            while len(bullets) < 3:
                bullets.append(f"Phase {len(bullets) + 1}: Description")
        elif layout == "quote":
            bullets = bullets_raw[:2]
            while len(bullets) < 1:
                bullets.append("Insert quote here")
        elif layout == "two_column":
            # Ensure ## header markers are present
            has_headers = any(b.startswith("## ") for b in bullets_raw)
            if has_headers:
                bullets = bullets_raw[:8]
            else:
                # Wrap legacy bullets with default headers
                mid = len(bullets_raw) // 2 or 1
                left = bullets_raw[:mid] or ["Key point"]
                right = bullets_raw[mid:] or ["Key point"]
                bullets = ["## Key Points"] + left + ["## Details"] + right
        elif layout == "hero":
            bullets = bullets_raw[:2]
            if not bullets:
                bullets = ["Subtitle or tagline"]
        else:  # bullets
            bullets = bullets_raw[:6]
            while len(bullets) < 3:
                bullets.append("Key point")

        out.append({
            "layout": layout,
            "title": title,
            "bullets": bullets,
            "speaker_notes": (s.get("speaker_notes", "") or "")[:800],
        })
    return out


_VALID_COLOR_SCHEMES = {"default", "teal", "blue", "purple", "amber", "rose", "green", "orange"}
_VALID_SHAPE_STYLES = {"square", "rounded", "pill"}


async def enhance_slide(instruction: str, slide_data: dict) -> dict:
    """Apply a free-form user instruction to a slide and return changed fields."""
    title = slide_data.get("title", "")
    bullets = slide_data.get("bullets", [])
    notes = slide_data.get("speaker_notes", "")
    layout = slide_data.get("layout", "bullets")
    color_scheme = slide_data.get("color_scheme", "default")
    shape_style = slide_data.get("shape_style", "square")
    bullets_str = "\n".join(f"  - {b}" for b in bullets)

    prompt = f"""\
You are editing a single presentation slide. Apply the user's instruction and return ONLY the fields that changed.

Current slide:
  Layout: {layout}
  Title: {title}
  Bullets:
{bullets_str}
  Speaker Notes: {notes[:300] if notes else "(none)"}
  Color Scheme: {color_scheme}
  Shape Style: {shape_style}

User instruction: "{instruction}"

Rules:
- Return ONLY valid JSON — no markdown, no explanation, start with {{ and end with }}
- Include ONLY fields that need to change: "title", "bullets", "speaker_notes", "layout", "color_scheme", "shape_style"
- title: max 10 words
- bullets: each max 15 words; keep same count unless instruction says otherwise
- layout options: hero | bullets | two_column | data_table | timeline | big_stat | process | quote
- color_scheme options: default | teal | blue | purple | amber | rose | green | orange
- shape_style options: square | rounded | pill
- If changing layout, reformat bullets to match:
    timeline → "Phase: Description"
    data_table / big_stat → "Label: Value"
    process → each bullet is one numbered step
    quote → bullets[0] = quote text, bullets[1] = attribution
- two_column: column headers are "## Header" bullets. Format: ["## Left Header", "content", "content", "## Right Header", "content", "content"]
  To rename a column header (e.g. "change Key Points to Strengths"), update the "## " bullet text only
  Content bullets have NO prefix — write them as plain points without "Label: " repetition
- "make rounded" or "round corners" → set shape_style to "rounded"
- "pill shape" or "very rounded" → set shape_style to "pill"
- "square" or "sharp corners" → set shape_style to "square"
- Color instructions map to color_scheme: "blue" → "blue", "purple" → "purple", "amber/orange/warm" → "amber", "red/rose/pink" → "rose", "teal/green" → "teal", "reset color" → "default"

Return example: {{"color_scheme": "blue", "shape_style": "rounded"}}"""

    result_text = await _call_ai_text(prompt, max_tokens=2048)
    result_text = strip_fences(result_text).strip()
    _log.info("enhance_slide raw response: %r", result_text[:500])
    start = result_text.find('{')
    if start == -1:
        raise ValueError(f"No JSON object in response: {result_text[:200]}")
    try:
        parsed, _ = json.JSONDecoder().raw_decode(result_text, start)
    except json.JSONDecodeError as exc:
        _log.error("enhance_slide JSON parse failed. raw=%r", result_text[:500])
        raise ValueError(f"AI returned malformed JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object")

    out: dict = {}
    if "title" in parsed and isinstance(parsed["title"], str):
        out["title"] = " ".join(parsed["title"].split()[:10])
    if "bullets" in parsed and isinstance(parsed["bullets"], list):
        out["bullets"] = [str(b)[:120] for b in parsed["bullets"][:7]]
    if "speaker_notes" in parsed and isinstance(parsed["speaker_notes"], str):
        out["speaker_notes"] = parsed["speaker_notes"][:800]
    if "layout" in parsed and parsed["layout"] in (
        "hero", "bullets", "two_column", "data_table", "timeline", "big_stat", "process", "quote"
    ):
        out["layout"] = parsed["layout"]
    if "color_scheme" in parsed and parsed["color_scheme"] in _VALID_COLOR_SCHEMES:
        out["color_scheme"] = parsed["color_scheme"]
    if "shape_style" in parsed and parsed["shape_style"] in _VALID_SHAPE_STYLES:
        out["shape_style"] = parsed["shape_style"]
    return out


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def _call_ai_text(prompt: str, max_tokens: int = 512) -> str:
    """Call AI with a plain prompt and return raw text."""
    settings = get_settings()

    if settings.GEMINI_API_KEY:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        safety_off = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                safety_settings=safety_off,
            ),
        )
        text = None
        finish_reason = None
        try:
            if response.candidates:
                finish_reason = str(getattr(response.candidates[0], 'finish_reason', ''))
            text = response.text
        except Exception:
            pass
        if not text:
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                pass
        if not text:
            _log.error("Gemini returned empty response. finish_reason=%s", finish_reason)
            raise ValueError("AI returned an empty response — please try again")
        _log.error("Gemini finish_reason=%s text_len=%d", finish_reason, len(text))
        return text.strip()

    if not _is_placeholder_anthropic_key(settings.ANTHROPIC_API_KEY):
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    raise ValueError("No AI API key configured")


_STUB_QUESTIONS = [
    "Who is the primary target audience for this presentation?",
    "What is the single most important message you want the audience to take away?",
    "What tone should the presentation have (formal, inspiring, educational, persuasive)?",
    "Are there specific data points, statistics, or case studies you want to include?",
    "What problem does your presentation address, and what is your proposed solution?",
    "What makes your approach unique compared to existing alternatives?",
    "What is the desired outcome — what should the audience do after seeing this?",
    "Are there any constraints or requirements (brand guidelines, time limit, slide count)?",
    "What background knowledge can you assume the audience already has?",
    "Are there any topics or angles that should be avoided or handled carefully?",
]


async def generate_questions(prompt: str) -> list[str]:
    """Generate 10 clarifying questions for a presentation prompt."""
    settings = get_settings()

    system = (
        "You are a presentation strategist. Given a topic or prompt, produce exactly 10 "
        "targeted clarifying questions that will help generate better slides. "
        "Return ONLY a JSON array of 10 strings. No markdown fences, no explanation. "
        'Example: ["Question 1?", "Question 2?", ...]'
    )
    user_msg = f"Presentation topic/prompt:\n{prompt}"

    try:
        text = await _call_ai_text(f"{system}\n\n{user_msg}", max_tokens=1024)
        text = strip_fences(text)
        start = text.find("[")
        if start == -1:
            raise ValueError("No JSON array in response")
        questions = json.loads(text[start:])
        if isinstance(questions, list):
            return [str(q) for q in questions[:10]]
        raise ValueError("Not a list")
    except Exception:
        # Fall back to generic questions if AI call fails or no key
        return list(_STUB_QUESTIONS)


def friendly_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "429" in msg or "resource_exhausted" in low or "quota" in low or "rate_limit" in low:
        return "AI quota exceeded — please wait a few minutes and try again."
    if "503" in msg or "unavailable" in low or "high demand" in low or "overloaded" in low:
        return "AI service is busy — please try again in a moment."
    if "401" in msg or "api_key" in low or "invalid key" in low or "unauthenticated" in low:
        return "AI API key is invalid or missing. Please check your configuration."
    if "timeout" in low or "timed out" in low or "deadline" in low:
        return "AI service timed out — please try again."
    if "json" in low or "unterminated" in low or "parse" in low:
        return "AI returned an unexpected response. Please try again with fewer slides."
    return "AI generation failed — please try again."


def _is_placeholder_anthropic_key(key: str) -> bool:
    return not key or "placeholder" in key.lower() or not key.startswith("sk-ant-")


def _stub_slides(system: str, slide_count: int) -> tuple[dict, dict]:
    m = re.search(r"approximately (\d+)", system)
    n = int(m.group(1)) if m else slide_count
    # Pitch deck structure with editable placeholder text
    deck = [
        {
            "layout": "hero",
            "title": "Your Presentation Title",
            "bullets": ["Add your tagline or subtitle here"],
            "speaker_notes": "Opening slide. Replace the title and tagline with your own content.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "bullets",
            "title": "The Problem",
            "bullets": ["Describe the problem you are solving", "Who is affected and how", "Current solutions fall short because…"],
            "speaker_notes": "Explain the pain point clearly. Make the audience feel the urgency.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "bullets",
            "title": "Our Solution",
            "bullets": ["State your solution in one sentence", "Key differentiator vs alternatives", "Why now is the right time"],
            "speaker_notes": "Present your solution simply and confidently.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "data_table",
            "title": "Market Opportunity",
            "bullets": ["Total Addressable Market: $X billion", "Serviceable Market: $X million", "Target Segment: Describe here", "Growth Rate: X% annually"],
            "speaker_notes": "Back up your market size with credible data sources.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "bullets",
            "title": "Business Model",
            "bullets": ["Revenue stream: how you make money", "Pricing model: subscription / per-use / etc.", "Unit economics: LTV vs CAC"],
            "speaker_notes": "Be specific about how revenue flows in.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "two_column",
            "title": "Traction & Milestones",
            "bullets": ["## Progress", "Users / customers to date", "Revenue or ARR", "## Goals", "Key partnerships signed", "Next milestone target"],
            "speaker_notes": "Show momentum. Numbers build credibility.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "bullets",
            "title": "The Team",
            "bullets": ["Founder name — role and background", "Co-founder name — role and background", "Key advisor — relevant expertise"],
            "speaker_notes": "Investors back people. Highlight why this team wins.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "data_table",
            "title": "Financial Projections",
            "bullets": ["Year 1 Revenue: $X", "Year 2 Revenue: $X", "Year 3 Revenue: $X", "Break-even: Month X"],
            "speaker_notes": "Show a credible growth path. Explain key assumptions.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "bullets",
            "title": "The Ask",
            "bullets": ["Raising: $X at $Y valuation", "Use of funds: product / sales / hiring", "Timeline: close by [date]"],
            "speaker_notes": "Be clear and confident about what you need and why.",
            "color_scheme": "default",
            "shape_style": "square",
        },
        {
            "layout": "hero",
            "title": "Thank You",
            "bullets": ["your@email.com  ·  yourwebsite.com"],
            "speaker_notes": "Leave contact details. Invite questions.",
            "color_scheme": "default",
            "shape_style": "square",
        },
    ]
    return {"slides": deck[:n]}, {"input": 0, "output": 0}


async def _call_gemini(system: str, user_message: str) -> tuple[dict, dict]:
    from google import genai
    from google.genai import types
    settings = get_settings()
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=_tokens_for_slides(system),
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    # Robustly extract text — gemini-2.5-flash thinking model can fail .text
    text = None
    finish_reason = None
    try:
        if response.candidates:
            finish_reason = str(getattr(response.candidates[0], "finish_reason", ""))
        text = response.text
    except Exception:
        pass
    if not text:
        try:
            text = response.candidates[0].content.parts[0].text
        except Exception:
            pass
    if not text:
        _log.error("Gemini slide generation empty response. finish_reason=%s", finish_reason)
        raise ValueError("AI returned an empty response — please try again")
    text = strip_fences(text.strip())
    # Extract JSON object even if there's surrounding text
    start = text.find("{")
    if start == -1:
        _log.error("Gemini slide generation: no JSON object found. raw=%r", text[:300])
        raise ValueError("AI returned an unexpected response. Please try again with fewer slides.")
    try:
        result, _ = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError as exc:
        _log.error("Gemini slide generation JSON parse failed. raw=%r", text[:300])
        raise ValueError("AI returned an unexpected response. Please try again with fewer slides.") from exc
    input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
    output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
    return result, {"input": input_tokens, "output": output_tokens}


def _tokens_for_slides(system: str) -> int:
    m = re.search(r"approximately (\d+)", system)
    n = int(m.group(1)) if m else 10
    # ~400 tokens per slide (title + bullets + speaker_notes + JSON overhead)
    return min(8192, max(4096, n * 400))


async def _call_anthropic(system: str, user_message: str) -> tuple[dict, dict]:
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
    return result, {"input": response.usage.input_tokens, "output": response.usage.output_tokens}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
async def call_claude(system: str, user_message: str) -> tuple[dict, dict]:
    settings = get_settings()

    if settings.GEMINI_API_KEY:
        return await _call_gemini(system, user_message)

    if not _is_placeholder_anthropic_key(settings.ANTHROPIC_API_KEY):
        return await _call_anthropic(system, user_message)

    # No real API key — use stub slides for development
    m = re.search(r"approximately (\d+)", system)
    n = int(m.group(1)) if m else 8
    return _stub_slides(system, n)