from __future__ import annotations

from typing import Any, Optional

import httpx


def complete_openai_compatible(
    prompt: str,
    *,
    base_url: str,
    api_key: Optional[str],
    model: str,
    timeout_s: float = 120.0,
) -> str:
    """POST /v1/chat/completions (OpenAI-compatible)."""
    url = base_url.rstrip("/") + "/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("LLM response missing choices")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise ValueError("LLM response missing message.content")
    return content


def mock_complete(prompt: str, *, model: str = "mock") -> str:
    return (
        "Mock LLM response.\n\n"
        f"(model={model})\n"
        f"Echo: {prompt[:500]}"
        + ("…" if len(prompt) > 500 else "")
    )
