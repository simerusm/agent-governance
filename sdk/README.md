# Governance SDK (`sdk/`)

Thin **developer-facing** layer for marking agent-style code and handing execution to a pluggable **runtime client**. It does **not** run detectors, score text, or start servers—that stays in [`governance_engine/`](../governance_engine/) and future control-plane services.

## What this package does

| Concern | Handled here? |
|--------|----------------|
| `@governed_agent` decorator, metadata on functions | Yes |
| `RunContext` (run id, policy) for tracing helpers | Yes |
| Optional HTTP POST of **run summaries** to a control plane URL | Yes (`HttpReportingClient`) |
| Secrets/PII detection, SQLite ingest, Flask UI | No — use `governance_engine` |

Flow today: **decorate → runtime client runs your function locally → sets context → optional report**.

## Layout

| Module | Purpose |
|--------|---------|
| `decorators.py` | `@governed_agent`, `get_default_client` / `set_default_client` |
| `client.py` | `RuntimeClient` protocol, `DefaultRuntimeClient`, `HttpReportingClient`, `build_client_from_config` |
| `config.py` | `GovernanceConfig`, `load_config` (env + overrides) |
| `context.py` | `AgentMetadata`, `RunContext`, `run_context`, `current_run_context`, `with_run_context` |
| `tooling.py` | `record_tool_invocation`, `file_reference` |
| `artifacts.py` | `ArtifactRef`, `record_artifact` |

## Quick start

From the repo root (ensure `PYTHONPATH` includes the project root):

```python
from sdk import governed_agent, record_tool_invocation
from sdk.context import current_run_context

@governed_agent(policy="default", tags={"app": "demo"})
def my_agent(task: str) -> str:
    record_tool_invocation("echo", {"len": len(task)})
    return task.upper()

my_agent("hello")
```

The wrapped function exposes **`__governance_metadata__`** (`AgentMetadata`: policy, name, module, qualname, tags).

## Configuration (environment)

| Variable | Meaning |
|----------|---------|
| `GOVERNANCE_CONTROL_PLANE_URL` | Base URL; if set, `build_client_from_config` uses `HttpReportingClient` to POST run metadata after each call |
| `GOVERNANCE_API_KEY` | Optional `Authorization: Bearer …` for that POST |
| `GOVERNANCE_DEFAULT_POLICY` | Default policy when `@governed_agent()` omits `policy=` |
| `GOVERNANCE_CLIENT` | Reserved hint (`local` / `http`); selection is effectively driven by whether a control plane URL is set |

Override defaults in code: `load_config(overrides={"default_policy": "strict", ...})` or pass a custom `client=` to the decorator.

## Runtime clients

- **`DefaultRuntimeClient`** — Creates a `RunContext`, runs `fn(*args, **kwargs)`, clears context when done. No network.
- **`HttpReportingClient`** — Delegates to an inner client (default: `DefaultRuntimeClient`), then POSTs JSON to `{base}/v1/runs` with policy, agent name, status, elapsed time, and error class/message on failure. **User task text and arguments are not sent** by default.

Implement **`RuntimeClient`** yourself to forward runs to a sandbox, queue, or internal orchestrator without changing decorator code.

## Relationship to `governance_engine`

- **`governance_engine`**: analyze **text** (transcripts, etc.) with detectors + scoring — **post-hoc** or batch.
- **`sdk`**: **wrap code paths** so a future control plane can correlate runs, policies, and signals. You can later combine both (e.g. send transcript snippets from the runtime into the same detectors).

## Example script

See [`examples/sdk_governed_agent.py`](../examples/sdk_governed_agent.py):

```bash
python examples/sdk_governed_agent.py
```

## Tests

```bash
PYTHONPATH=. python -m unittest sdk.tests.test_sdk -v
```
