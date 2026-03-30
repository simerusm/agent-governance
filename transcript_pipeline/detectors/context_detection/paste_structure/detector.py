from __future__ import annotations

import re
from typing import List

from transcript_pipeline.detectors.context_detection.metrics import analyze_text_metrics
from transcript_pipeline.detectors.types import Finding

DETECTOR_ID = "context_paste_structure"

# Distinct "file" or module hints inside pasted blocks (not secrets)
_MULTI_FILE_HINT = re.compile(
    r"(?i)(?:^|\n)\s*(?:#|//|/\*)\s*(?:file|path|source):\s*[^\n]+",
    re.MULTILINE,
)


class PasteStructureDetector:
    """
    Signals how content was structured: many fenced blocks, many @refs — 
    'multiple artifacts in one turn', not size alone.
    """

    id = DETECTOR_ID

    def scan(self, text: str) -> List[Finding]:
        if not text:
            return []

        m = analyze_text_metrics(text)
        findings: List[Finding] = []

        if m.code_fence_count >= 4:
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="many_fenced_blocks",
                    label="Multiple markdown code fences in one blob — suggests multi-snippet / multi-file paste",
                    start=0,
                    end=len(text),
                    redacted_snippet=f"{m.code_fence_count} ``` blocks",
                    meta={
                        "kind": "paste_structure",
                        "code_fence_count": m.code_fence_count,
                    },
                )
            )
        elif m.code_fence_count >= 2 and m.fenced_code_lines >= 35:
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="multi_snippet_paste",
                    label="Several fenced code regions with non-trivial length — structured paste pattern",
                    start=0,
                    end=len(text),
                    redacted_snippet=f"fences={m.code_fence_count}, fenced_lines≈{m.fenced_code_lines}",
                    meta={
                        "kind": "paste_structure",
                        "code_fence_count": m.code_fence_count,
                        "fenced_code_lines": m.fenced_code_lines,
                    },
                )
            )

        if m.at_reference_count >= 5:
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="many_attachment_style_refs",
                    label="Many @path-style references in one turn — broad file/context attachment pattern",
                    start=0,
                    end=len(text),
                    redacted_snippet=f"@{m.at_reference_count} refs",
                    meta={
                        "kind": "paste_structure",
                        "at_reference_count": m.at_reference_count,
                    },
                )
            )

        file_hints = len(_MULTI_FILE_HINT.findall(text))
        if file_hints >= 3:
            findings.append(
                Finding(
                    detector_id=DETECTOR_ID,
                    rule_id="labeled_file_sections",
                    label="Multiple inline 'file:' / 'path:' labeled sections — multi-file dump pattern",
                    start=0,
                    end=len(text),
                    redacted_snippet=f"{file_hints} section hints",
                    meta={"kind": "paste_structure", "labeled_sections": file_hints},
                )
            )

        return findings
