"""
Policy / scoring layer: combine detector findings into a capped score and optional alert.

Tune weights in ``registry.ScoringRegistry``; new detectors/rules fall back to ``global_fallback``
or per-detector ``"*"`` weights.
"""

from transcript_pipeline.scoring.engine import (
    FindingScoreLine,
    PolicyScoreResult,
    score_findings_dicts,
    score_report,
)
from transcript_pipeline.scoring.registry import ScoringRegistry, default_registry

__all__ = [
    "FindingScoreLine",
    "PolicyScoreResult",
    "ScoringRegistry",
    "default_registry",
    "score_report",
    "score_findings_dicts",
]
