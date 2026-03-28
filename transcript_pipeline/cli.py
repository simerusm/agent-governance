from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from transcript_pipeline.db import TranscriptDB
from transcript_pipeline.detectors import analyze
from transcript_pipeline.detectors.types import Finding
from transcript_pipeline.ingest import default_db_path


def _finding_to_dict(f: Finding) -> dict:
    return {
        "detector_id": f.detector_id,
        "rule_id": f.rule_id,
        "label": f.label,
        "start": f.start,
        "end": f.end,
        "redacted_snippet": f.redacted_snippet,
        "meta": dict(f.meta),
    }


def _text_for_scan(row: dict, source: str) -> str:
    u = row.get("user_text") or ""
    a = row.get("assistant_text") or ""
    if source == "user":
        return u
    if source == "assistant":
        return a
    return f"{u}\n\n{a}".strip()


def cmd_stats(db: TranscriptDB) -> int:
    db.init_schema()
    s = db.stats()
    print(json.dumps(s, indent=2))
    return 0


def cmd_chats(db: TranscriptDB, project_id: str | None) -> int:
    db.init_schema()
    rows = db.list_chats(project_id)
    for r in rows:
        print(f"{r['project_id']}\t{r['chat_id']}\tturns={r['turns']}")
    return 0


def cmd_list_exchanges(
    db: TranscriptDB,
    project_id: str | None,
    chat_id: str | None,
    limit: int,
    json_out: bool,
) -> int:
    db.init_schema()
    rows = db.fetch_exchanges(project_id, chat_id, limit=limit)
    if json_out:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    for r in rows:
        uid = r["id"]
        print(
            f"[{uid}] {r['project_id']} / {r['chat_id']} turn={r['turn_index']} "
            f"code={r['contains_code']} file_ref={r['contains_file_reference']}"
        )
        ut = (r["user_text"] or "")[:120].replace("\n", " ")
        if len(r["user_text"] or "") > 120:
            ut += "…"
        print(f"  user: {ut}")
    return 0


def cmd_detect(
    db: TranscriptDB,
    project_id: str | None,
    chat_id: str | None,
    limit: int,
    text_source: str,
    json_out: bool,
    hits_only: bool,
) -> int:
    """Run registered detectors on exchange rows from the DB."""
    db.init_schema()
    rows = db.fetch_exchanges(project_id, chat_id, limit=limit)
    out_rows: list[dict] = []
    for row in rows:
        text = _text_for_scan(row, text_source)
        report = analyze(text)
        findings = [_finding_to_dict(f) for f in report.findings]
        if hits_only and not findings:
            continue
        rec = {
            "id": row["id"],
            "project_id": row["project_id"],
            "chat_id": row["chat_id"],
            "turn_index": row["turn_index"],
            "text_source": text_source,
            "scanned_chars": len(text),
            "summary": report.to_summary(),
            "findings": findings,
        }
        out_rows.append(rec)

    if json_out:
        print(json.dumps(out_rows, indent=2))
        return 0

    print(
        f"Scanned {len(rows)} exchange row(s) from DB "
        f"({len(out_rows)} after --hits-only filter).\n"
        f"text_source={text_source}\n"
    )
    for rec in out_rows:
        s = rec["summary"]
        print(
            f"[id={rec['id']}] {rec['project_id']} / {rec['chat_id']} "
            f"turn={rec['turn_index']} — {s['finding_count']} finding(s)"
        )
        if rec["findings"]:
            by_d: dict[str, list[str]] = {}
            for f in rec["findings"]:
                by_d.setdefault(f["detector_id"], []).append(f["rule_id"])
            for det, rules in sorted(by_d.items()):
                print(f"  {det}: {', '.join(sorted(set(rules)))}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Browse ingested transcript database.")
    p.add_argument(
        "--db-path",
        type=Path,
        default=default_db_path(),
        help="SQLite path",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="Show row counts")

    sp = sub.add_parser("chats", help="List chat sessions")
    sp.add_argument("--project-id", default=None)

    sp = sub.add_parser("exchanges", help="List exchanges (rows)")
    sp.add_argument("--project-id", default=None)
    sp.add_argument("--chat-id", default=None)
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--json", action="store_true", dest="json_out")

    sp = sub.add_parser(
        "detect",
        help="Run detectors on ingested exchanges (user/assistant/both text)",
    )
    sp.add_argument("--project-id", default=None)
    sp.add_argument("--chat-id", default=None)
    sp.add_argument("--limit", type=int, default=200)
    sp.add_argument(
        "--text-source",
        choices=("user", "assistant", "both"),
        default="both",
        help="Which column(s) to scan (default: both)",
    )
    sp.add_argument("--json", action="store_true", dest="json_out")
    sp.add_argument(
        "--hits-only",
        action="store_true",
        help="Only output rows with at least one finding",
    )

    args = p.parse_args()
    args.db_path = args.db_path.expanduser().resolve()
    db = TranscriptDB(args.db_path)

    if args.cmd == "stats":
        return cmd_stats(db)
    if args.cmd == "chats":
        return cmd_chats(db, args.project_id)
    if args.cmd == "exchanges":
        return cmd_list_exchanges(
            db,
            args.project_id,
            args.chat_id,
            args.limit,
            args.json_out,
        )
    if args.cmd == "detect":
        return cmd_detect(
            db,
            args.project_id,
            args.chat_id,
            args.limit,
            args.text_source,
            args.json_out,
            args.hits_only,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
