"""python -m transcript_pipeline [ingest|db|serve]"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m transcript_pipeline <ingest|db|serve> [args...]\n"
            "  ingest  — same as python -m transcript_pipeline.ingest -h\n"
            "  db      — browse SQLite (stats, chats, exchanges, detect)\n"
            "  serve   — web UI\n",
            file=sys.stderr,
        )
        return 2
    cmd = sys.argv[1]
    sys.argv = [sys.argv[0] + " " + cmd] + sys.argv[2:]
    if cmd == "ingest":
        from transcript_pipeline.ingest import main as m

        return m()
    if cmd == "db":
        from transcript_pipeline.cli import main as m

        return m()
    if cmd == "serve":
        from transcript_pipeline.web import main as m

        return m()
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
