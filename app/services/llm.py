"""Thin OpenAI chat-completions client (httpx, no SDK dependency).

All AI features degrade gracefully: if OPENAI_API_KEY is unset or a call
fails, callers receive None and the manual flow continues unchanged.
"""

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/chat/completions"
FAST_MODEL = "gpt-4o-mini"
SMART_MODEL = "gpt-4o"


async def complete_json(
    system: str,
    user: str,
    model: str = FAST_MODEL,
    max_tokens: int = 500,
    timeout: float = 15.0,
) -> dict | None:
    """Run a chat completion that must return a JSON object. None on any failure."""
    text = await complete_text(
        system, user, model=model, max_tokens=max_tokens, timeout=timeout, json_mode=True
    )
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("LLM returned non-JSON output")
        return None


async def complete_text(
    system: str,
    user: str,
    model: str = FAST_MODEL,
    max_tokens: int = 500,
    timeout: float = 15.0,
    json_mode: bool = False,
) -> str | None:
    if not settings.openai_api_key:
        return None
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return None
