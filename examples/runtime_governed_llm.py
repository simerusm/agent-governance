#!/usr/bin/env python3
"""
Example: runtime layer performs inline governance on LLM prompt + response.

Run from repo root:

  python examples/runtime_governed_llm.py

Notes:
- Default is observe-only (warn on alert, do not block).
- To enable blocking, set `RuntimePolicy(block_on_alert=True)` in this file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime import GovernedRunner, MockLLM, RuntimePolicy
from sdk import RuntimeLayerClient, governed_agent


runner = GovernedRunner(
    policy=RuntimePolicy(
        name="default",
        alert_threshold=75.0,
        block_on_alert=False,  # feature flag
    ),
    llm=MockLLM(name="mock"),
)
client = RuntimeLayerClient(runner)


@governed_agent(
    policy="default",
    client=client,
)
def my_agent(task: str, *, execution_context=None) -> str:
    """
    Agent code uses the runtime-injected `execution_context` to call the LLM.
    The runtime layer wraps that call with:
      - pre_prompt governance_engine.analyze + score_report
      - post_response governance_engine.analyze + score_report
    """
    prompt = (
        "You are my assistant. Summarize the following.\n\n"
        f"Task: {task}\n\n"
        "Here is a token: sk-ant-api01-aaaaaaaaaaaaaaaaaaaa\n"
        "Here is a JWT: eyJaaaaaaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbbbbbb.cccccccccccccccccccc\n"
        "Here is a file mention: `.env`\n"
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQD\n"
        "-----END PRIVATE KEY-----\n"
    )

    # Inline gate happens here (pre_prompt + post_response).
    resp = execution_context.governed_complete(prompt, model="mock-1")
    return resp


def main() -> None:
    print("Runtime example — governed prompt + response checks\n")
    out = my_agent("Draft a 1-paragraph README for the project.")
    print("Agent return value (truncated):")
    print(out[:220] + ("…" if len(out) > 220 else ""))
    print()

    print("Captured runtime trace events:")
    print(json.dumps(runner.last_trace, indent=2))


if __name__ == "__main__":
    main()

