#!/usr/bin/env python3
"""
Cursor chat interceptor/analytics tool.

This script watches Cursor agent transcript files and extracts:
- User chat input (including likely pasted blocks)
- Assistant/model responses
- Basic analytics per message
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_TRANSCRIPTS_DIR = (
    Path.home()
    / ".cursor"
    / "projects"
    / "Users-mahesh-Code-quick-mvp"
    / "agent-transcripts"
)


PASTE_HINT_PATTERNS = [
    re.compile(r"```[\s\S]+?```"),
    re.compile(r"\n\s{4,}\S"),
    re.compile(r"(?:^|\n)\s*(?:import |from .* import |class |def |function |\{|\[)"),
]


@dataclass
class MessageEvent:
    timestamp: Optional[str]
    role: str
    text: str
    source_file: str

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def line_count(self) -> int:
        if not self.text:
            return 0
        return self.text.count("\n") + 1

    @property
    def likely_paste(self) -> bool:
        if self.char_count >= 800:
            return True
        return any(pattern.search(self.text) for pattern in PASTE_HINT_PATTERNS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor Cursor transcript messages and analyze user/model content."
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        default=DEFAULT_TRANSCRIPTS_DIR,
        help=f"Path to Cursor transcript folder (default: {DEFAULT_TRANSCRIPTS_DIR})",
    )
    parser.add_argument(
        "--since-seconds",
        type=int,
        default=0,
        help="Only process files modified in the last N seconds on startup.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds for change detection.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("captured_chat.jsonl"),
        help="Where to write normalized extracted messages.",
    )
    parser.add_argument(
        "--print-full",
        action="store_true",
        help="Print full message bodies (default prints short preview).",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=15.0,
        help="Print watcher-alive heartbeat when no events arrive (0 disables).",
    )
    return parser.parse_args()


def extract_candidate_text(data: Any) -> List[str]:
    """
    Pull potential message text from unknown transcript schemas.
    Uses broad matching so it keeps working if Cursor changes internal formats.
    """
    hits: List[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_l = key.lower()
                if (
                    isinstance(value, str)
                    and key_l
                    in {
                        "text",
                        "content",
                        "message",
                        "prompt",
                        "response",
                        "body",
                        "input",
                        "output",
                    }
                    and value.strip()
                ):
                    hits.append(value.strip())
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    # Remove duplicates while preserving order.
    seen = set()
    unique_hits: List[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            unique_hits.append(h)
    return unique_hits


def infer_role(payload: Dict[str, Any]) -> str:
    role_candidates = [
        payload.get("role"),
        payload.get("author"),
        payload.get("sender"),
        payload.get("type"),
        payload.get("eventType"),
        payload.get("event_type"),
    ]
    role_blob = " ".join(str(v).lower() for v in role_candidates if v is not None)
    if any(k in role_blob for k in ("user", "human", "prompt")):
        return "user"
    if any(k in role_blob for k in ("assistant", "model", "ai", "response")):
        return "assistant"
    return "unknown"


def infer_timestamp(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("timestamp", "time", "createdAt", "created_at", "ts"):
        if key in payload:
            value = payload[key]
            if isinstance(value, (int, float)):
                try:
                    return datetime.fromtimestamp(value).isoformat()
                except Exception:
                    continue
            if isinstance(value, str):
                return value
    return None


def parse_jsonl_lines(path: Path) -> Iterable[MessageEvent]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            role = infer_role(payload)
            ts = infer_timestamp(payload)
            text_candidates = extract_candidate_text(payload)
            for text in text_candidates:
                yield MessageEvent(
                    timestamp=ts,
                    role=role,
                    text=text,
                    source_file=path.name,
                )


def file_recent_enough(path: Path, since_seconds: int) -> bool:
    if since_seconds <= 0:
        return True
    try:
        return (time.time() - path.stat().st_mtime) <= since_seconds
    except OSError:
        return False


def short_preview(text: str, max_len: int = 140) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1] + "…"


def iter_transcript_files(transcripts_dir: Path) -> List[Path]:
    # Cursor stores transcripts in nested per-session folders.
    return sorted(p for p in transcripts_dir.rglob("*.jsonl") if p.is_file())


def write_output_jsonl(output_path: Path, event: MessageEvent) -> None:
    output_record = {
        "captured_at": datetime.now().isoformat(),
        "timestamp": event.timestamp,
        "role": event.role,
        "text": event.text,
        "char_count": event.char_count,
        "line_count": event.line_count,
        "likely_paste": event.likely_paste,
        "source_file": event.source_file,
    }
    with output_path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(output_record, ensure_ascii=False) + "\n")


def print_event(event: MessageEvent, print_full: bool) -> None:
    ts = event.timestamp or "no-ts"
    paste_tag = " yes" if event.likely_paste else " no"
    print(
        f"[{ts}] role={event.role:9s} chars={event.char_count:4d} "
        f"lines={event.line_count:3d} likely_paste={paste_tag} file={event.source_file}"
    )
    if print_full:
        print(event.text)
        print("-" * 80)
    else:
        print(f"  preview: {short_preview(event.text)}")


def scan_new_content(
    transcripts_dir: Path,
    offsets: Dict[Path, int],
    seen_signatures: set,
    since_seconds: int,
) -> List[MessageEvent]:
    events: List[MessageEvent] = []
    for path in iter_transcript_files(transcripts_dir):
        if not file_recent_enough(path, since_seconds):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue

        last_offset = offsets.get(path, 0)
        if size < last_offset:
            # File got rotated or truncated.
            last_offset = 0

        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(last_offset)
            chunk = fh.read()
            offsets[path] = fh.tell()

        for raw in chunk.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            role = infer_role(payload)
            ts = infer_timestamp(payload)
            for txt in extract_candidate_text(payload):
                signature = (ts, role, txt[:200], path.name)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                events.append(
                    MessageEvent(
                        timestamp=ts,
                        role=role,
                        text=txt,
                        source_file=path.name,
                    )
                )
    return events


def print_rollup(stats: Dict[str, int]) -> None:
    total = stats.get("total", 0)
    if total == 0:
        return
    print(
        f"\nRollup: total={total}, user={stats.get('user', 0)}, "
        f"assistant={stats.get('assistant', 0)}, unknown={stats.get('unknown', 0)}, "
        f"likely_pastes={stats.get('likely_paste', 0)}"
    )


def main() -> int:
    args = parse_args()
    transcripts_dir: Path = args.transcripts_dir.expanduser().resolve()
    output_jsonl: Path = args.output_jsonl.expanduser().resolve()

    if not transcripts_dir.exists():
        print(f"ERROR: transcript directory does not exist: {transcripts_dir}")
        return 1

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    # Ensure output file exists immediately, even before first captured event.
    output_jsonl.touch(exist_ok=True)

    offsets: Dict[Path, int] = {}
    seen_signatures: set = set()
    stats = {"total": 0, "user": 0, "assistant": 0, "unknown": 0, "likely_paste": 0}
    last_heartbeat = time.time()

    # Prime offsets (or scan recent files immediately).
    transcript_files = iter_transcript_files(transcripts_dir)
    for path in transcript_files:
        if args.since_seconds > 0 and file_recent_enough(path, args.since_seconds):
            offsets[path] = 0
        else:
            try:
                offsets[path] = path.stat().st_size
            except OSError:
                offsets[path] = 0

    print(f"Watching transcripts in: {transcripts_dir}")
    print(f"Detected transcript files: {len(transcript_files)}")
    print(f"Writing normalized output to: {output_jsonl}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            new_events = scan_new_content(
                transcripts_dir=transcripts_dir,
                offsets=offsets,
                seen_signatures=seen_signatures,
                since_seconds=args.since_seconds,
            )
            for ev in new_events:
                stats["total"] += 1
                stats[ev.role] = stats.get(ev.role, 0) + 1
                if ev.likely_paste:
                    stats["likely_paste"] += 1
                write_output_jsonl(output_jsonl, ev)
                print_event(ev, print_full=args.print_full)

            if new_events:
                print_rollup(stats)
                print()
                last_heartbeat = time.time()
            elif args.heartbeat_seconds > 0:
                now = time.time()
                if (now - last_heartbeat) >= args.heartbeat_seconds:
                    print(
                        f"[{datetime.now().isoformat(timespec='seconds')}] "
                        "watcher alive: no new transcript events yet"
                    )
                    last_heartbeat = now

            time.sleep(max(0.1, args.poll_interval))
    except KeyboardInterrupt:
        print("\nStopped.")
        print_rollup(stats)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
