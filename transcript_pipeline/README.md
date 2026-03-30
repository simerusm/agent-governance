# Transcript ingestion pipeline

Reads Cursor `agent-transcripts/<chat_id>/<chat_id>.jsonl` files, parses **user / assistant** turns into normalized rows, and stores them in **SQLite** for analysis.

NOTE: You will need to find and provide a project id and chat id for ingestion

**Full reference (concepts, schema, every CLI flag, detectors):** [DOCUMENTATION.md](DOCUMENTATION.md) — start here if terms like **exchange** or **`db exchanges`** are unclear.

## Layout

- `paths.py` — resolves `~/.cursor/projects/<project_id>/agent-transcripts/`, lists `chat_id` folders.
- `parser.py` — extracts text from `message.content[].text`, groups **one user message + following assistant messages** into one row (`ExchangeRecord`).
- `db.py` — SQLite schema + upserts (`UNIQUE(project_id, chat_id, turn_index)`).
- `ingest.py` — CLI to load transcripts into the DB.
- `cli.py` — terminal browse (`stats`, `chats`, `exchanges`, `detect`).
- `web.py` — minimal Flask table UI.
- `detectors/` — secrets, PII, sensitive context, sensitive path detectors + orchestrator.

## Install (web UI)

```bash
pip install -r requirements.txt
```

## Ingest

All sessions for a project:

```bash
cd /Users/mahesh/Code/quick-mvp
python3 -m transcript_pipeline ingest --project-id Users-mahesh-Code-quick-mvp
```

One chat:

```bash
python3 -m transcript_pipeline ingest \
  --project-id Users-mahesh-Code-quick-mvp \
  --chat-id b608d697-fc98-423a-8ffd-5f3409aacbbd
```

Default DB: `data/transcripts.db` (override with `--db-path`).

Re-running ingest **updates** existing rows for the same `(project_id, chat_id, turn_index)`.

## Browse (CLI)

```bash
python3 -m transcript_pipeline db stats
python3 -m transcript_pipeline db chats
python3 -m transcript_pipeline db exchanges --project-id Users-mahesh-Code-quick-mvp --limit 20
python3 -m transcript_pipeline db exchanges --json --limit 5
```

Run detectors on rows already in the DB (default DB: `data/transcripts.db`):

```bash
# Human summary: each exchange + detector/rule hits
python3 -m transcript_pipeline db detect --limit 50

# Only user messages (common for “what did the user paste?”)
python3 -m transcript_pipeline db detect --text-source user --hits-only

# One chat, full JSON (redacted snippets only)
python3 -m transcript_pipeline db detect \
  --project-id Users-mahesh-Code-quick-mvp \
  --chat-id b608d697-fc98-423a-8ffd-5f3409aacbbd \
  --json

# Short summary only (no per-finding reason/snippet lines)
python3 -m transcript_pipeline db detect --compact --limit 20

# Policy score (0–100) + alert if score >= threshold (default 75)
python3 -m transcript_pipeline db detect --score --hits-only --limit 10
python3 -m transcript_pipeline db detect --score --alert-threshold 80 --json --limit 5
```

Weights and combo rules: `transcript_pipeline/scoring/registry.py`.

## Web UI

```bash
python3 -m transcript_pipeline serve --port 5050
```

Open http://127.0.0.1:5050

## Detectors

Primary entry:

```python
from transcript_pipeline.detectors import analyze

report = analyze(some_text)
report.to_summary()   # counts + rule ids
report.findings     # Finding objects (redacted snippets only)
```

Detectors are separate classifiers (no single fuzzy “sensitive” score):

| Package | `id` | Purpose |
|---------|------|---------|
| `detectors/secrets/` | `secrets` | API keys, Bearer/Basic, JWTs, PEM keys, DB URLs, `.env`-style assignments, cloud connection strings |
| `detectors/pii/` | `pii` | Emails, phones, SSN-shaped (validated), PAN (Luhn), US street heuristic, labeled account IDs |
| `detectors/sensitive_context/` | `sensitive_context` | Keywords (confidential/internal), auth/deployment filenames, internal hosts, private IPs, repo paths, export/log patterns |
| `detectors/sensitive_files/` | `sensitive_files` | Path/filename references (`.env`, `.aws/credentials`, SSH keys, kubeconfig, …) |
| `detectors/context_detection/exposure_scope/` | `context_exposure_scope` | Governance tiers: `small_snippet` / `moderate_internal_context` / `broad_internal_context_transfer` (volume + fences; not “large = bad” alone) |
| `detectors/context_detection/paste_structure/` | `context_paste_structure` | Many fenced blocks, many `@` refs, multi-file labeled sections |
| `detectors/context_detection/technical_markers/` | `context_technical_markers` | Tracebacks, dense paths, architecture/incident language |

Context detectors are **visibility signals** — combine with secrets/PII for escalation. `detectors/context_detection/metrics.py` holds shared thresholds.

`detectors/orchestrator.py` composes them; extend with `register_detector(MyDetector())`.

## Row shape (conceptual)

Each row is one **exchange**: user turn + concatenated assistant replies until the next user message. Fields include `chat_id`, `transcript_path`, char counts, `contains_code`, `contains_file_reference`, `raw_messages` (JSONL lines in that exchange).
