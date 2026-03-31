from __future__ import annotations

from typing import Any, Mapping

from .context import current_run_context


def record_tool_invocation(
    name: str,
    payload: Any = None,
    **extra: Any,
) -> None:
    """
    Best-effort record of a tool call inside a governed run (for tracing / later governance signals).
    Does nothing when no :class:`~sdk.context.RunContext` is active.
    """
    ctx = current_run_context()
    if ctx is None:
        return
    row = {"name": name, "payload": payload, **extra}
    ctx.tool_events.append(row)


def file_reference(
    path: str,
    *,
    label: str | None = None,
    role: str | None = None,
) -> Mapping[str, Any]:
    """
    Structured file reference for logging or attaching to events — not a filesystem open.

    Returns a small dict you can pass to :func:`record_tool_invocation` or your own payloads.
    """
    out: dict[str, Any] = {"kind": "file", "path": path}
    if label is not None:
        out["label"] = label
    if role is not None:
        out["role"] = role
    return out
