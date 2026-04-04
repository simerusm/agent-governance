"""
Call a governance-runner pod over HTTP (after kubectl port-forward).

Example::

    from infrastructure.backend.client.governance_http import GovernanceRunnerClient

    c = GovernanceRunnerClient("http://127.0.0.1:8080")
    r = c.governed_complete("Hello, write a haiku.")
    print(r["response_text"], r["prompt_governance"], r["response_governance"])
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx


class GovernanceRunnerClient:
    def __init__(self, base_url: str, *, timeout_s: float = 180.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    def healthz(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(f"{self._base}/healthz")
            r.raise_for_status()
            return r.json()

    def evaluate(
        self,
        text: str,
        *,
        phase: str = "evaluate",
        policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"text": text, "phase": phase}
        if policy:
            body["policy"] = policy
        with httpx.Client(timeout=self._timeout) as client:
            r = client.post(f"{self._base}/v1/evaluate", json=body)
            r.raise_for_status()
            return r.json()

    def governed_complete(
        self,
        prompt: str,
        *,
        policy: Optional[Dict[str, Any]] = None,
        llm: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"prompt": prompt}
        if policy:
            body["policy"] = policy
        if llm:
            body["llm"] = llm
        with httpx.Client(timeout=self._timeout) as client:
            r = client.post(f"{self._base}/v1/governed-complete", json=body)
            r.raise_for_status()
            return r.json()
