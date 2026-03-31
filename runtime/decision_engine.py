from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from governance_engine.detectors import AnalysisReport, Finding, analyze
from governance_engine.scoring import PolicyScoreResult, score_report

from .policies import RuntimePolicy


class DecisionAction(str, Enum):
    allow = "allow"
    block = "block"
    warn = "warn"


@dataclass(frozen=True)
class Decision:
    phase: str  # e.g. pre_prompt, post_response
    action: DecisionAction
    report: AnalysisReport
    policy_score: PolicyScoreResult
    reason: str | None = None

    def to_summary(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "action": self.action.value,
            "score": self.policy_score.score,
            "alert": self.policy_score.alert,
            "threshold": self.policy_score.threshold,
            "finding_count": len(self.report.findings),
            "rule_hits": sorted({f.rule_id for f in self.report.findings}),
        }


class DecisionEngine:
    """
    Inline governance evaluation using `governance_engine` building blocks.

    This is intentionally synchronous and local. A future control plane can override it
    (e.g., remote policy evaluation).
    """

    def __init__(self, policy: RuntimePolicy) -> None:
        self.policy = policy

    def evaluate_text(self, *, phase: str, text: str) -> Decision:
        rep = analyze(text or "")
        pol = score_report(rep, alert_threshold=self.policy.alert_threshold)

        # Observe-only by default. Optional feature flag to block on alert.
        if pol.alert and self.policy.block_on_alert:
            return Decision(
                phase=phase,
                action=DecisionAction.block,
                report=rep,
                policy_score=pol,
                reason=f"policy.alert==True (score >= {self.policy.alert_threshold})",
            )

        if pol.alert and not self.policy.block_on_alert:
            return Decision(
                phase=phase,
                action=DecisionAction.warn,
                report=rep,
                policy_score=pol,
                reason=f"policy.alert==True (score >= {self.policy.alert_threshold})",
            )

        return Decision(
            phase=phase,
            action=DecisionAction.allow,
            report=rep,
            policy_score=pol,
            reason=None,
        )

