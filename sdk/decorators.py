from __future__ import annotations

import functools
from typing import Any, Callable, Mapping, TypeVar, cast

from .client import RuntimeClient, build_client_from_config
from .config import load_config
from .context import AgentMetadata

F = TypeVar("F", bound=Callable[..., Any])

_default_client: RuntimeClient | None = None


def set_default_client(client: RuntimeClient | None) -> None:
    """Override process-wide client used when a decorator does not pass ``client=``."""
    global _default_client
    _default_client = client


def get_default_client() -> RuntimeClient:
    if _default_client is not None:
        return _default_client
    return build_client_from_config(load_config())


def governed_agent(
    policy: str | None = None,
    *,
    name: str | None = None,
    client: RuntimeClient | None = None,
    tags: Mapping[str, str] | None = None,
) -> Callable[[F], F]:
    """
    Mark a callable as a governed agent: attach :class:`AgentMetadata`, wrap execution,
    and delegate to a :class:`RuntimeClient` (no infra is started here).

    The wrapped function gains ``__governance_metadata__`` (an :class:`AgentMetadata`).

    Example::

        @governed_agent(policy=\"default\")
        def my_agent(task: str) -> str:
            return task.upper()
    """

    def decorator(fn: F) -> F:
        cfg = load_config()
        pol = policy if policy is not None else cfg.default_policy
        meta = AgentMetadata(
            policy=pol,
            name=name or fn.__name__,
            module=getattr(fn, "__module__", None),
            qualname=getattr(fn, "__qualname__", None),
            tags=dict(tags or {}),
        )

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            c = client if client is not None else get_default_client()
            return c.run_agent(fn, meta, args, kwargs)

        setattr(wrapper, "__governance_metadata__", meta)
        setattr(wrapper, "__governed__", True)
        return cast(F, wrapper)

    return decorator
