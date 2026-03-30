from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExchangeRecord:
    """One user turn + aggregated assistant reply (until next user message)."""

    source: str = "cursor_transcript"
    project_id: str = ""
    chat_id: str = ""
    transcript_path: str = ""
    user_text: str = ""
    assistant_text: str = ""
    user_char_count: int = 0
    assistant_char_count: int = 0
    contains_code: bool = False
    contains_file_reference: bool = False
    raw_messages: int = 0
    timestamp: Optional[str] = None
    turn_index: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_row_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "project_id": self.project_id,
            "chat_id": self.chat_id,
            "transcript_path": self.transcript_path,
            "user_text": self.user_text,
            "assistant_text": self.assistant_text,
            "user_char_count": self.user_char_count,
            "assistant_char_count": self.assistant_char_count,
            "contains_code": int(self.contains_code),
            "contains_file_reference": int(self.contains_file_reference),
            "raw_messages": self.raw_messages,
            "timestamp": self.timestamp,
            "turn_index": self.turn_index,
        }
