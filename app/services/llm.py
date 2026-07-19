"""Thin OpenAI chat-completions client (httpx, no SDK dependency).

All AI features degrade gracefully: if OPENAI_API_KEY is unset or a call
fails, callers receive None and the manual flow continues unchanged.
"""

import json
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger("flow.llm")

_API_URL = "https://api.openai.com/v1/chat/completions"
FAST_MODEL = "gpt-4o-mini"
SMART_MODEL = "gpt-4o"

# Persistent client — reuses TCP connections across calls (avoids TLS overhead per request)
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _client


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
        logger.warning("llm  non-JSON response from %s", model)
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
        logger.warning("llm  OPENAI_API_KEY not set — skipping")
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

    t0 = time.perf_counter()
    try:
        client = get_client()
        resp = await client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        ms = (time.perf_counter() - t0) * 1000
        data = resp.json()
        tokens = data.get("usage", {}).get("total_tokens", "?")
        logger.info("llm.call  model=%s  %.0fms  tokens=%s  [ok]", model, ms, tokens)
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        ms = (time.perf_counter() - t0) * 1000
        logger.warning("llm.call  model=%s  %.0fms  [err] %s", model, ms, exc)
        return None
