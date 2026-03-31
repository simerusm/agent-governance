from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class RuntimePolicy:
    """
    Runtime policy configuration for inline governance.

    - `alert_threshold`: passed to `governance_engine.scoring.score_report(...)`.
    - `block_on_alert`: feature flag; if True, block when `policy.alert` is True.
      Defaults to False (observe-only).
    """

    name: str = "default"
    alert_threshold: float = 75.0
    block_on_alert: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

