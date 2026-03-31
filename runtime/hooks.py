from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class HookEvent:
    """
    Lightweight hook payload. Keep this control-plane friendly (no raw secrets by default).
    """

    name: str
    payload: Mapping[str, Any]


@runtime_checkable
class Hook(Protocol):
    """
    Lifecycle hooks for governed runs.

    Hooks are for observability/integration; they should not decide allow/block directly.
    """

    def on_event(self, event: HookEvent) -> None:
        ...

