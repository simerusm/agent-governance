from __future__ import annotations

from typing import List, Protocol, Sequence, runtime_checkable

from transcript_pipeline.detectors.pii import PIIDetector
from transcript_pipeline.detectors.secrets import SecretDetector
from transcript_pipeline.detectors.sensitive_context import SensitiveContextDetector
from transcript_pipeline.detectors.sensitive_files import SensitiveFileDetector
from transcript_pipeline.detectors.types import AnalysisReport, DetectorRun, Finding


@runtime_checkable
class Detector(Protocol):
    """Contract for pluggable detectors."""

    id: str

    def scan(self, text: str) -> Sequence[Finding]:
        ...


def _default_instances() -> List[Detector]:
    # Three focused classifiers + path references (separate package).
    return [
        SecretDetector(),
        PIIDetector(),
        SensitiveContextDetector(),
        SensitiveFileDetector(),
    ]


_REGISTRY: List[Detector] = _default_instances()


def register_detector(detector: Detector, *, first: bool = False) -> None:
    """Add a detector. Use first=True to prepend (e.g. override ordering)."""
    if first:
        _REGISTRY.insert(0, detector)
    else:
        _REGISTRY.append(detector)


def clear_detectors() -> None:
    """Remove all detectors (mainly for tests)."""
    _REGISTRY.clear()


def reset_default_detectors() -> None:
    """Restore built-in detector set."""
    clear_detectors()
    _REGISTRY.extend(_default_instances())


def list_detectors() -> List[str]:
    return [d.id for d in _REGISTRY]


def analyze(text: str, *, detectors: Sequence[Detector] | None = None) -> AnalysisReport:
    """
    Primary entry: run all registered detectors on ``text``.

    Pass ``detectors`` to override the global registry for one call.
    """
    src = detectors if detectors is not None else _REGISTRY
    runs: List[DetectorRun] = []
    for d in src:
        findings = list(d.scan(text or ""))
        runs.append(DetectorRun(detector_id=d.id, findings=findings))
    return AnalysisReport(text_length=len(text or ""), runs=runs)
