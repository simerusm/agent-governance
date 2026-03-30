from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from governance_engine.detectors.types import AnalysisReport

_BUILTIN_RULE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "secrets": {
        "*": 18.0,
        "pem_private_key": 38.0,
        "jwt": 32.0,
        "bearer_token": 30.0,
        "basic_auth_header": 28.0,
        "env_sensitive_assignment": 26.0,
        "aws_secret_access_key_like": 30.0,
        "aws_access_key_id": 26.0,
        "aws_session_key_id": 24.0,
        "azure_connection_string": 32.0,
        "gcp_sa_json_hint": 30.0,
        "postgres_url": 28.0,
        "mysql_url": 28.0,
        "mongo_url": 28.0,
        "redis_url": 24.0,
        "jdbc_postgres": 26.0,
        "url_password_param": 22.0,
        "github_pat": 28.0,
        "openai_sk": 24.0,
        "openai_proj": 24.0,
        "anthropic_key": 24.0,
        "google_api_key": 24.0,
        "stripe_secret": 26.0,
        "stripe_test": 12.0,
        "slack_token": 22.0,
        "npm_token": 18.0,
    },
    "pii": {
        "*": 12.0,
        "credit_card_luhn": 34.0,
        "ssn": 32.0,
        "labeled_account_id": 16.0,
        "us_street_address": 18.0,
        "email": 8.0,
        "phone": 14.0,
        "cust_prefix": 14.0,
        "acct_numeric": 12.0,
    },
    "sensitive_context": {
        "*": 8.0,
        "private_ip": 14.0,
        "internal_hostname": 12.0,
        "export_dump_pattern": 16.0,
        "keyword_confidential": 14.0,
        "keyword_internal_only": 12.0,
        "keyword_proprietary": 12.0,
        "k8s_secret_resource": 18.0,
        "deployment_config": 12.0,
        "auth_config_filename": 14.0,
        "user_home_path": 6.0,
        "git_ssh_remote": 10.0,
        "github_repo_path": 10.0,
    },
    "sensitive_files": {
        "*": 12.0,
        "dotenv_file": 16.0,
        "aws_credentials_file": 18.0,
        "ssh_private_key_file": 16.0,
        "gcp_service_account": 16.0,
        "kubeconfig": 14.0,
    },
    "context_exposure_scope": {
        "*": 10.0,
        "small_snippet": 6.0,
        "moderate_internal_context": 14.0,
        "broad_internal_context_transfer": 26.0,
    },
    "context_paste_structure": {
        "*": 10.0,
        "many_fenced_blocks": 16.0,
        "many_attachment_style_refs": 18.0,
        "multi_snippet_paste": 12.0,
        "labeled_file_sections": 14.0,
    },
    "context_technical_markers": {
        "*": 8.0,
        "python_traceback_or_file_lines": 14.0,
        "dense_internal_paths": 12.0,
        "architecture_incident_language": 10.0,
    },
}


def _rule_set(report: AnalysisReport) -> set[str]:
    return {f.rule_id for f in report.findings}


def _has_detector(report: AnalysisReport, detector_id: str) -> bool:
    return any(f.detector_id == detector_id for f in report.findings)


ComboDef = Tuple[str, float, Callable[[AnalysisReport], bool]]


def _combo_broad_plus_secrets(r: AnalysisReport) -> bool:
    if "broad_internal_context_transfer" not in _rule_set(r):
        return False
    return _has_detector(r, "secrets")


def _combo_broad_plus_pii(r: AnalysisReport) -> bool:
    if "broad_internal_context_transfer" not in _rule_set(r):
        return False
    return _has_detector(r, "pii")


def _combo_broad_plus_sensitive_files(r: AnalysisReport) -> bool:
    if "broad_internal_context_transfer" not in _rule_set(r):
        return False
    return _has_detector(r, "sensitive_files")


def _combo_secrets_plus_pii(r: AnalysisReport) -> bool:
    return _has_detector(r, "secrets") and _has_detector(r, "pii")


def _combo_secrets_plus_dotenv_path(r: AnalysisReport) -> bool:
    if not _has_detector(r, "secrets"):
        return False
    return any(
        f.detector_id == "sensitive_files" and f.rule_id == "dotenv_file" for f in r.findings
    )


_BUILTIN_COMBOS: List[ComboDef] = [
    ("broad_context_plus_secrets", 22.0, _combo_broad_plus_secrets),
    ("broad_context_plus_pii", 20.0, _combo_broad_plus_pii),
    ("broad_context_plus_sensitive_paths", 16.0, _combo_broad_plus_sensitive_files),
    ("secrets_plus_pii", 18.0, _combo_secrets_plus_pii),
    ("secrets_plus_dotenv_reference", 14.0, _combo_secrets_plus_dotenv_path),
]


@dataclass
class ScoringRegistry:
    """
    Per-(detector_id, rule_id) weights. New detectors: add a block with ``"*"`` default,
    or rely on ``global_fallback``. New rules: add key under detector or use ``"*"``.

    ``per_rule_weight_cap_multiplier`` limits how much repeated hits of the same rule can
    add (total for that rule ≤ multiplier × that rule's weight). Set ≤ 0 to disable.
    """

    rule_weights: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: deepcopy(_BUILTIN_RULE_WEIGHTS)
    )
    detector_fallback: Dict[str, float] = field(default_factory=dict)
    global_fallback: float = 10.0
    combos: List[ComboDef] = field(default_factory=lambda: list(_BUILTIN_COMBOS))
    score_cap: float = 100.0
    # Max total score contribution per (detector_id, rule_id) = multiplier × single-rule weight.
    per_rule_weight_cap_multiplier: float = 2.5

    def merge_rule_weights(self, patch: Dict[str, Dict[str, float]]) -> None:
        for det, rules in patch.items():
            self.rule_weights.setdefault(det, {})
            self.rule_weights[det].update(rules)

    def weight_for(self, detector_id: str, rule_id: str) -> float:
        dm = self.rule_weights.get(detector_id)
        if dm:
            if rule_id in dm:
                return float(dm[rule_id])
            if "*" in dm:
                return float(dm["*"])
        if detector_id in self.detector_fallback:
            return float(self.detector_fallback[detector_id])
        return float(self.global_fallback)


def default_registry() -> ScoringRegistry:
    return ScoringRegistry()
