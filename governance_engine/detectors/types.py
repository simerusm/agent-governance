from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Finding:
    """Single match from a detector (values should be safe to log — use redaction)."""

    detector_id: str
    rule_id: str
    label: str
    start: int
    end: int
    redacted_snippet: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectorRun:
    """Output of one detector implementation."""

    detector_id: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0


@dataclass
class AnalysisReport:
    """Aggregated result from the orchestrator."""

    text_length: int
    runs: List[DetectorRun] = field(default_factory=list)

    @property
    def findings(self) -> List[Finding]:
        out: List[Finding] = []
        for r in self.runs:
            out.extend(r.findings)
        return sorted(out, key=lambda f: (f.start, f.end, f.rule_id))

    @property
    def by_detector(self) -> Dict[str, List[Finding]]:
        d: Dict[str, List[Finding]] = {}
        for f in self.findings:
            d.setdefault(f.detector_id, []).append(f)
        return d

    def to_summary(self) -> Dict[str, Any]:
        return {
            "text_length": self.text_length,
            "detector_count": len(self.runs),
            "finding_count": len(self.findings),
            "detectors_with_hits": sorted(
                {r.detector_id for r in self.runs if r.has_findings}
            ),
            "rule_hits": sorted({f.rule_id for f in self.findings}),
        }
