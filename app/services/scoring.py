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
