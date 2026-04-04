# Governance execution backend (Kubernetes)

Two services:

1. **Governance runner** (runs **inside** each pod): FastAPI on port **8080** — evaluates prompts/responses with `governance_engine` + `runtime`, optionally calls an OpenAI-compatible LLM, returns structured scores.
2. **Cluster API** (runs on your laptop or in-cluster): FastAPI on port **8090** — creates/lists/deletes runner pods via the Kubernetes API.

Recommended flow: **Cluster API** → create pod → **kubectl port-forward** (or in-cluster Service) → **HTTP** to the runner’s `/v1/governed-complete`. Using HTTP keeps a single code path (same as prod) and avoids parsing `kubectl exec` output.

## Build the runner image

From the **repository root**:

```bash
docker build -f infrastructure/backend/governance_runner/Dockerfile -t governance-runner:latest .
```

### Kind / minikube (local cluster)

Load the image so the node can run `IfNotPresent` pulls:

```bash
kind load docker-image governance-runner:latest
# or: minikube image load governance-runner:latest
```

For purely local images, you can also set `IMAGE_PULL_POLICY=Never` when using the Cluster API (the pod spec reads this env var on the **client** that calls the Kubernetes API — set it in the shell that runs `uvicorn`).

### EKS / ECR

Push to your registry and set `GOVERNANCE_RUNNER_IMAGE` to that URI when calling `POST /v1/pods` or when starting the Cluster API.

## Run the Cluster API

```bash
cd infrastructure/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-cluster-api.txt
export KUBECONFIG=~/.kube/config   # default
export GOVERNANCE_RUNNER_IMAGE=governance-runner:latest  # optional
PYTHONPATH=. uvicorn cluster_api.main:app --host 0.0.0.0 --port 8090
```

### Create a pod

```bash
curl -sS -X POST http://127.0.0.1:8090/v1/pods \
  -H 'Content-Type: application/json' \
  -d '{"namespace":"default","wait_ready":true}'
```

The response includes `port_forward_hint` and the pod `name`.

### Port-forward to the runner

```bash
chmod +x infrastructure/backend/scripts/port-forward-pod.sh
./infrastructure/backend/scripts/port-forward-pod.sh <pod-name> 8080
```

Or use the `kubectl port-forward` line from the API response.

### Call governed chat (prompt → governance → LLM → governance)

```bash
curl -sS http://127.0.0.1:8080/v1/governed-complete \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Say hello in one sentence.","policy":{"alert_threshold":75,"block_on_alert":false},"llm":{}}'
```

With a real LLM (OpenAI-compatible `base_url`):

```bash
curl -sS http://127.0.0.1:8080/v1/governed-complete \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Hi","llm":{"base_url":"https://api.openai.com/v1","api_key":"'$OPENAI_API_KEY'","model":"gpt-4o-mini"}}'
```

Secrets: in production, inject API keys via Kubernetes Secrets + env on the pod, not via this curl example.

### Evaluate only (no LLM)

```bash
curl -sS http://127.0.0.1:8080/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"text":"some user text","phase":"pre_prompt"}'
```

## Python client (local code → port-forwarded pod)

Install `httpx` in the environment that runs your SDK or scripts:

```bash
pip install httpx
```

From repo root with `PYTHONPATH` including the repo (or install the package as editable):

```python
from infrastructure.backend.client import GovernanceRunnerClient

c = GovernanceRunnerClient("http://127.0.0.1:8080")
out = c.governed_complete("Your prompt here", llm={"base_url": "https://api.openai.com/v1", "api_key": "..."})
# out["response_text"], out["prompt_governance"], out["response_governance"], out["blocked"]
```

## Runner API reference (in-pod)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Liveness/readiness |
| POST | `/v1/evaluate` | Analyze + score text (`phase` e.g. `pre_prompt` / `post_response`) |
| POST | `/v1/governed-complete` | Full pipeline with optional LLM; returns prompt/response governance summaries |

## Optional: Kubernetes Deployment

For production, prefer a **Deployment** + **Service** instead of raw Pods created by the API. See `k8s/deployment-reference.yaml` for a starting point; keep using the same container image and port **8080**.

## Alternative architecture

- **Jobs instead of long-lived Pods**: if each user session is short-lived, create a **Job** that runs the same image, expose results via object status or a sidecar — fewer idle pods.
- **Single shared runner + session IDs**: one Deployment, multiplex requests in-process; simpler ops, weaker isolation.
- **Service mesh / auth**: front the runner with network policies and mTLS between Cluster API and runners.

The current split (pod per environment + in-pod HTTP) balances isolation and a straightforward local dev story (port-forward).
