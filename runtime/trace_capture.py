from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class TraceEvent:
    ts: datetime
    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)


class TraceCollector:
    """
    In-memory event capture for a single run.

    Later, a backend can stream these to a control plane.
    """

    def __init__(self) -> None:
        self.events: List[TraceEvent] = []

    def emit(self, name: str, payload: Optional[Mapping[str, Any]] = None) -> None:
        self.events.append(
            TraceEvent(
                ts=datetime.now(timezone.utc),
                name=name,
                payload=dict(payload or {}),
            )
        )

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [
            {"ts": e.ts.isoformat(), "name": e.name, "payload": dict(e.payload)}
            for e in self.events
        ]

