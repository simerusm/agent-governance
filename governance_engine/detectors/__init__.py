"""
Pluggable text detectors: secrets, PII, sensitive context, paths, and governance context scope.

Primary API::

    from governance_engine.detectors import analyze

    report = analyze(text)
    report.to_summary()
"""

from governance_engine.detectors.orchestrator import (
    analyze,
    clear_detectors,
    list_detectors,
    register_detector,
    reset_default_detectors,
)
from governance_engine.detectors.context_detection import (
    ExposureScopeDetector,
    PasteStructureDetector,
    TechnicalContextMarkersDetector,
)
from governance_engine.detectors.pii import PIIDetector
from governance_engine.detectors.secrets import SecretDetector, scan_secrets
from governance_engine.detectors.sensitive_context import SensitiveContextDetector
from governance_engine.detectors.sensitive_files import SensitiveFileDetector
from governance_engine.detectors.types import AnalysisReport, DetectorRun, Finding

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
    "ExposureScopeDetector",
    "PasteStructureDetector",
    "TechnicalContextMarkersDetector",
    "scan_secrets",
]
