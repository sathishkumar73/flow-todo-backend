"""Smart Task Rewriting ("Sharpen"): turn a vague task into a concrete,
implementation-intention version the user can accept or reject.
"""

from datetime import datetime, timezone

from app.services import llm

_SYSTEM = """You rewrite vague todo items into sharp, actionable tasks.

A sharp task names the concrete next action, a scope, and (when the original
implies one) a time anchor. Examples:
- "Work on deck" -> "Draft slides 3-7 of investor deck (45 min)"
- "Emails" -> "Clear inbox to zero and reply to the 3 client threads"
- "Fix the bug" -> "Reproduce and fix the login redirect bug"

Rules:
- Keep it under 90 characters.
- Never invent specifics that change the task's meaning; sharpen, don't expand.
- If the task is already sharp, return it unchanged.

Respond with a JSON object: {"suggestion": "<rewritten task>"}"""


async def sharpen_task(title: str) -> str | None:
    today = datetime.now(timezone.utc).strftime("%A, %Y-%m-%d")
    result = await llm.complete_json(
        _SYSTEM,
        f"Today is {today}.\nTask: {title}",
        model=llm.FAST_MODEL,
        max_tokens=150,
    )
    if not result:
        return None
    suggestion = result.get("suggestion")
    if not isinstance(suggestion, str) or not suggestion.strip():
        return None
    return suggestion.strip()[:200]
