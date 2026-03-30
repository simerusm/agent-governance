from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from governance_engine.models import ExchangeRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL DEFAULT 'cursor_transcript',
    project_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    transcript_path TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    user_text TEXT NOT NULL DEFAULT '',
    assistant_text TEXT NOT NULL DEFAULT '',
    user_char_count INTEGER NOT NULL DEFAULT 0,
    assistant_char_count INTEGER NOT NULL DEFAULT 0,
    contains_code INTEGER NOT NULL DEFAULT 0,
    contains_file_reference INTEGER NOT NULL DEFAULT 0,
    raw_messages INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, chat_id, turn_index)
);

CREATE INDEX IF NOT EXISTS idx_exchanges_project ON exchanges(project_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_chat ON exchanges(project_id, chat_id);
"""


class TranscriptDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_exchange(self, rec: ExchangeRecord) -> None:
        row = rec.to_row_dict()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO exchanges (
                    source, project_id, chat_id, transcript_path, turn_index,
                    user_text, assistant_text, user_char_count, assistant_char_count,
                    contains_code, contains_file_reference, raw_messages, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, chat_id, turn_index) DO UPDATE SET
                    source=excluded.source,
                    transcript_path=excluded.transcript_path,
                    user_text=excluded.user_text,
                    assistant_text=excluded.assistant_text,
                    user_char_count=excluded.user_char_count,
                    assistant_char_count=excluded.assistant_char_count,
                    contains_code=excluded.contains_code,
                    contains_file_reference=excluded.contains_file_reference,
                    raw_messages=excluded.raw_messages,
                    timestamp=excluded.timestamp,
                    ingested_at=datetime('now')
                """,
                (
                    row["source"],
                    row["project_id"],
                    row["chat_id"],
                    row["transcript_path"],
                    row["turn_index"],
                    row["user_text"],
                    row["assistant_text"],
                    row["user_char_count"],
                    row["assistant_char_count"],
                    row["contains_code"],
                    row["contains_file_reference"],
                    row["raw_messages"],
                    row["timestamp"],
                ),
            )

    def list_projects(self) -> List[str]:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT DISTINCT project_id FROM exchanges ORDER BY project_id"
            )
            return [r[0] for r in cur.fetchall()]

    def list_chats(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        q = "SELECT project_id, chat_id, COUNT(*) AS turns FROM exchanges"
        args: List[Any] = []
        if project_id:
            q += " WHERE project_id = ?"
            args.append(project_id)
        q += " GROUP BY project_id, chat_id ORDER BY project_id, chat_id"
        with self.connect() as conn:
            cur = conn.execute(q, args)
            return [dict(row) for row in cur.fetchall()]

    def fetch_exchanges(
        self,
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        q = "SELECT * FROM exchanges WHERE 1=1"
        args: List[Any] = []
        if project_id:
            q += " AND project_id = ?"
            args.append(project_id)
        if chat_id:
            q += " AND chat_id = ?"
            args.append(chat_id)
        q += " ORDER BY project_id, chat_id, turn_index LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        with self.connect() as conn:
            cur = conn.execute(q, args)
            return [dict(row) for row in cur.fetchall()]

    def stats(self) -> Dict[str, Any]:
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()[0]
            chats = conn.execute(
                "SELECT COUNT(DISTINCT project_id || ':' || chat_id) FROM exchanges"
            ).fetchone()[0]
        return {"total_exchanges": total, "total_chat_sessions": chats}
