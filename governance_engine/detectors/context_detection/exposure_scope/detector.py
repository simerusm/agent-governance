from __future__ import annotations

from typing import List

from governance_engine.detectors.context_detection.metrics import (
    analyze_text_metrics,
    classify_exposure_tier,
)
from governance_engine.detectors.types import Finding

DETECTOR_ID = "context_exposure_scope"


class ExposureScopeDetector:
    """
    Estimates scope of internal technical context (chars, fenced code volume).
    Outputs governance tiers — not 'large code = violation'.
    """

    id = DETECTOR_ID

    def scan(self, text: str) -> List[Finding]:
        if not text or not text.strip():
            return []

        m = analyze_text_metrics(text)
        rule_id, label = classify_exposure_tier(m)
        if rule_id == "none":
            return []

        meta = {
            "tier": rule_id,
            "kind": "governance_scope",
            "chars": m.char_count,
            "lines": m.line_count,
            "code_fence_count": m.code_fence_count,
            "fenced_code_lines": m.fenced_code_lines,
            "at_reference_count": m.at_reference_count,
            "path_like_count": m.path_like_count,
        }
        return [
            Finding(
                detector_id=DETECTOR_ID,
                rule_id=rule_id,
                label=label,
                start=0,
                end=len(text),
                redacted_snippet=f"{rule_id} (chars={m.char_count}, fences={m.code_fence_count}, "
                f"fenced_lines≈{m.fenced_code_lines})",
                meta=meta,
            )
        ]
