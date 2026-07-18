"""AI Daily Briefing: a 3-sentence "your day at a glance" generated once per
day per user and cached in the briefings table. Falls back to a deterministic
stats-only summary when the LLM is unavailable (fallbacks are not cached, so
the AI version replaces them once the API is reachable).
"""

from datetime import datetime, timezone

from app.services import llm, scoring
from app.services.db.core import execute, query_one
from app.services.db import tasks as tasks_db

_SYSTEM = """You write the morning briefing inside Flow Todo, a todo app that
surfaces only the user's top 10 tasks.

Given the user's task stats and their top tasks (already sorted by priority),
write a briefing of at most 3 short sentences: what today looks like, roughly
how much focus time it needs, and which 2-3 tasks to start with (name them).

Tone: calm, direct, encouraging — never guilt-tripping. No greetings, no
emojis, no bullet points. Plain sentences only."""


async def get_briefing(user_id: str) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()

    cached = await query_one(
        "SELECT content FROM briefings WHERE user_id = %s AND brief_date = %s",
        (user_id, today),
    )
    if cached:
        return {"date": today, "content": cached["content"], "cached": True}

    tasks = await tasks_db.get_tasks(user_id)
    active = [t for t in tasks if t["status"] == "active"]
    if not active:
        return {
            "date": today,
            "content": "Nothing on your list yet. Add a task to get started.",
            "cached": False,
        }

    for t in active:
        t["_eff"] = scoring.effective_priority(t["priority_score"], t["due_date"])
    top = sorted(active, key=lambda t: t["_eff"], reverse=True)[:5]

    due_soon = sum(1 for t in active if scoring.deadline_boost(t["due_date"]) >= 10)
    known_minutes = [t["duration_minutes"] for t in top if t["duration_minutes"]]
    focus_minutes = sum(known_minutes)

    task_lines = "\n".join(
        f"- {t['title']}"
        + (f" (due boost {scoring.deadline_boost(t['due_date'])})" if t["due_date"] else "")
        + (f" (~{t['duration_minutes']} min)" if t["duration_minutes"] else "")
        for t in top
    )
    stats = (
        f"Active tasks: {len(active)}. Due within ~3 days: {due_soon}. "
        f"Known focus time for top tasks: {focus_minutes} min.\n"
        f"Top tasks by priority:\n{task_lines}"
    )

    content = await llm.complete_text(
        _SYSTEM, stats, model=llm.FAST_MODEL, max_tokens=200
    )
    if content:
        content = content.strip()
        await execute(
            """
            INSERT INTO briefings (user_id, brief_date, content)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, brief_date) DO UPDATE SET content = EXCLUDED.content
            """,
            (user_id, today, content),
        )
        return {"date": today, "content": content, "cached": False}

    # deterministic fallback, intentionally not cached
    first = top[0]["title"]
    fallback = (
        f"You have {len(active)} active tasks"
        + (f", {due_soon} due soon" if due_soon else "")
        + f". Start with: {first}."
    )
    return {"date": today, "content": fallback, "cached": False}
