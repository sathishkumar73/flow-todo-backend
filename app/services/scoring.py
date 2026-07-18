from datetime import datetime, timezone

EISENHOWER_SCORES: dict[str, int] = {
    "do_first": 100,
    "schedule": 70,
    "delegate": 40,
    "eliminate": 10,
}

IMPACT_EFFORT_SCORES: dict[str, int] = {
    "quick_win": 100,
    "major_project": 70,
    "fill_in": 40,
    "thankless": 10,
}


def compute_priority_score(
    eisenhower: str | None,
    impact_effort: str | None,
) -> int:
    e = EISENHOWER_SCORES.get(eisenhower) if eisenhower else None
    i = IMPACT_EFFORT_SCORES.get(impact_effort) if impact_effort else None

    if e is not None and i is not None:
        return round((e + i) / 2)
    if e is not None:
        return e
    if i is not None:
        return i
    return 0


def deadline_boost(due_date, now: datetime | None = None) -> int:
    """Boost applied at read time so "next week" tasks rise as their deadline
    approaches — no nightly recalculation job needed."""
    if not due_date:
        return 0
    if isinstance(due_date, str):
        try:
            due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
        except ValueError:
            return 0
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    days = (due_date - now).total_seconds() / 86_400
    if days < 0:
        return 25
    if days < 1:
        return 20
    if days < 2:
        return 15
    if days < 4:
        return 10
    if days < 8:
        return 5
    return 0


def effective_priority(priority_score: int, due_date) -> int:
    return priority_score + deadline_boost(due_date)
