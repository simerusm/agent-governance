from __future__ import annotations

import re
from typing import List, Pattern, Tuple

from governance_engine.detectors.redact import redact_match
from governance_engine.detectors.types import Finding

# (rule_id, label, regex, flags)
_SECRET_PATTERNS: List[Tuple[str, str, str, int]] = [
    (
        "pem_private_key",
        "PEM private key block",
        r"-----BEGIN[A-Z0-9 -]+PRIVATE KEY-----[\s\S]{0,20000}?-----END[A-Z0-9 -]+PRIVATE KEY-----",
        re.DOTALL | re.MULTILINE,
    ),
    (
        "jwt",
        "JWT-like token",
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_.+-=]{10,}",
        0,
    ),
    (
        "bearer_token",
        "Bearer token",
        r"(?i)\bBearer\s+([A-Za-z0-9._\-+/=]{20,800})\b",
        0,
    ),
    (
        "basic_auth_header",
        "Basic auth header",
        r"(?i)\bBasic\s+([A-Za-z0-9+/=]{20,2000})",
        0,
    ),
    (
        "openai_sk",
        "OpenAI-style API key (sk-…)",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        0,
    ),
    (
        "openai_proj",
        "OpenAI project key (sk-proj-…)",
        r"\bsk-proj-[A-Za-z0-9_-]{20,}\b",
        0,
    ),
    (
        "anthropic_key",
        "Anthropic API key",
        r"\bsk-ant-api\d{2}-[A-Za-z0-9_-]{20,}\b",
        0,
    ),
    (
        "github_pat",
        "GitHub personal access token",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        0,
    ),
    (
        "github_oauth",
        "GitHub OAuth/app token",
        r"\bgho_[A-Za-z0-9]{20,}\b",
        0,
    ),
    (
        "github_user",
        "GitHub user-to-server token",
        r"\bghu_[A-Za-z0-9]{20,}\b",
        0,
    ),
    (
        "github_server",
        "GitHub server-to-server token",
        r"\bghs_[A-Za-z0-9]{20,}\b",
        0,
    ),
    (
        "github_refresh",
        "GitHub refresh token",
        r"\bghr_[A-Za-z0-9]{20,}\b",
        0,
    ),
    (
        "aws_access_key_id",
        "AWS access key id",
        r"\bAKIA[0-9A-Z]{16}\b",
        0,
    ),
    (
        "aws_session_key_id",
        "AWS temporary access key id",
        r"\bASIA[0-9A-Z]{16}\b",
        0,
    ),
    (
        "aws_secret_access_key_like",
        "AWS secret access key (40 char base64)",
        r"(?i)(?:aws_secret_access_key|secret_access_key)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
        0,
    ),
    (
        "google_api_key",
        "Google API key (AIza…)",
        r"\bAIza[0-9A-Za-z\-_]{30,}\b",
        0,
    ),
    (
        "stripe_secret",
        "Stripe secret key",
        r"\bsk_live_[0-9a-zA-Z]{20,}\b",
        0,
    ),
    (
        "stripe_test",
        "Stripe test secret key",
        r"\bsk_test_[0-9a-zA-Z]{20,}\b",
        0,
    ),
    (
        "slack_token",
        "Slack bot/user token",
        r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b",
        0,
    ),
    (
        "twilio_api_key",
        "Twilio API key (SK…)",
        r"\bSK[0-9a-f]{32}\b",
        0,
    ),
    (
        "npm_token",
        "npm token",
        r"\bnpm_[A-Za-z0-9]{36,}\b",
        0,
    ),
    (
        "postgres_url",
        "PostgreSQL URL with credentials",
        r"(?i)\bpostgres(?:ql)?://[^\s/:@]+:[^\s@]+@[^\s]+",
        0,
    ),
    (
        "mysql_url",
        "MySQL URL with credentials",
        r"(?i)\bmysql://[^\s/:@]+:[^\s@]+@[^\s]+",
        0,
    ),
    (
        "mongo_url",
        "MongoDB URL with credentials",
        r"(?i)\bmongodb(?:\+srv)?://[^\s/:@]+:[^\s@]+@[^\s]+",
        0,
    ),
    (
        "redis_url",
        "Redis URL with credentials",
        r"(?i)\bredis://:[^\s@]+@[^\s]+",
        0,
    ),
    (
        "jdbc_postgres",
        "JDBC PostgreSQL with password",
        r"(?i)jdbc:postgresql://[^\s;]+(?:;|\?)[^\s;]*password\s*=\s*[^\s;&]+",
        0,
    ),
    (
        "url_password_param",
        "URL query password parameter",
        r"(?i)[?&]password=([^&\s#\"']{6,})",
        0,
    ),
    (
        "env_sensitive_assignment",
        "Sensitive .env-style assignment",
        r"(?im)^\s*([A-Z0-9_]*(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|ACCESS_KEY|AUTH|BEARER|CREDENTIAL|CLIENT_SECRET|REFRESH_TOKEN)[A-Z0-9_]*)\s*=\s*(\S+)",
        0,
    ),
    (
        "gcp_sa_json_hint",
        "GCP service account JSON field",
        r"(?i)\"private_key\"\s*:\s*\"-----BEGIN",
        0,
    ),
    (
        "azure_connection_string",
        "Azure storage connection string",
        r"(?i)DefaultEndpointsProtocol=https://[^;\s\"']+;AccountName=[^;\s\"']+;AccountKey=[^;\s\"']+",
        0,
    ),
]

