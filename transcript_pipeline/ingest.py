from __future__ import annotations

import argparse
import sys
from pathlib import Path

from transcript_pipeline.db import TranscriptDB
from transcript_pipeline.parser import parse_transcript_jsonl
from transcript_pipeline.paths import agent_transcripts_dir, resolve_transcript_path


def default_db_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "transcripts.db"


def run_ingest(
    project_id: str,
    chat_id: str | None,
    db_path: Path,
    dry_run: bool = False,
) -> int:
    agent_root = agent_transcripts_dir(project_id)
    if not agent_root.is_dir():
        print(f"ERROR: agent-transcripts not found: {agent_root}", file=sys.stderr)
        return 1

    pairs = resolve_transcript_path(project_id, chat_id)
    if not pairs:
        if chat_id:
            print(
                f"ERROR: no transcript for chat_id={chat_id} under {agent_root}",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: no chat sessions found under {agent_root}", file=sys.stderr)
        return 1

    db: TranscriptDB | None = None
    if not dry_run:
        db = TranscriptDB(db_path)
        db.init_schema()

    total = 0
    for cid, jpath in pairs:
        if not jpath.is_file():
            print(f"SKIP missing file: {jpath}", file=sys.stderr)
            continue
        exchanges = parse_transcript_jsonl(jpath, project_id=project_id, chat_id=cid)
        print(f"{cid}: {len(exchanges)} exchange(s) from {jpath.name}")
        for ex in exchanges:
            total += 1
            if db is not None:
                db.upsert_exchange(ex)

    if dry_run:
        print(f"DRY RUN: would ingest {total} row(s)")
    else:
        print(f"Ingested {total} exchange row(s) into {db_path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Ingest Cursor agent-transcripts JSONL into SQLite."
    )
    p.add_argument(
        "--project-id",
        required=True,
        help="Cursor project folder name, e.g. Users-mahesh-Code-quick-mvp",
    )
    p.add_argument(
        "--chat-id",
        default=None,
        help="Optional session UUID folder name; if omitted, all sessions are ingested.",
    )
    p.add_argument(
        "--db-path",
        type=Path,
        default=default_db_path(),
        help=f"SQLite database path (default: {default_db_path()})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only; do not write to database.",
    )
    args = p.parse_args()
    return run_ingest(
        project_id=args.project_id,
        chat_id=args.chat_id,
        db_path=args.db_path.expanduser().resolve(),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
