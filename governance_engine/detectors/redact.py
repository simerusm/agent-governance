from __future__ import annotations


def redact_match(s: str, head: int = 4, tail: int = 4) -> str:
    """Short redacted preview; never return full secret."""
    s = s.strip()
    if not s:
        return "[empty]"
    if len(s) <= head + tail + 3:
        return "[REDACTED]"
    return f"{s[:head]}…{s[-tail:]}"


def mask_line_preserving_shape(line: str, max_visible: int = 12) -> str:
    """Keep length class for logs without exposing content."""
    line = line.rstrip("\n")
    if len(line) <= max_visible:
        return "[REDACTED]"
    return line[:4] + "…" + line[-4:] if len(line) > 8 else "[REDACTED]"
