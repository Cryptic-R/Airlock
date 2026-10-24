"""Thin ASI:One LLM client with retries. Returns None on failure so callers can fall back."""

import json
import logging
import re
import time

import requests

from common.config import ASI1_API_KEY, ASI1_BASE_URL, ASI1_MODEL

log = logging.getLogger("asi1")


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 900,
         retries: int = 2, timeout: float = 40) -> str | None:
    if not ASI1_API_KEY:
        log.warning("ASI1_API_KEY not set; skipping LLM call")
        return None
    url = f"{ASI1_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {ASI1_API_KEY}", "Content-Type": "application/json"}
    body = {"model": ASI1_MODEL, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens}
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"ASI1 HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # network, HTTP, malformed response
            log.warning("ASI1 call failed (attempt %s): %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    return None


def parse_json_block(text: str | None) -> dict | None:
    """Pull the first JSON object out of an LLM reply (handles ```json fences)."""
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
