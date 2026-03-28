# Cursor Chat Interceptor (Local)

This tool monitors Cursor transcript files and extracts both:
- what the user entered (including likely pasted blocks), and
- what the assistant/model replied.

It writes a normalized JSONL log for later analysis.

## What it captures

- Message role (`user`, `assistant`, or `unknown`)
- Message text
- Character + line counts
- A simple `likely_paste` heuristic
- Source transcript filename
- Timestamps (when available)

## Run

From this folder:

```bash
python3 interceptor.py --since-seconds 3600 --print-full
```

Useful flags:

- `--transcripts-dir`: custom transcript directory
- `--output-jsonl`: where normalized records are stored
- `--poll-interval`: seconds between scans
- `--since-seconds`: start by scanning recent transcript files
- `--print-full`: print full messages to terminal
- `--heartbeat-seconds`: print periodic "watcher alive" status (0 disables)

Default output file:

- `captured_chat.jsonl`

## Example analysis ideas

You can later analyze `captured_chat.jsonl` for:
- paste frequency by session
- average user prompt size vs assistant response size
- recurring user intents or repeated prompts
- response quality scoring pipelines

## Notes

- This is a local file-based interceptor (no network proxy).
- It relies on Cursor transcript files already stored on disk.
- It recursively scans nested transcript folders (per-session layout).
- If Cursor changes transcript schema, extraction still attempts to work via broad key matching.
