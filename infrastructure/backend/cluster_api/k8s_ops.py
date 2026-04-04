from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List

from kubernetes import client, config


def load_config() -> None:
    """Load in-cluster config if available, else kubeconfig."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


def create_governance_pod(
    *,
    namespace: str,
    image: str,
    port: int = 8080,
    name_prefix: str = "gov-runner",
) -> Dict[str, Any]:
    load_config()
    core = client.CoreV1Api()
    pod_name = f"{name_prefix}-{uuid.uuid4().hex[:8]}"

    pod = client.V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=client.V1ObjectMeta(
            name=pod_name,
            namespace=namespace,
            labels={
                "app": "governance-runner",
                "component": "execution",
            },
        ),
        spec=client.V1PodSpec(
            restart_policy="Always",
            containers=[
                client.V1Container(
                    name="runner",
                    image=image,
                    image_pull_policy=os.environ.get("IMAGE_PULL_POLICY", "IfNotPresent"),
                    ports=[client.V1ContainerPort(container_port=port, name="http")],
                    readiness_probe=client.V1Probe(
                        http_get=client.V1HTTPGetAction(path="/healthz", port=port),
                        initial_delay_seconds=3,
                        period_seconds=5,
                    ),
                    liveness_probe=client.V1Probe(
                        http_get=client.V1HTTPGetAction(path="/healthz", port=port),
                        initial_delay_seconds=10,
                        period_seconds=15,
                    ),
                    resources=client.V1ResourceRequirements(
                        requests={"cpu": "100m", "memory": "256Mi"},
                        limits={"cpu": "500m", "memory": "512Mi"},
                    ),
                )
            ],
        ),
    )
    core.create_namespaced_pod(namespace=namespace, body=pod)
    return {"name": pod_name, "namespace": namespace, "port": port}


def delete_pod(*, namespace: str, name: str) -> None:
    load_config()
    core = client.CoreV1Api()
    core.delete_namespaced_pod(name=name, namespace=namespace)


def list_governance_pods(*, namespace: str) -> List[Dict[str, Any]]:
    load_config()
    core = client.CoreV1Api()
    pods = core.list_namespaced_pod(
        namespace=namespace,
        label_selector="app=governance-runner",
    )
    out: List[Dict[str, Any]] = []
    for p in pods.items:
        phase = p.status.phase if p.status else None
        out.append(
            {
                "name": p.metadata.name,
                "namespace": p.metadata.namespace,
                "phase": phase,
            }
        )
    return out


def wait_pod_ready(*, namespace: str, name: str, timeout_s: int = 300) -> bool:
    """Block until pod phase Running and ready (best-effort)."""
    import time

    load_config()
    core = client.CoreV1Api()
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        p = core.read_namespaced_pod(name=name, namespace=namespace)
        phase = p.status.phase if p.status else None
        if phase == "Running":
            conditions = (p.status.conditions or []) if p.status else []
            ready = any(
                getattr(c, "type", None) == "Ready" and getattr(c, "status", None) == "True"
                for c in conditions
            )
            if ready or not conditions:
                return True
        if phase in ("Failed", "Succeeded"):
            return False
        time.sleep(2)
    return False
