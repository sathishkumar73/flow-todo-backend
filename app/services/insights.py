"""Behavioral insights: burnout signal detection (pure SQL statistics, LLM
only phrases the message) and the weekly retrospective (cached per ISO week).
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

from app.services import llm
from app.services.db.core import execute, query_one

_BURNOUT_SYSTEM = """You write one short, kind message inside Flow Todo when a
user's completion pace has dropped well below their own baseline while they
keep adding tasks. Two sentences max. Acknowledge the pace change without
judgment and suggest clearing the decks to find what actually needs to happen
this week. Never use the word "burnout", never guilt-trip, no emojis."""

_RETRO_SYSTEM = """You write the weekly retrospective inside Flow Todo. Given
a user's stats for the past week (and the week before for comparison), write
3-4 short sentences: what they completed, one concrete pattern worth noticing,
and one specific suggestion for next week. Address the user as "you". Calm and
concrete, never generic filler, no emojis, no bullet points."""


async def get_velocity_stats(user_id: str) -> dict:
    row = await query_one(
        """
        SELECT
          count(*) FILTER (WHERE created_at   > now() - interval '7 days')  AS created_7d,
          count(*) FILTER (WHERE completed_at > now() - interval '7 days')  AS completed_7d,
          count(*) FILTER (WHERE created_at   > now() - interval '30 days') AS created_30d,
          count(*) FILTER (WHERE completed_at > now() - interval '30 days') AS completed_30d,
          count(*) FILTER (WHERE status = 'active') AS active_now
        FROM tasks WHERE user_id = %s
        """,
        (user_id,),
    )
    return row or {}


def detect_burnout(stats: dict) -> bool:
    """Completion rate dropped 40%+ below the 30-day weekly baseline while task
    creation stayed constant. Needs enough history to have a baseline."""
    completed_30d = stats.get("completed_30d") or 0
    created_7d = stats.get("created_7d") or 0
    completed_7d = stats.get("completed_7d") or 0
    if completed_30d < 8 or created_7d < 5:
        return False
    weekly_baseline = completed_30d / 4.3
    return completed_7d <= weekly_baseline * 0.6


async def get_insights(user_id: str) -> dict:
    stats = await get_velocity_stats(user_id)
    burnout = detect_burnout(stats)

    message = None
    if burnout:
        message = await llm.complete_text(
            _BURNOUT_SYSTEM,
            (
                f"This week: {stats['created_7d']} tasks added, "
                f"{stats['completed_7d']} completed. "
                f"Their usual pace is about {round((stats['completed_30d'] or 0) / 4.3)} "
                f"completions a week. Active tasks right now: {stats['active_now']}."
            ),
            model=llm.FAST_MODEL,
            max_tokens=120,
        )
        if not message:
            message = (
                f"You've added {stats['created_7d']} tasks this week and completed "
                f"{stats['completed_7d']} — slower than your usual pace. Want to clear "
                "the decks and pick what actually needs to happen this week?"
            )

    return {"stats": stats, "burnout_signal": burnout, "message": message}


def _week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())


async def get_retrospective(user_id: str) -> dict:
    today = datetime.now(timezone.utc).date()
    week_start = _week_start(today)
    ws = week_start.isoformat()

    # Run cache check, stats, and top_done all in parallel — discard unused results
    cached, stats, top_done = await asyncio.gather(
        query_one(
            "SELECT content, stats FROM retrospectives WHERE user_id = %s AND week_start = %s",
            (user_id, ws),
        ),
        query_one(
            """
            SELECT
              count(*) FILTER (WHERE completed_at >= %s::timestamptz)              AS completed_this_week,
              count(*) FILTER (WHERE created_at   >= %s::timestamptz)              AS created_this_week,
              count(*) FILTER (WHERE completed_at >= %s::timestamptz - interval '7 days'
                                 AND completed_at <  %s::timestamptz)              AS completed_last_week,
              count(*) FILTER (WHERE status = 'active')                            AS active_now,
              count(*) FILTER (WHERE status = 'active'
                                 AND last_touched_at < now() - interval '14 days') AS stale_now
            FROM tasks WHERE user_id = %s
            """,
            (ws, ws, ws, ws, user_id),
        ),
        query_one(
            """
            SELECT string_agg(title, '; ') AS titles FROM (
              SELECT title FROM tasks
              WHERE user_id = %s AND completed_at >= %s::timestamptz
              ORDER BY priority_score DESC LIMIT 3
            ) t
            """,
            (user_id, ws),
        ),
    )

    if cached:
        return {
            "week_start": ws,
            "content": cached["content"],
            "stats": cached["stats"],
            "cached": True,
        }

    if (stats["completed_this_week"] or 0) == 0 and (stats["created_this_week"] or 0) == 0:
        return {
            "week_start": ws,
            "content": "No activity yet this week — your retrospective will appear once you've added or completed tasks.",
            "stats": stats,
            "cached": False,
        }

    content = await llm.complete_text(
        _RETRO_SYSTEM,
        (
            f"This week: completed {stats['completed_this_week']}, added "
            f"{stats['created_this_week']}. Last week: completed "
            f"{stats['completed_last_week']}. Active now: {stats['active_now']} "
            f"({stats['stale_now']} untouched 14+ days). "
            f"Highest-priority completions: {top_done['titles'] or 'none'}."
        ),
        model=llm.SMART_MODEL,
        max_tokens=250,
    )

    if content:
        content = content.strip()
        import json

        await execute(
            """
            INSERT INTO retrospectives (user_id, week_start, content, stats)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, week_start)
            DO UPDATE SET content = EXCLUDED.content, stats = EXCLUDED.stats
            """,
            (user_id, ws, content, json.dumps(stats)),
        )
        return {
            "week_start": ws,
            "content": content,
            "stats": stats,
            "cached": False,
        }

    return {
        "week_start": ws,
        "content": (
            f"You completed {stats['completed_this_week']} tasks this week and added "
            f"{stats['created_this_week']}."
        ),
        "stats": stats,
        "cached": False,
    }
