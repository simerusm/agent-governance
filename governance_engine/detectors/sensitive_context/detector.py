from __future__ import annotations

import re
from typing import List, Pattern, Tuple

from governance_engine.detectors.types import Finding

DETECTOR_ID = "sensitive_context"

# (rule_id, label, pattern, flags)
_CONTEXT_PATTERNS: List[Tuple[str, str, str, int]] = [
    (
        "keyword_confidential",
        "Confidentiality keyword",
        r"(?i)\b(confidential|confidentiality|company\s+confidential|strictly\s+confidential)\b",
        0,
    ),
    (
        "keyword_internal_only",
        "Internal-only keyword",
        r"(?i)\b(internal\s+only|internal\s+use|not\s+for\s+(?:external|public)\s+distribution|"
        r"do\s+not\s+(?:share|distribute)\s+externally)\b",
        0,
    ),
    (
        "keyword_proprietary",
        "Proprietary / NDA language",
        r"(?i)\b(proprietary|trade\s+secret|nda\b|non[-\s]?disclosure|"
        r"attorney[-\s]?client\s+privilege)\b",
        0,
    ),
    (
        "auth_config_filename",
        "Auth/config filename reference",
        r"(?i)(?:^|[\s\"'`/])(?:auth\.json|secrets\.yaml|secrets\.yml|application[-.]?ya?ml|"
        r"settings\.py|config\.secrets|vault\.hcl)\b",
        0,
    ),
    (
        "deployment_config",
        "Deployment / infra config reference",
        r"(?i)\b(?:docker[- ]compose\.ya?ml|kubernetes|k8s\b|helmfile\.ya?ml|"
        r"terraform\.tfvars|\.tfstate\b|pulumi\.ya?ml|ansible\.cfg|inventory\.ini)\b",
        0,
    ),
    (
        "k8s_secret_resource",
        "Kubernetes Secret manifest hint",
        r"(?i)kind\s*:\s*Secret\b|secretKeyRef|valueFrom\s*:\s*secretKeyRef",
        0,
    ),
    (
        "internal_hostname",
        "Likely internal hostname",
        r"(?i)\b[a-z0-9][a-z0-9.\-]{0,50}\.(?:internal|corp|local|lan|intranet|private)\b",
        0,
    ),
    (
        "private_ip",
        "Private IPv4 address",
        r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3})\b",
        0,
    ),
    (
        "user_home_path",
        "User home / developer path (repo context)",
        r"(?:/Users/[^/\s]+/|/home/[^/\s]+/|C:\\Users\\[^\\\s]+\\)",
        0,
    ),
    (
        "git_ssh_remote",
        "Git SSH remote",
        r"\bgit@[a-z0-9.\-]+:[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(?:\.git)?\b",
        0,
    ),
    (
        "github_repo_path",
        "GitHub repo URL path",
        r"(?i)github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(?:\.git)?\b",
        0,
    ),
    (
        "export_dump_pattern",
        "Export / dump / backup filename pattern",
        r"(?i)\b(?:customer|user|account)?_?(?:export|dump|backup|full_?export)\.(?:csv|json|sql|gz|zip)\b|"
        r"\b(?:database\s+)?(?:dump|backup)\.(?:sql|dump)\b",
        0,
    ),
    (
        "log_tail_pattern",
        "Log / audit file pattern",
        r"(?i)\b(?:access|application|audit|error|combined)\.(?:log|log\.\d+)\b",
        0,
    ),
]


def _compile() -> List[Tuple[str, str, Pattern[str]]]:
    return [(rid, lab, re.compile(pat, fl)) for rid, lab, pat, fl in _CONTEXT_PATTERNS]


_COMPILED = _compile()

# `/Users/foo/` inside IDE metadata (Cursor, etc.) — low governance value.
_TOOLING_PATH_AFTER_HOME = re.compile(
    r"[/\\]\.cursor[/\\]|\.cursor[/\\]projects|[/\\]\.vscode[/\\]|"
    r"AppData[/\\]Local[/\\]Programs[/\\]cursor",
    re.IGNORECASE,
)


def _user_home_path_is_tooling_metadata(text: str, m: re.Match) -> bool:
    tail = text[m.start() : min(len(text), m.end() + 160)]
    return bool(_TOOLING_PATH_AFTER_HOME.search(tail))


class SensitiveContextDetector:
    """Internal/confidential context: language, configs, hosts, paths, exports."""

    id = DETECTOR_ID

    def scan(self, text: str) -> List[Finding]:
        if not text:
            return []
        out: List[Finding] = []
        seen: set[tuple[int, int, str]] = set()
        for rule_id, label, rx in _COMPILED:
            for m in rx.finditer(text):
                key = (m.start(), m.end(), rule_id)
                if key in seen:
                    continue
                if rule_id == "user_home_path" and _user_home_path_is_tooling_metadata(
                    text, m
                ):
                    continue
                seen.add(key)
                raw = m.group(0)
                out.append(
                    Finding(
                        detector_id=DETECTOR_ID,
                        rule_id=rule_id,
                        label=label,
                        start=m.start(),
                        end=m.end(),
                        redacted_snippet=(raw[:100] + "…") if len(raw) > 100 else raw,
                        meta={"kind": "context"},
                    )
                )
        return sorted(out, key=lambda f: (f.start, f.end))
