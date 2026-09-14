#!/usr/bin/env bash
# Start BrowserMesh locally on kind: clean cluster -> build -> load -> deploy ->
# auth -> smoke test (create a browser, confirm Chrome CDP answers, delete it).
#
#   ./start.sh
#
# Requires: docker, kind, kubectl, curl. Run from the repo root (or anywhere).
set -euo pipefail

CLUSTER=browsermesh
NAMESPACE=browser
CONTROL_URL=http://127.0.0.1:30080
# Local dev defaults; override with env for anything non-local.
ADMIN_EMAIL="${BROWSERMESH_ADMIN_EMAIL:-admin@browsermesh.local}"
ADMIN_PASSWORD="${BROWSERMESH_ADMIN_PASSWORD:-changeme123}"
COOKIES=/tmp/browsermesh-cookies.txt
TOTAL_STEPS=8

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

STEP=0
START_TS=$SECONDS
step()  { STEP=$((STEP + 1)); printf '\n\033[1;36m[%d/%d] %s\033[0m\n' "$STEP" "$TOTAL_STEPS" "$*"; }
info()  { printf '      %s\n' "$*"; }
done_() { printf '      \033[0;32mok\033[0m (%ss)\n' "$((SECONDS - START_TS))"; }

printf '\033[1mBrowserMesh local start\033[0m  cluster=%s  namespace=%s\n' "$CLUSTER" "$NAMESPACE"

step "Stopping any existing cluster"
./stop.sh
done_ ""

step "Creating kind cluster"
kind create cluster --config infra/kind-config.yaml
done_ ""

step "Building images"
for spec in "browser-control:v1|control/Dockerfile|control" \
            "browser-operator:v1|operator/Dockerfile|operator" \
            "browser-pod:v1|infra/browser/Dockerfile|."; do
  IFS='|' read -r tag dockerfile ctx <<< "$spec"
  info "building $tag  (docker build -f $dockerfile $ctx)"
  docker build -t "$tag" -f "$dockerfile" "$ctx"
done
done_ ""

step "Loading images into kind"
for img in browser-control:v1 browser-operator:v1 browser-pod:v1; do
  info "loading $img"
  kind load docker-image "$img" --name "$CLUSTER"
done
done_ ""

step "Deploying CRD, operator, and control plane"
info "namespace/$NAMESPACE"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
info "crds/browsers.crd.yaml"
kubectl apply -f crds/browsers.crd.yaml
info "operator/operator.yaml"
kubectl apply -f operator/operator.yaml
info "waiting for browser-operator..."
kubectl rollout status deployment/browser-operator -n "$NAMESPACE" --timeout=120s
info "control/control.yaml"
kubectl apply -f control/control.yaml
info "waiting for browser-control..."
kubectl rollout status deployment/browser-control -n "$NAMESPACE" --timeout=120s
done_ ""

step "Waiting for the control API"
code=""
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$CONTROL_URL/browsers" || true)
  printf '\r      attempt %2d/30  http %s' "$i" "${code:----}"
  [ "$code" = "401" ] && break
  sleep 2
done
printf '\n'
[ "$code" = "401" ] || { echo "control not reachable at $CONTROL_URL (got '$code')"; exit 1; }
done_ ""

step "Creating admin account and API key"
info "register $ADMIN_EMAIL"
curl -s -X POST "$CONTROL_URL/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" >/dev/null
info "login"
curl -s -c "$COOKIES" -X POST "$CONTROL_URL/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" >/dev/null
info "mint API key"
API_KEY=$(curl -s -b "$COOKIES" -X POST "$CONTROL_URL/keys" -H 'Content-Type: application/json' \
  -d '{"name":"local"}' | sed -E 's/.*"key":"([^"]+)".*/\1/')
[ -n "$API_KEY" ] || { echo "failed to mint API key"; exit 1; }
done_ ""

step "Smoke test: create -> wait -> check Chrome CDP -> delete"
AUTH="Authorization: Bearer $API_KEY"
ID=$(curl -s -H "$AUTH" -X POST "$CONTROL_URL/browsers" -H 'Content-Type: application/json' \
  -d '{"type":"cloak","timeout_seconds":300}' | sed -E 's/.*"browser_id":"([^"]+)".*/\1/')
[ -n "$ID" ] || { echo "failed to create browser"; exit 1; }
info "created browser br-$ID"

phase=""
for i in $(seq 1 60); do
  S=$(curl -s -H "$AUTH" "$CONTROL_URL/browsers/$ID")
  phase=$(echo "$S" | sed -E 's/.*"status":"([^"]+)".*/\1/')
  printf '\r      waiting for Running  attempt %2d/60  phase=%s' "$i" "$phase"
  [ "$phase" = "Running" ] && break
  [ "$phase" = "Failed" ] && { printf '\n'; echo "$S"; exit 1; }
  sleep 3
done
printf '\n'
[ "$phase" = "Running" ] || { echo "browser did not become Running"; exit 1; }

info "checking Chrome CDP inside the pod"
ok=""
for _ in $(seq 1 15); do
  if kubectl exec "br-$ID" -n "$NAMESPACE" -- python -c \
      "import json,urllib.request; print('      CDP Browser:', json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/version'))['Browser'])" 2>/dev/null; then
    ok=1; break
  fi
  sleep 2
done
[ -n "$ok" ] || { echo "Chrome CDP not responding inside the pod"; exit 1; }

info "deleting the test browser"
curl -s -H "$AUTH" -X DELETE "$CONTROL_URL/browsers/$ID" >/dev/null
done_ ""

printf '\n\033[1;32mBrowserMesh is up.\033[0m\n'
echo "  Control:   $CONTROL_URL"
echo "  API key:   $API_KEY"
echo "  Dashboard: cd dashboard && npm run dev   ->  http://localhost:4003"
echo "  Stop:      ./stop.sh"
