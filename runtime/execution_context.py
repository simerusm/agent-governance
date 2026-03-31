from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from sdk.context import RunContext

from .decision_engine import DecisionEngine
from .hooks import Hook, HookEvent
from .policies import RuntimePolicy
from .trace_capture import TraceCollector


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> str:
        ...


class MockLLM:
    """
    No-network stand-in for an LLM. Useful for local runtime testing.
    """

    def __init__(self, *, name: str = "mock-llm") -> None:
        self.name = name

    def complete(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> str:
        return (
            "Mock response.\n\n"
            f"(model={model or self.name})\n"
            f"Echo: {prompt[:200]}"
        )


@dataclass
class ExecutionContext:
    """
    Runtime-provided context injected into agent code (optionally).

    The key runtime feature: `llm.complete()` performs pre/post governance evaluation.
    """

    run: RunContext
    policy: RuntimePolicy
    decision_engine: DecisionEngine
    trace: TraceCollector = field(default_factory=TraceCollector)
    hooks: list[Hook] = field(default_factory=list)
    llm: LLMClient | None = None

    def emit(self, name: str, payload: Optional[Mapping[str, Any]] = None) -> None:
        self.trace.emit(name, payload)
        ev = HookEvent(name=name, payload=dict(payload or {}))
        for h in self.hooks:
            h.on_event(ev)

    def governed_complete(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> str:
        if self.llm is None:
            raise RuntimeError("ExecutionContext.llm is not configured")

        pre = self.decision_engine.evaluate_text(phase="pre_prompt", text=prompt or "")
        self.emit("governance.decision", pre.to_summary())

        if pre.action.value == "block":
            raise RuntimeError(f"Blocked prompt by policy: {pre.reason}")

        resp = self.llm.complete(prompt, model=model, **kwargs)

        post = self.decision_engine.evaluate_text(phase="post_response", text=resp or "")
        self.emit("governance.decision", post.to_summary())

        if post.action.value == "block":
            raise RuntimeError(f"Blocked response by policy: {post.reason}")

        return resp

