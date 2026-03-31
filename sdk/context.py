from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Mapping

_current_run: ContextVar["RunContext | None"] = ContextVar("governance_current_run", default=None)


@dataclass(frozen=True)
class AgentMetadata:
    """Attached to a wrapped function by :func:`sdk.decorators.governed_agent`."""

    policy: str
    name: str
    module: str | None = None
    qualname: str | None = None
    tags: Mapping[str, str] = field(default_factory=dict)


@dataclass
class RunContext:
    """
    One logical governed execution (agent run). Nested runs may use child contexts later;
    for now a single stack per task is enough for tracing helpers.

    ``tool_events`` and ``artifact_refs`` are appended by :mod:`sdk.tooling` / :mod:`sdk.artifacts`
    during the run (best-effort; no-op if no active context).
    """

    run_id: str
    policy: str
    agent_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    artifact_refs: list[Any] = field(default_factory=list)  # ArtifactRef; forward ref to avoid cycle

    @staticmethod
    def new(policy: str, agent_name: str, **meta: Any) -> RunContext:
        return RunContext(
            run_id=str(uuid.uuid4()),
            policy=policy,
            agent_name=agent_name,
            metadata=meta,
        )


def current_run_context() -> RunContext | None:
    return _current_run.get()


@contextmanager
def run_context(ctx: RunContext) -> Iterator[RunContext]:
    token = _current_run.set(ctx)
    try:
        yield ctx
    finally:
        _current_run.reset(token)


def with_run_context(fn: Callable[..., Any], ctx: RunContext) -> Callable[..., Any]:
    """Wrap ``fn`` so it executes under ``run_context(ctx)``."""

    def inner(*args: Any, **kwargs: Any) -> Any:
        with run_context(ctx):
            return fn(*args, **kwargs)

    return inner
