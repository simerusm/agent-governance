from __future__ import annotations

import argparse
import html
from pathlib import Path

from governance_engine.db import TranscriptDB
from governance_engine.ingest import default_db_path


def create_app(db_path: Path):
    try:
        from flask import Flask, request
    except ImportError as e:
        raise SystemExit(
            "Flask is required for the web UI. Install: pip install flask"
        ) from e

    app = Flask(__name__)
    db = TranscriptDB(db_path)
    db.init_schema()

    @app.route("/")
    def index():
        project = request.args.get("project_id") or ""
        chat = request.args.get("chat_id") or ""
        limit = min(int(request.args.get("limit") or 100), 500)
        pid = project or None
        cid = chat or None
        rows = db.fetch_exchanges(pid, cid, limit=limit)
        stats = db.stats()
        chats = db.list_chats(pid)

        projects = db.list_projects()

        opt_projects = "".join(
            f'<option value="{html.escape(p)}"'
            f'{" selected" if p == project else ""}>{html.escape(p)}</option>'
            for p in projects
        )

        rows_html = []
        for r in rows:
            rows_html.append(
                "<tr>"
                f"<td>{r['id']}</td>"
                f"<td>{html.escape(r['project_id'])}</td>"
                f"<td><code>{html.escape(r['chat_id'])}</code></td>"
                f"<td>{r['turn_index']}</td>"
                f"<td>{r['user_char_count']}</td>"
                f"<td>{r['assistant_char_count']}</td>"
                f"<td>{r['contains_code']}</td>"
                f"<td>{r['contains_file_reference']}</td>"
                f"<td><pre>{html.escape((r['user_text'] or '')[:400])}"
                f"{'…' if len(r['user_text'] or '') > 400 else ''}</pre></td>"
                f"<td><pre>{html.escape((r['assistant_text'] or '')[:400])}"
                f"{'…' if len(r['assistant_text'] or '') > 400 else ''}</pre></td>"
                "</tr>"
            )

        chat_rows = "".join(
            f"<li>{html.escape(c['project_id'])} / <code>{html.escape(c['chat_id'])}</code> "
            f"— {c['turns']} turns</li>"
            for c in chats[:50]
        )

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Transcript DB</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px; vertical-align: top; }}
th {{ background: #f4f4f4; }}
pre {{ white-space: pre-wrap; margin: 0; font-size: 12px; }}
code {{ font-size: 12px; }}
</style></head><body>
<h1>Governance engine</h1>
<p>Total exchanges: <strong>{stats['total_exchanges']}</strong> — 
sessions: <strong>{stats['total_chat_sessions']}</strong></p>
<form method="get">
<label>project_id <select name="project_id"><option value="">(all)</option>{opt_projects}</select></label>
<label>chat_id <input name="chat_id" value="{html.escape(chat)}" size="40" placeholder="optional UUID"></label>
<label>limit <input name="limit" type="number" value="{limit}" min="1" max="500"></label>
<button type="submit">Filter</button>
</form>
<h2>Sessions</h2>
<ul>{chat_rows or '<li>(none)</li>'}</ul>
<h2>Exchanges</h2>
<table><thead><tr>
<th>id</th><th>project</th><th>chat_id</th><th>turn</th><th>u.chars</th><th>a.chars</th><th>code</th><th>file ref</th><th>user preview</th><th>assistant preview</th>
</tr></thead><tbody>
{''.join(rows_html) if rows_html else '<tr><td colspan="10">No rows</td></tr>'}
</tbody></table>
</body></html>"""

    return app


def main() -> int:
    p = argparse.ArgumentParser(description="Simple web UI for the governance_engine SQLite DB.")
    p.add_argument("--db-path", type=Path, default=default_db_path())
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5050)
    args = p.parse_args()
    db_path = args.db_path.expanduser().resolve()
    app = create_app(db_path)
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
