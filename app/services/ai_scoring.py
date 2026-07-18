"""AI auto-categorization: one fast LLM call on task creation returns both
matrix quadrants, a one-line rationale, a duration estimate, and any deadline
parsed from natural language ("call Sarah before Friday" -> due_date).
"""

import logging
from datetime import datetime, timezone

from app.services import llm

logger = logging.getLogger(__name__)

_VALID_EISENHOWER = {"do_first", "schedule", "delegate", "eliminate"}
_VALID_IMPACT_EFFORT = {"quick_win", "major_project", "fill_in", "thankless"}

_SYSTEM = """You are the prioritization engine inside Flow Todo, a todo app \
that scores every task on two matrices and only surfaces the user's top 10.

Given one task title, respond with a JSON object:
{
  "eisenhower_quadrant": "do_first" | "schedule" | "delegate" | "eliminate",
  "impact_effort_quadrant": "quick_win" | "major_project" | "fill_in" | "thankless",
  "rationale": "<one sentence, max 120 chars, explaining the ranking>",
  "duration_minutes": <integer estimate, or null if unguessable>,
  "due_date": "<ISO 8601 date/datetime if the title states or implies a deadline, else null>"
}

Guidance:
- Eisenhower: urgency + importance. Deadlines soon or blocking others -> do_first.
  Important but not urgent -> schedule. Urgent but low importance -> delegate.
  Neither -> eliminate.
- Impact/Effort: high impact + low effort -> quick_win. High impact + high effort
  -> major_project. Low impact + low effort -> fill_in. Low impact + high effort
  -> thankless.
- Resolve relative deadlines ("Friday", "end of quarter") against today's date
  given in the user message. Only set due_date when the title actually implies one.
- rationale is shown to the user next to the task; be concrete, not generic."""


async def score_task(title: str) -> dict | None:
    """Returns validated scoring dict or None (caller falls back to manual flow)."""
    today = datetime.now(timezone.utc).strftime("%A, %Y-%m-%d")
    result = await llm.complete_json(
        _SYSTEM,
        f"Today is {today}.\nTask: {title}",
        model=llm.FAST_MODEL,
        max_tokens=300,
    )
    if not result:
        return None

    eisenhower = result.get("eisenhower_quadrant")
    impact_effort = result.get("impact_effort_quadrant")
    if eisenhower not in _VALID_EISENHOWER or impact_effort not in _VALID_IMPACT_EFFORT:
        logger.warning("AI scoring returned invalid quadrants: %s", result)
        return None

    duration = result.get("duration_minutes")
    if not isinstance(duration, int) or duration <= 0 or duration > 24 * 60:
        duration = None

    due_date = _parse_due_date(result.get("due_date"))

    rationale = result.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        rationale = None
    else:
        rationale = rationale.strip()[:200]

    return {
        "eisenhower_quadrant": eisenhower,
        "impact_effort_quadrant": impact_effort,
        "rationale": rationale,
        "duration_minutes": duration,
        "due_date": due_date,
    }


def _parse_due_date(raw) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.isoformat()
    except ValueError:
        return None
