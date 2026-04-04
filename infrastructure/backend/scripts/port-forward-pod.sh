#!/usr/bin/env bash
# Port-forward a governance runner pod to localhost (default local port 8080).
#
# Usage:
#   ./port-forward-pod.sh <pod-name> [local-port]
# Env:
#   KUBE_NAMESPACE (default: default)
set -euo pipefail

NS="${KUBE_NAMESPACE:-default}"
POD="${1:?usage: $0 <pod-name> [local-port]}"
LOCAL="${2:-8080}"
REMOTE="${REMOTE_PORT:-8080}"

echo "Forwarding ${NS}/pod/${POD}  localhost:${LOCAL} -> pod:${REMOTE}"
exec kubectl port-forward -n "${NS}" "pod/${POD}" "${LOCAL}:${REMOTE}"
