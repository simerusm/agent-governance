from __future__ import annotations

import inspect
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Protocol, runtime_checkable

from sdk.context import AgentMetadata, RunContext, run_context

from .decision_engine import DecisionEngine
from .execution_context import ExecutionContext, LLMClient, MockLLM
from .hooks import Hook
from .policies import RuntimePolicy


@runtime_checkable
class ExecutionBackend(Protocol):
    """
    Abstract execution backend: local, docker, remote sandbox, etc.

    The runtime layer passes a callable to this backend. A future backend may serialize
    code+inputs and execute elsewhere; local backend just calls it.
    """

    def run_callable(self, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        ...


class LocalExecutionBackend:
    def run_callable(self, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        return fn(*args, **kwargs)


class CloudExecutionBackend:
    """
    Placeholder backend for future gVisor/pods/sandbox integration.
    """

    def __init__(self, *, endpoint: str | None = None) -> None:
        self.endpoint = endpoint

    def run_callable(self, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        raise NotImplementedError(
            "CloudExecutionBackend is a stub. "
            "Integrate your sandbox execution folder and call it from here."
        )


def _maybe_inject_execution_context(
    fn: Callable[..., Any],
    kwargs: dict[str, Any],
    ctx: ExecutionContext,
) -> dict[str, Any]:
    """
    If the function accepts `execution_context` or `ctx`, inject the context.
    Otherwise, do nothing (keeps existing functions working).
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return kwargs

    if "execution_context" in sig.parameters and "execution_context" not in kwargs:
        return {**kwargs, "execution_context": ctx}
    if "ctx" in sig.parameters and "ctx" not in kwargs:
        return {**kwargs, "ctx": ctx}
    return kwargs


@dataclass
class GovernedRunner:
    """
    Main runtime entrypoint: defines run lifecycle and policy evaluation.
    """

    backend: ExecutionBackend = LocalExecutionBackend()
    policy: RuntimePolicy = RuntimePolicy()
    hooks: list[Hook] = None  # type: ignore[assignment]
    llm: LLMClient = None  # type: ignore[assignment]
    # Debug/UX: populated after each run (best-effort, overwritten each run).
    last_trace: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.hooks is None:
            self.hooks = []
        if self.llm is None:
            self.llm = MockLLM()
        if self.last_trace is None:
            self.last_trace = []

    def run_agent(
        self,
        fn: Callable[..., Any],
        metadata: AgentMetadata,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        run = RunContext.new(metadata.policy, metadata.name)
        engine = DecisionEngine(self.policy)
        exec_ctx = ExecutionContext(
            run=run,
            policy=self.policy,
            decision_engine=engine,
            hooks=list(self.hooks),
            llm=self.llm,
        )
        # Convention: agent code calls `execution_context.governed_complete(...)`.

        exec_ctx.emit("run.start", {"agent": metadata.name, "policy": metadata.policy})
        t0 = time.perf_counter()
        try:
            with run_context(run):
                call_kwargs = _maybe_inject_execution_context(fn, kwargs, exec_ctx)
                out = self.backend.run_callable(fn, args, call_kwargs)
            exec_ctx.emit("run.end", {"status": "ok", "elapsed_ms": int((time.perf_counter() - t0) * 1000)})
            self.last_trace = exec_ctx.trace.to_dicts()
            return out
        except BaseException as e:
            exec_ctx.emit(
                "run.end",
                {
                    "status": "error",
                    "error": f"{type(e).__name__}: {e}",
                    "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                },
            )
            self.last_trace = exec_ctx.trace.to_dicts()
            raise