DETECTOR_ID = "secrets"


def _compile_patterns() -> List[Tuple[str, str, Pattern[str]]]:
    out: List[Tuple[str, str, Pattern[str]]] = []
    for rule_id, label, pat, flags in _SECRET_PATTERNS:
        out.append((rule_id, label, re.compile(pat, flags)))
    return out


_COMPILED: List[Tuple[str, str, Pattern[str]]] = _compile_patterns()


def _finding_from_match(
    detector_id: str,
    rule_id: str,
    label: str,
    full_text: str,
    m: re.Match[str],
    *,
    value_group: int | None = None,
) -> Finding:
    if value_group is not None:
        inner = m.group(value_group)
        start = m.start(value_group)
        end = m.end(value_group)
        raw = inner
    else:
        start, end = m.start(), m.end()
        raw = full_text[start:end]
    return Finding(
        detector_id=detector_id,
        rule_id=rule_id,
        label=label,
        start=start,
        end=end,
        redacted_snippet=redact_match(raw),
    )


def scan_secrets(text: str) -> List[Finding]:
    """Regex + heuristics for credentials and secret-like material."""
    if not text:
        return []

    findings: List[Finding] = []
    seen_spans: set[Tuple[int, int, str]] = set()

    for rule_id, label, rx in _COMPILED:
        for m in rx.finditer(text):
            if rule_id == "bearer_token" and m.lastindex:
                f = _finding_from_match(
                    DETECTOR_ID, rule_id, label, text, m, value_group=1
                )
            elif rule_id == "basic_auth_header" and m.lastindex:
                f = _finding_from_match(
                    DETECTOR_ID, rule_id, label, text, m, value_group=1
                )
            elif rule_id == "aws_secret_access_key_like" and m.lastindex:
                f = _finding_from_match(
                    DETECTOR_ID, rule_id, label, text, m, value_group=1
                )
            elif rule_id == "url_password_param" and m.lastindex:
                f = _finding_from_match(
                    DETECTOR_ID, rule_id, label, text, m, value_group=1
                )
            elif rule_id == "env_sensitive_assignment" and m.lastindex and m.lastindex >= 2:
                f = _finding_from_match(
                    DETECTOR_ID, rule_id, label, text, m, value_group=2
                )
            else:
                f = _finding_from_match(DETECTOR_ID, rule_id, label, text, m)

            key = (f.start, f.end, f.rule_id)
            if key in seen_spans:
                continue
            seen_spans.add(key)
            findings.append(f)

    return findings


class SecretDetector:
    """API keys, tokens, keys, JWTs, DB URLs, .env assignments, cloud strings."""

    id = DETECTOR_ID

    def scan(self, text: str) -> List[Finding]:
        return scan_secrets(text)
