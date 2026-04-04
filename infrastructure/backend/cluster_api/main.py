"""
Local/cluster API to create governance runner Pods.

Uses kubeconfig (or in-cluster config when deployed in Kubernetes).

Run:
  cd infrastructure/backend
  pip install -r requirements-cluster-api.txt
  PYTHONPATH=. uvicorn cluster_api.main:app --reload --port 8090
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .k8s_ops import (
    create_governance_pod,
    delete_pod,
    list_governance_pods,
    wait_pod_ready,
)

app = FastAPI(title="Governance Cluster API", version="0.1.0")


class CreatePodRequest(BaseModel):
    namespace: str = Field(default_factory=lambda: os.environ.get("K8S_NAMESPACE", "default"))
    image: str = Field(
        default_factory=lambda: os.environ.get(
            "GOVERNANCE_RUNNER_IMAGE", "governance-runner:latest"
        )
    )
    wait_ready: bool = Field(
        default=False,
        description="If true, block until pod is Running (timeout 300s).",
    )
    timeout_seconds: int = 300


class CreatePodResponse(BaseModel):
    name: str
    namespace: str
    port: int
    ready: Optional[bool] = None
    port_forward_hint: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/pods", response_model=CreatePodResponse)
def create_pod(req: CreatePodRequest) -> CreatePodResponse:
    try:
        info = create_governance_pod(
            namespace=req.namespace,
            image=req.image,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    ready: Optional[bool] = None
    if req.wait_ready:
        ready = wait_pod_ready(
            namespace=info["namespace"],
            name=info["name"],
            timeout_s=req.timeout_seconds,
        )
        if not ready:
            raise HTTPException(
                status_code=504,
                detail=f"Pod {info['name']} did not become ready in time",
            )

    pf = (
        f"kubectl port-forward -n {info['namespace']} pod/{info['name']} "
        f"{info['port']}:{info['port']}"
    )
    return CreatePodResponse(
        name=info["name"],
        namespace=info["namespace"],
        port=info["port"],
        ready=ready,
        port_forward_hint=pf,
    )


@app.delete("/v1/pods/{name}")
def remove_pod(
    name: str,
    namespace: str = Query(default_factory=lambda: os.environ.get("K8S_NAMESPACE", "default")),
) -> dict[str, str]:
    try:
        delete_pod(namespace=namespace, name=name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"deleted": name, "namespace": namespace}


@app.get("/v1/pods", response_model=List[Dict[str, Any]])
def list_pods(
    namespace: str = Query(default_factory=lambda: os.environ.get("K8S_NAMESPACE", "default")),
) -> List[Dict[str, Any]]:
    try:
        return list_governance_pods(namespace=namespace)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
