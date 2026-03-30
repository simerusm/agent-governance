from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from governance_engine.models import ExchangeRecord

USER_QUERY_WRAP = re.compile(
    r"^\s*<user_query>\s*([\s\S]*?)\s*</user_query>\s*$", re.IGNORECASE
)
CODE_FENCE = re.compile(r"```")
FILE_REF = re.compile(
    r"(?:@[\w./\\-]+|`[^`]+\.(?:py|ts|tsx|js|json|md|yaml|yml|toml)`)",
    re.IGNORECASE,
)


def extract_role(payload: Dict[str, Any]) -> str:
    r = payload.get("role")
    if isinstance(r, str):
        return r.lower().strip()
    return "unknown"


def extract_text_from_line(payload: Dict[str, Any]) -> str:
    """Cursor format: role + message.content[].{type,text}."""
    msg = payload.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    t = block.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                elif "text" in block and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            return "\n".join(parts).strip()
    # Fallback: generic string walk
    return _fallback_extract_strings(payload)


def _fallback_extract_strings(obj: Any) -> str:
    hits: List[str] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                kl = k.lower()
                if isinstance(v, str) and kl in ("text", "content") and v.strip():
                    hits.append(v.strip())
                walk(v)
        elif isinstance(o, list):
            for i in o:
                walk(i)

    walk(obj)
    seen = set()
    out: List[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return "\n".join(out).strip()


def normalize_user_text(text: str) -> str:
    m = USER_QUERY_WRAP.match(text.strip())
    if m:
        return m.group(1).strip()
    return text.strip()


def detect_contains_code(text: str) -> bool:
    if CODE_FENCE.search(text):
        return True
    if re.search(r"(?:^|\n)\s{4,}\S", text):
        return True
    return bool(
        re.search(
            r"(?:^|\n)\s*(?:import |from \w+ import |def |class |function |\{|\[)",
            text,
        )
    )


def detect_contains_file_reference(text: str) -> bool:
    if FILE_REF.search(text):
        return True
    if re.search(r"@\S+", text):
        return True
    return False


def parse_transcript_jsonl(
    path: Path,
    project_id: str,
    chat_id: str,
) -> List[ExchangeRecord]:
    lines: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                lines.append(obj)

    exchanges: List[ExchangeRecord] = []
    turn_index = 0
    i = 0
    while i < len(lines):
        payload = lines[i]
        role = extract_role(payload)
        if role != "user":
            i += 1
            continue

        user_raw = extract_text_from_line(payload)
        user_text = normalize_user_text(user_raw)
        assistant_chunks: List[str] = []
        raw_count = 1
        ts = _first_timestamp(payload, lines, i)

        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            r = extract_role(nxt)
            if r == "user":
                break
            if r == "assistant":
                t = extract_text_from_line(nxt)
                if t:
                    assistant_chunks.append(t)
                raw_count += 1
            else:
                raw_count += 1
            j += 1

        assistant_text = "\n\n".join(assistant_chunks).strip()

        ex = ExchangeRecord(
            source="cursor_transcript",
            project_id=project_id,
            chat_id=chat_id,
            transcript_path=str(path.resolve()),
            user_text=user_text,
            assistant_text=assistant_text,
            user_char_count=len(user_text),
            assistant_char_count=len(assistant_text),
            contains_code=detect_contains_code(user_text),
            contains_file_reference=detect_contains_file_reference(user_text),
            raw_messages=raw_count,
            timestamp=ts,
            turn_index=turn_index,
        )
        exchanges.append(ex)
        turn_index += 1
        i = j

    return exchanges


def _first_timestamp(
    payload: Dict[str, Any], lines: List[Dict[str, Any]], idx: int
) -> Optional[str]:
    for key in ("timestamp", "time", "createdAt", "created_at", "ts"):
        if key in payload:
            v = payload[key]
            if v is not None:
                return str(v)
    return None
