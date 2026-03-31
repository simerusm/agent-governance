#!/usr/bin/env python3
"""
Example: wrap an agent function with the governance SDK.

Run from the repository root::

    python examples/sdk_governed_agent.py

Or::

    PYTHONPATH=. python examples/sdk_governed_agent.py

Optional env (see ``sdk.config``): ``GOVERNANCE_DEFAULT_POLICY``,
``GOVERNANCE_CONTROL_PLANE_URL`` (enables HTTP run reporting after each call).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow ``python examples/sdk_governed_agent.py`` without installing the package.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sdk import (
    ArtifactRef,
    governed_agent,
    record_artifact,
    record_tool_invocation,
    file_reference,
)
from sdk.context import current_run_context


@governed_agent(policy="example-demo", tags={"example": "sdk"})
def summarize_task(task: str) -> str:
    """Pretend agent: record a tool call and an artifact, then return a stub summary."""
    ctx = current_run_context()
    if ctx:
        print(f"  active run: id={ctx.run_id[:8]}… policy={ctx.policy!r}")

    record_tool_invocation("parse", {"chars": len(task)})
    # Structured file hint (e.g. attach to a payload); does not open the file.
    file_reference("/tmp/notes.txt", role="optional", label="scratch")
    record_artifact(
        ArtifactRef(
            kind="file",
            uri="file:///tmp/notes.txt",
            name="notes",
            meta={"role": "example"},
        )
    )
    return f"Summary: {task[:60].strip()}…"


def main() -> None:
    print("SDK example — governed_agent + tooling + artifacts\n")
    text = "Write a short design doc for the governance layer."
    result = summarize_task(text)
    print(f"return value: {result}\n")

    meta = getattr(summarize_task, "__governance_metadata__")
    print("Attached metadata (__governance_metadata__):")
    print(f"  policy: {meta.policy!r}")
    print(f"  name:   {meta.name!r}")
    print(f"  module: {meta.module!r}")
    print(f"  tags:   {dict(meta.tags)}")


if __name__ == "__main__":
    main()
