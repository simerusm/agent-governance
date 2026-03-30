"""Shared heuristics for governance / internal-context scope (not 'large = bad')."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

# Markdown fenced blocks (optional language line after opening ```)
_FENCE = re.compile(r"```[a-zA-Z0-9]*\s*\n([\s\S]*?)```", re.MULTILINE)
_AT_REF = re.compile(r"@[\w./\\-]+")
_PATH_LIKE = re.compile(
    r"(?:/Users/[^\s]+|/home/[^\s]+|C:\\Users\\[^\s\\]+|[A-Za-z]:\\[^\s]+)"
)
_TRACEBACK_START = re.compile(
    r"(?i)^Traceback \(most recent call last\):", re.MULTILINE
)
_FILE_LINE = re.compile(r'File "[^"]+", line \d+', re.MULTILINE)


@dataclass
class ContextMetrics:
    char_count: int
    line_count: int
    code_fence_count: int
    fenced_code_lines: int
    at_reference_count: int
    path_like_count: int
    has_traceback: bool
    traceback_file_line_hits: int


def analyze_text_metrics(text: str) -> ContextMetrics:
    if not text:
        return ContextMetrics(0, 0, 0, 0, 0, 0, False, 0)

    lines = text.count("\n") + 1
    fences = list(_FENCE.finditer(text))
    fenced_lines = 0
    for m in fences:
        body = m.group(1) if m.lastindex else ""
        fenced_lines += body.count("\n") + (1 if body.strip() else 0)

    return ContextMetrics(
        char_count=len(text),
        line_count=lines,
        code_fence_count=len(fences),
        fenced_code_lines=fenced_lines,
        at_reference_count=len(_AT_REF.findall(text)),
        path_like_count=len(_PATH_LIKE.findall(text)),
        has_traceback=bool(_TRACEBACK_START.search(text)),
        traceback_file_line_hits=len(_FILE_LINE.findall(text)),
    )


def classify_exposure_tier(m: ContextMetrics) -> Tuple[str, str]:
    """
    Return (rule_id, human_label) for governance-relevant exposure scope.
    Tiers: none (caller may skip), small_snippet, moderate_internal_context,
    broad_internal_context_transfer.
    """
    c, fl, nf, fcl = m.char_count, m.line_count, m.code_fence_count, m.fenced_code_lines
    atc, plc = m.at_reference_count, m.path_like_count

    # Broad: substantial manual context transfer (high char, many fences/lines, many refs)
    if (
        c >= 18_000
        or fcl >= 220
        or nf >= 6
        or (nf >= 4 and fcl >= 120)
        or atc >= 10
        or (c >= 12_000 and (nf >= 3 or atc >= 6))
    ):
        return (
            "broad_internal_context_transfer",
            "Substantial internal technical context by volume, structure, or refs — "
            "governance visibility signal (not a judgment of misuse).",
        )

    # Moderate: noteworthy but common in Cursor for real work
    if (
        c >= 4_500
        or fcl >= 45
        or nf >= 3
        or atc >= 4
        or (nf >= 2 and fcl >= 25)
        or (c >= 3_000 and atc >= 2)
        or fl >= 120
    ):
        return (
            "moderate_internal_context",
            "Moderate amount of technical context (length, fenced code, or file refs) — "
            "may warrant review combined with policy and destination.",
        )

    # Small: light informational — only meaningful above trivial size
    if c >= 450 or fcl >= 12 or nf >= 1 or atc >= 1 or fl >= 25:
        return (
            "small_snippet",
            "Limited technical context in this interaction — usually normal; "
            "use as low-severity visibility only.",
        )

    return ("none", "")
