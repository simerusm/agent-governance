from __future__ import annotations

import re
from typing import List

from transcript_pipeline.detectors.context_detection.metrics import analyze_text_metrics
from transcript_pipeline.detectors.types import Finding

DETECTOR_ID = "context_technical_markers"

_ARCH_KEYWORDS = re.compile(
    r"(?i)\b(?:microservices?|monolith|service\s+mesh|kafka|kubernetes\s+cluster|"
    r"data\s+plane|control\s+plane|on-?call|runbook|postmortem|"
    r"architecture\s+(?:diagram|decision|review))\b"
)


class TechnicalContextMarkersDetector:
    """
    Tracebacks, dense internal paths, architecture/incident language — 
    governance-relevant technical context markers (escalate with other detectors).
    """

    id = DETECTOR_ID

    def scan(self, text: str) -> List[Finding]:
        if not text:
            return []

        m = analyze_text_metrics(text)
        findings: List[Finding] = []

        if m.has_traceback or m.traceback_file_line_hits >= 2:
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="python_traceback_or_file_lines",
                    label="Traceback or repeated File/line patterns — often includes paths and stack context",
                    start=0,
                    end=len(text),
                    redacted_snippet="traceback/stack pattern present",
                    meta={
                        "kind": "technical_marker",
                        "traceback": m.has_traceback,
                        "file_line_hits": m.traceback_file_line_hits,
                    },
                )
            )

        # Dense developer paths (not already user_home_path from sensitive_context — complementary count)
        if m.path_like_count >= 6:
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="dense_internal_paths",
                    label="Many filesystem-style paths in one blob — internal tree exposure signal",
                    start=0,
                    end=len(text),
                    redacted_snippet=f"~{m.path_like_count} path-like tokens",
                    meta={"kind": "technical_marker", "path_like_count": m.path_like_count},
                )
            )

        arch_hits = len(_ARCH_KEYWORDS.findall(text))
        if arch_hits >= 2:
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="architecture_incident_language",
                    label="Architecture / ops / incident language — policy-relevant context (not misuse)",
                    start=0,
                    end=len(text),
                    redacted_snippet=f"{arch_hits} keyword hits",
                    meta={"kind": "technical_marker", "keyword_hits": arch_hits},
                )
            )

        return findings
