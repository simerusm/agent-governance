from __future__ import annotations

import re
from typing import List, Tuple

from transcript_pipeline.detectors.types import Finding

DETECTOR_ID = "sensitive_files"

# Path / filename references that often hold secrets (not the secret body).
_PATH_PATTERNS: List[Tuple[str, str, str]] = [
    ("dotenv_file", r"(?i)(?:^|[\s/\"'`])(\.env)(?:\.local|\.production|\.development)?\b"),
    ("aws_credentials_file", r"(?i)(?:~/?|/)[^\s\n]*/?\.aws/credentials\b"),
    ("ssh_private_key_file", r"(?i)\bid_rsa\b|id_ed25519\b|\.pem\b"),
    ("gcp_service_account", r"(?i)service[_-]?account[^\s\n]*\.json\b"),
    ("kubeconfig", r"(?i)\bkubeconfig\b|\.kube/config\b"),
    ("npmrc_auth", r"(?i)\.npmrc\b"),
    ("netrc", r"(?i)\.netrc\b"),
    ("docker_config", r"(?i)config\.json\b.*docker|\.docker/config\.json\b"),
]

_COMPILED = [(rid, re.compile(pat)) for rid, pat in _PATH_PATTERNS]


class SensitiveFileDetector:
    id = DETECTOR_ID

    def scan(self, text: str) -> List[Finding]:
        if not text:
            return []
        out: List[Finding] = []
        seen: set[tuple[int, int, str]] = set()
        for rule_id, rx in _COMPILED:
            for m in rx.finditer(text):
                start, end = m.start(), m.end()
                key = (start, end, rule_id)
                if key in seen:
                    continue
                seen.add(key)
                raw = text[start:end]
                out.append(
                    Finding(
                        detector_id=DETECTOR_ID,
                        rule_id=rule_id,
                        label="Sensitive filename or path reference",
                        start=start,
                        end=end,
                        redacted_snippet=raw[:80] + ("…" if len(raw) > 80 else ""),
                        meta={"kind": "path_reference"},
                    )
                )
        return out
