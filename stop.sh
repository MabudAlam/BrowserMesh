#!/usr/bin/env bash
# Stop BrowserMesh locally: delete the kind cluster and clear any stale node
# container still holding :30080 (e.g. a pre-rename cluster or a failed create).
set -euo pipefail

CLUSTER=browsermesh

printf '\033[1mBrowserMesh local stop\033[0m  cluster=%s\n' "$CLUSTER"

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "[1/2] Deleting kind cluster '$CLUSTER'..."
  kind delete cluster --name "$CLUSTER"
else
  echo "[1/2] No kind cluster '$CLUSTER'."
fi

echo "[2/2] Clearing leftover node containers..."
leftovers=$(docker ps -a --format '{{.Names}}' \
  | grep -E '^(browserstation|browsermesh)-control-plane$' || true)
if [ -n "$leftovers" ]; then
  while read -r c; do
    echo "      removing '$c'"
    docker rm -f "$c" >/dev/null
  done <<< "$leftovers"
else
  echo "      none"
fi

echo "Stopped."
