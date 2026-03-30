from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from governance_engine.detectors.types import (
    AnalysisReport,
    DetectorRun,
    Finding,
)

from governance_engine.scoring.registry import ScoringRegistry, default_registry


@dataclass
class FindingScoreLine:
    detector_id: str
    rule_id: str
    weight: float


@dataclass
class PolicyScoreResult:
    """Unified governance score (0–cap) and alert decision."""

    score: float
    raw_points: float
    alert: bool
    threshold: float
    finding_lines: List[FindingScoreLine] = field(default_factory=list)
    combo_bonuses: List[Dict[str, Any]] = field(default_factory=list)
    cap_applied: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "raw_points": self.raw_points,
            "alert": self.alert,
            "threshold": self.threshold,
            "cap_applied": self.cap_applied,
            "finding_breakdown": [
                {
                    "detector_id": fl.detector_id,
                    "rule_id": fl.rule_id,
                    "weight": fl.weight,
                }
                for fl in self.finding_lines
            ],
            "combo_bonuses": list(self.combo_bonuses),
        }


def score_report(
    report: AnalysisReport,
    *,
    registry: ScoringRegistry | None = None,
    alert_threshold: float = 75.0,
) -> PolicyScoreResult:
    """
    Sum per-finding weights from registry, apply combo bonuses, cap to ``registry.score_cap``,
    then ``alert = score >= alert_threshold``.
    """
    reg = registry or default_registry()
    lines: List[FindingScoreLine] = []
    raw = 0.0
    cap_mult = reg.per_rule_weight_cap_multiplier
    accrued: Dict[Tuple[str, str], float] = {}

    for f in report.findings:
        w = reg.weight_for(f.detector_id, f.rule_id)
        key = (f.detector_id, f.rule_id)
        prev = accrued.get(key, 0.0)
        if cap_mult is None or cap_mult <= 0:
            room = float("inf")
        else:
            ceiling = cap_mult * w
            room = max(0.0, ceiling - prev)
        contrib = min(w, room)
        accrued[key] = prev + contrib
        lines.append(FindingScoreLine(f.detector_id, f.rule_id, contrib))
        raw += contrib

    combo_applied: List[Dict[str, Any]] = []
    for name, bonus, pred in reg.combos:
        if pred(report):
            raw += bonus
            combo_applied.append({"name": name, "bonus": bonus})

    cap = reg.score_cap
    final = min(cap, raw)
    alert = final >= alert_threshold

    return PolicyScoreResult(
        score=final,
        raw_points=raw,
        alert=alert,
        threshold=alert_threshold,
        finding_lines=lines,
        combo_bonuses=combo_applied,
        cap_applied=cap,
    )


def score_findings_dicts(
    findings: List[Dict[str, Any]],
    *,
    registry: ScoringRegistry | None = None,
    alert_threshold: float = 75.0,
) -> PolicyScoreResult:
    """Score from serialized findings (e.g. stored JSON) without a live AnalysisReport."""
    by_det: Dict[str, List[Finding]] = {}
    for fd in findings:
        det = str(fd.get("detector_id", ""))
        rid = str(fd.get("rule_id", ""))
        f = Finding(
            detector_id=det,
            rule_id=rid,
            label=str(fd.get("label") or ""),
            start=int(fd.get("start", 0)),
            end=int(fd.get("end", 0)),
            redacted_snippet=str(fd.get("redacted_snippet") or ""),
            meta=dict(fd.get("meta") or {}),
        )
        by_det.setdefault(det, []).append(f)

    report = AnalysisReport(
        text_length=0,
        runs=[DetectorRun(detector_id=k, findings=v) for k, v in sorted(by_det.items())],
    )
    return score_report(report, registry=registry, alert_threshold=alert_threshold)
