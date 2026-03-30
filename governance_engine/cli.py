from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from governance_engine.db import TranscriptDB
from governance_engine.detectors import analyze
from governance_engine.detectors.types import Finding
from governance_engine.ingest import default_db_path
from governance_engine.scoring import score_report


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


def _format_finding_line(f: dict, index: int) -> str:
    """Human-readable one finding for terminal (uses redacted snippet as match preview)."""
    det = f["detector_id"]
    rid = f["rule_id"]
    label = f.get("label") or ""
    snip = f.get("redacted_snippet") or ""
    start = f.get("start", 0)
    end = f.get("end", 0)
    # Keep snippet single-line for terminal width
    one = " ".join(snip.split())
    if len(one) > 100:
        one = one[:97] + "…"
    lines = [
        f"  {index}. [{det}] {rid}",
        f"      reason: {label}",
        f"      matched: {one}",
        f"      span: chars [{start}, {end})",
    ]
    meta = f.get("meta") or {}
    if meta and not (
        len(meta) == 1 and meta.get("kind") in ("path_reference", "context")
    ):
        lines.append(f"      meta: {meta}")
    return "\n".join(lines)


def _format_policy_text(pol_dict: dict) -> str:
    combos = pol_dict.get("combo_bonuses") or []
    cb = ", ".join(f"{c['name']}(+{c['bonus']})" for c in combos) if combos else "(none)"
    alert = "ALERT" if pol_dict.get("alert") else "ok"
    return (
        f"  policy: score={pol_dict['score']:.1f}/{pol_dict['cap_applied']:.0f} "
        f"raw={pol_dict['raw_points']:.1f} threshold={pol_dict['threshold']:.0f} "
        f"[{alert}]  combos: {cb}"
    )


def cmd_detect(
    db: TranscriptDB,
    project_id: str | None,
    chat_id: str | None,
    limit: int,
    text_source: str,
    json_out: bool,
    hits_only: bool,
    compact: bool,
    do_score: bool,
    alert_threshold: float,
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
        if do_score:
            pol = score_report(report, alert_threshold=alert_threshold)
            rec["policy"] = pol.to_dict()
        out_rows.append(rec)

    if json_out:
        print(json.dumps(out_rows, indent=2))
        return 0

    hdr = (
        f"Scanned {len(rows)} exchange row(s) from DB "
        f"({len(out_rows)} after --hits-only filter).\n"
        f"text_source={text_source}"
    )
    if do_score:
        hdr += f"\npolicy scoring: alert if score >= {alert_threshold}"
    print(hdr + "\n")
    for rec in out_rows:
        s = rec["summary"]
        print(
            f"[id={rec['id']}] {rec['project_id']} / {rec['chat_id']} "
            f"turn={rec['turn_index']} — {s['finding_count']} finding(s)"
        )
        findings = rec["findings"]
        if findings:
            if compact:
                by_d: dict[str, list[str]] = {}
                for f in findings:
                    by_d.setdefault(f["detector_id"], []).append(f["rule_id"])
                for det, rules in sorted(by_d.items()):
                    print(f"  {det}: {', '.join(sorted(set(rules)))}")
            else:
                for i, f in enumerate(findings, start=1):
                    print(_format_finding_line(f, i))
        if do_score and "policy" in rec:
            print(_format_policy_text(rec["policy"]))
            pd = rec["policy"]
            if not compact and pd.get("finding_breakdown"):
                print("    points: " + ", ".join(
                    f"{x['detector_id']}/{x['rule_id']}={x['weight']:.0f}"
                    for x in pd["finding_breakdown"][:12]
                ) + (" …" if len(pd["finding_breakdown"]) > 12 else ""))
        print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Browse ingested exchanges (governance_engine SQLite DB).")
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
    sp.add_argument(
        "--compact",
        action="store_true",
        help="Short summary only (detector → rule ids); omit per-finding details",
    )
    sp.add_argument(
        "--score",
        action="store_true",
        help="Attach policy score (0–100) and alert flag; tune weights in scoring/registry.py",
    )
    sp.add_argument(
        "--alert-threshold",
        type=float,
        default=75.0,
        help="Alert when policy score >= this value (default: 75)",
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
            args.compact,
            args.score,
            args.alert_threshold,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
