from __future__ import annotations

from pathlib import Path
from typing import List, Optional


def cursor_projects_root() -> Path:
    return Path.home() / ".cursor" / "projects"


def agent_transcripts_dir(project_id: str) -> Path:
    """project_id e.g. Users-mahesh-Code-quick-mvp"""
    return cursor_projects_root() / project_id / "agent-transcripts"


def transcript_jsonl_for_chat(agent_root: Path, chat_id: str) -> Path:
    return agent_root / chat_id / f"{chat_id}.jsonl"


def discover_chat_ids(agent_root: Path) -> List[str]:
    if not agent_root.is_dir():
        return []
    out: List[str] = []
    for child in sorted(agent_root.iterdir()):
        if not child.is_dir():
            continue
        cid = child.name
        jl = child / f"{cid}.jsonl"
        if jl.is_file():
            out.append(cid)
    return out


def resolve_transcript_path(
    project_id: str, chat_id: Optional[str] = None
) -> List[tuple[str, Path]]:
    """
    Returns list of (chat_id, path_to_jsonl).
    If chat_id is set, returns one entry if file exists; else empty.
    """
    root = agent_transcripts_dir(project_id)
    if chat_id:
        p = transcript_jsonl_for_chat(root, chat_id)
        return [(chat_id, p)] if p.is_file() else []
    return [(cid, transcript_jsonl_for_chat(root, cid)) for cid in discover_chat_ids(root)]
