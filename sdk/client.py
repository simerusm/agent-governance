from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Protocol, runtime_checkable

from .context import AgentMetadata, RunContext, run_context


@runtime_checkable
class RuntimeClient(Protocol):
    """
    Pluggable execution boundary. Implementations may call the function locally and/or
    notify a control plane. They must not start servers or provision infra.
    """

    def run_agent(
        self,
        fn: Callable[..., Any],
        metadata: AgentMetadata,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        ...


class DefaultRuntimeClient:
    """
    Local execution only: sets :class:`RunContext`, invokes ``fn``, returns result.
    Use in tests and offline development.
    """

    def run_agent(
        self,
        fn: Callable[..., Any],
        metadata: AgentMetadata,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        ctx = RunContext.new(metadata.policy, metadata.name)
        with run_context(ctx):
            return fn(*args, **kwargs)


class RuntimeLayerClient:
    """
    Runtime-backed client: delegates run lifecycle + governance decisions to `runtime/`.

    This is the intended bridge from the thin SDK decorator to the richer runtime layer.
    """

    def __init__(self, runner: Any) -> None:
        self._runner = runner

    def run_agent(
        self,
        fn: Callable[..., Any],
        metadata: AgentMetadata,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        return self._runner.run_agent(fn, metadata, args, kwargs)


class HttpReportingClient:
    """
    Executes the function locally (same process), then POSTs a minimal run report to
    ``control_plane_url`` if configured. Request bodies avoid raw user payloads by default.
    """

    def __init__(
        self,
        *,
        control_plane_url: str | None,
        api_key: str | None = None,
        runs_path: str = "/v1/runs",
        timeout_s: float = 10.0,
        inner: RuntimeClient | None = None,
    ) -> None:
        self._base = (control_plane_url or "").rstrip("/")
        self._api_key = api_key
        self._runs_path = runs_path if runs_path.startswith("/") else f"/{runs_path}"
        self._timeout_s = timeout_s
        self._inner = inner or DefaultRuntimeClient()

    def run_agent(
        self,
        fn: Callable[..., Any],
        metadata: AgentMetadata,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        t0 = time.perf_counter()
        err: str | None = None
        status = "ok"
        try:
            return self._inner.run_agent(fn, metadata, args, kwargs)
        except BaseException as e:
            status = "error"
            err = f"{type(e).__name__}: {e}"
            raise
        finally:
            if self._base:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                self._post_report(
                    metadata=metadata,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    error=err,
                )

    def _post_report(
        self,
        *,
        metadata: AgentMetadata,
        status: str,
        elapsed_ms: int,
        error: str | None,
    ) -> None:
        url = f"{self._base}{self._runs_path}"
        body = {
            "policy": metadata.policy,
            "agent": metadata.name,
            "module": metadata.module,
            "qualname": metadata.qualname,
            "tags": dict(metadata.tags),
            "status": status,
            "elapsed_ms": elapsed_ms,
            "error": error,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        if self._api_key:
            req.add_header("Authorization", f"Bearer {self._api_key}")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                resp.read()
        except (urllib.error.URLError, OSError):
            # Control plane optional / may be down — do not fail the agent
            pass


def build_client_from_config(config: Any) -> RuntimeClient:
    """Factory using :class:`sdk.config.GovernanceConfig`."""
    from .config import GovernanceConfig

    if not isinstance(config, GovernanceConfig):
        raise TypeError("config must be GovernanceConfig")
    if config.control_plane_url:
        return HttpReportingClient(
            control_plane_url=config.control_plane_url,
            api_key=config.api_key,
        )
    return DefaultRuntimeClient()
