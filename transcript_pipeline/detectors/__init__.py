"""
Pluggable text detectors: secrets, PII, sensitive context, path references.

Primary API::

    from transcript_pipeline.detectors import analyze

    report = analyze(text)
    report.to_summary()
"""

from transcript_pipeline.detectors.orchestrator import (
    analyze,
    clear_detectors,
    list_detectors,
    register_detector,
    reset_default_detectors,
)
from transcript_pipeline.detectors.pii import PIIDetector
from transcript_pipeline.detectors.secrets import SecretDetector, scan_secrets
from transcript_pipeline.detectors.sensitive_context import SensitiveContextDetector
from transcript_pipeline.detectors.sensitive_files import SensitiveFileDetector
from transcript_pipeline.detectors.types import AnalysisReport, DetectorRun, Finding

__all__ = [
    "analyze",
    "register_detector",
    "clear_detectors",
    "reset_default_detectors",
    "list_detectors",
    "AnalysisReport",
    "DetectorRun",
    "Finding",
    "SecretDetector",
    "PIIDetector",
    "SensitiveContextDetector",
    "SensitiveFileDetector",
    "scan_secrets",
]
