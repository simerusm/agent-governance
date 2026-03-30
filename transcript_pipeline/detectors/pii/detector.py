from __future__ import annotations

import re
from typing import List, Set, Tuple

from transcript_pipeline.detectors.pii.validators import luhn_valid, ssn_plausible
from transcript_pipeline.detectors.redact import redact_match
from transcript_pipeline.detectors.types import Finding

DETECTOR_ID = "pii"

# Email (practical, not RFC-complete)
_EMAIL_RX = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# US-centric phone + simple international
_PHONE_RX = re.compile(
    r"(?:(?:\+|00)[1-9]\d{0,3}[\s.\-]?)?"
    r"(?:\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}|"
    r"\d{3}[\s.\-]\d{4}[\s.\-]\d{4})\b"
)

# Hostname / cloud context: phone-like digit runs inside these are usually account ids, not phones.
_PHONE_CLOUD_MARKERS = (
    "amazonaws.com",
    ".dkr.ecr.",
    "arn:aws:",
    "console.aws.amazon.com",
    "microsoftonline.com",
    "storage.googleapis.com",
    "googleapis.com",
    "azure.com",
    "cloud.google.com",
)


def _phone_likely_false_positive(text: str, m: re.Match, raw: str) -> bool:
    start, end = m.start(), m.end()
    lo = max(0, start - 72)
    hi = min(len(text), end + 72)
    window = text[lo:hi].lower()
    if any(marker in window for marker in _PHONE_CLOUD_MARKERS):
        return True

    i = start
    while i > 0 and text[i - 1].isdigit():
        i -= 1
    j = end
    while j < len(text) and text[j].isdigit():
        j += 1
    run_len = j - i
    has_phone_formatting = bool(re.search(r"[\s.\-+()]", raw))
    if run_len > 10 and not has_phone_formatting:
        return True
    return False

_SSN_RX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Candidate PAN: groups of 4 digits, optional separators, 13-19 digits total
_CC_CANDIDATE = re.compile(
    r"\b(?:\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,7}|\d{13,19})\b"
)

# US-style street line (heuristic)
_ADDRESS_RX = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9.'\-\s]{2,35}\s+"
    r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Drive|Dr\.?|"
    r"Lane|Ln\.?|Boulevard|Blvd\.?|Court|Ct\.?|Way|Place|Pl\.?)\b",
    re.IGNORECASE,
)

# Labeled account / customer identifiers
_ACCOUNT_LABELED = re.compile(
    r"(?i)\b(?:customer|account|member|client|subscriber)[_\- ]?"
    r"(?:id|no|number|#)\s*[:=#\s]+\s*([A-Za-z0-9][A-Za-z0-9\-]{3,40})\b"
)

# Patterned IDs (tune per org)
_PATTERN_IDS = [
    ("cust_prefix", re.compile(r"\bCUS-[A-Z0-9]{4,}\b", re.IGNORECASE)),
    ("acct_numeric", re.compile(r"\b(?:ACCT|ACC)[-#]?\s*(\d{6,14})\b", re.IGNORECASE)),
]


def _dedupe_spans(
    findings: List[Finding],
) -> List[Finding]:
    seen: Set[Tuple[int, int, str]] = set()
    out: List[Finding] = []
    for f in findings:
        k = (f.start, f.end, f.rule_id)
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return sorted(out, key=lambda x: (x.start, x.end))


class PIIDetector:
    """Emails, phones, SSN-shaped strings, PAN (Luhn), addresses, labeled IDs."""

    id = DETECTOR_ID

    def scan(self, text: str) -> List[Finding]:
        if not text:
            return []
        findings: List[Finding] = []

        for m in _EMAIL_RX.finditer(text):
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="email",
                    label="Email address",
                    start=m.start(),
                    end=m.end(),
                    redacted_snippet=redact_match(m.group(0)),
                )
            )

        for m in _PHONE_RX.finditer(text):
            raw = m.group(0)
            digits = re.sub(r"\D", "", raw)
            if len(digits) < 10:
                continue
            if _phone_likely_false_positive(text, m, raw):
                continue
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="phone",
                    label="Phone number (pattern)",
                    start=m.start(),
                    end=m.end(),
                    redacted_snippet=redact_match(raw),
                )
            )

        for m in _SSN_RX.finditer(text):
            if not ssn_plausible(m.group(0)):
                continue
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="ssn",
                    label="SSN-shaped number",
                    start=m.start(),
                    end=m.end(),
                    redacted_snippet="***-**-****",
                    meta={"validated": "partial"},
                )
            )

        for m in _CC_CANDIDATE.finditer(text):
            pan = re.sub(r"\D", "", m.group(0))
            if len(pan) < 13 or len(pan) > 19:
                continue
            if not luhn_valid(pan):
                continue
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="credit_card_luhn",
                    label="Credit card number (Luhn match)",
                    start=m.start(),
                    end=m.end(),
                    redacted_snippet=redact_match(pan),
                )
            )

        for m in _ADDRESS_RX.finditer(text):
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="us_street_address",
                    label="US-style street address (heuristic)",
                    start=m.start(),
                    end=m.end(),
                    redacted_snippet=m.group(0)[:40] + "…",
                )
            )

        for m in _ACCOUNT_LABELED.finditer(text):
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="labeled_account_id",
                    label="Labeled customer/account id",
                    start=m.start(1),
                    end=m.end(1),
                    redacted_snippet=redact_match(m.group(1)),
                )
            )

        for rule_id, rx in _PATTERN_IDS:
            for m in rx.finditer(text):
                g = 1 if m.lastindex else 0
                if g:
                    start, end = m.start(1), m.end(1)
                    snippet = m.group(1)
                else:
                    start, end = m.start(), m.end()
                    snippet = m.group(0)
                findings.append(
                    Finding(
                        detector_id=DETECTOR_ID,
                        rule_id=rule_id,
                        label="Patterned account/customer id",
                        start=start,
                        end=end,
                        redacted_snippet=redact_match(snippet),
                    )
                )

        return _dedupe_spans(findings)
