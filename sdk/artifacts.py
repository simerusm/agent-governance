from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .context import current_run_context


@dataclass(frozen=True)
class ArtifactRef:
    """
    Opaque handle for something produced or consumed during a run (file path, URI, blob id).
    The runtime / control plane interprets ``kind`` and ``uri``.
    """

    kind: str
    uri: str
    name: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)


def record_artifact(ref: ArtifactRef) -> None:
    """Attach an artifact to the current :class:`~sdk.context.RunContext`, if any."""
    ctx = current_run_context()
    if ctx is None:
        return
    ctx.artifact_refs.append(ref)
