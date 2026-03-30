"""Regression tests for phone, tooling paths, sensitive_files caps, and score capping."""

from __future__ import annotations

import unittest

from governance_engine.detectors.pii.detector import PIIDetector
from governance_engine.detectors.sensitive_context.detector import SensitiveContextDetector
from governance_engine.detectors.sensitive_files.detector import SensitiveFileDetector
from governance_engine.scoring import score_report
from governance_engine.scoring.registry import ScoringRegistry


class TestPhoneGuards(unittest.TestCase):
    def test_ecr_account_id_not_phone(self) -> None:
        d = PIIDetector()
        text = "image: 980921723213.dkr.ecr.us-west-1.amazonaws.com/sim-worker"
        phones = [f for f in d.scan(text) if f.rule_id == "phone"]
        self.assertEqual(phones, [])

    def test_formatted_us_phone_still_detected(self) -> None:
        d = PIIDetector()
        text = "Reach me at (555) 123-4567 after 5pm."
        phones = [f for f in d.scan(text) if f.rule_id == "phone"]
        self.assertEqual(len(phones), 1)


class TestUserHomeTooling(unittest.TestCase):
    def test_cursor_path_suppressed(self) -> None:
        d = SensitiveContextDetector()
        text = 'path="/Users/jane/.cursor/projects/foo/terminals/1.txt"'
        hits = [f for f in d.scan(text) if f.rule_id == "user_home_path"]
        self.assertEqual(hits, [])

    def test_plain_home_path_kept(self) -> None:
        d = SensitiveContextDetector()
        text = "Clone to /Users/jane/Code/acme-repo and run make."
        hits = [f for f in d.scan(text) if f.rule_id == "user_home_path"]
        self.assertEqual(len(hits), 1)


class TestSensitiveFilesCap(unittest.TestCase):
    def test_dotenv_capped(self) -> None:
        d = SensitiveFileDetector()
        text = " ".join(["see `.env`"] * 20)
        dot = [f for f in d.scan(text) if f.rule_id == "dotenv_file"]
        self.assertLessEqual(len(dot), 5)


class TestScorePerRuleCap(unittest.TestCase):
    def test_repeated_rule_contribution_capped(self) -> None:
        from governance_engine.detectors.types import AnalysisReport, DetectorRun, Finding

        findings = [
            Finding(
                detector_id="sensitive_files",
                rule_id="dotenv_file",
                label="x",
                start=i,
                end=i + 1,
                redacted_snippet="",
            )
            for i in range(10)
        ]
        report = AnalysisReport(
            text_length=100,
            runs=[DetectorRun(detector_id="sensitive_files", findings=findings)],
        )
        reg = ScoringRegistry(per_rule_weight_cap_multiplier=2.5)
        pol = score_report(report, registry=reg, alert_threshold=75)
        w = reg.weight_for("sensitive_files", "dotenv_file")
        self.assertAlmostEqual(pol.raw_points, 2.5 * w)
