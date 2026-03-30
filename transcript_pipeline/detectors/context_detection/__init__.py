"""
Governance-oriented context detection: scope of internal technical exposure,
paste structure, and technical markers — not 'large code = bad'.

Use with secrets/PII/sensitive_context for escalation, not standalone verdicts.
"""

from transcript_pipeline.detectors.context_detection.exposure_scope import (
    ExposureScopeDetector,
)
from transcript_pipeline.detectors.context_detection.paste_structure import (
    PasteStructureDetector,
)
from transcript_pipeline.detectors.context_detection.technical_markers import (
    TechnicalContextMarkersDetector,
)

__all__ = [
    "ExposureScopeDetector",
    "PasteStructureDetector",
    "TechnicalContextMarkersDetector",
]
