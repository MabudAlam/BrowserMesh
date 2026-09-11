# Commands — the two things you actually run

Most of the time you only need two lists of commands:

1. **First time setup** — run once when setting up a machine/cluster.
2. **Normal change cycle** — run whenever you edit code and want it deployed.

This repo has three things you build/deploy: the **control service**, the
**operator**, and the per-browser image. The "change cycle" is the same for each.

---

## 1. First time setup (run once)

### Start a cluster

```bash
# kind (this project's default). Exposes the control plane on :30080.
kind create cluster --config infra/kind-config.yaml

# minikube instead
minikube start --driver=docker --cpus=4 --memory=8192
```

### Build + load the three images

```bash
docker build -t browser-control:v1  -f control/Dockerfile        control
docker build -t browser-operator:v1 -f operator/Dockerfile       operator
docker build -t browser-pod:v1      -f infra/browser/Dockerfile  .

# minikube
minikube image load browser-control:v1 && minikube image load browser-operator:v1 && minikube image load browser-pod:v1
# kind
kind load docker-image browser-control:v1  --name browsermesh
kind load docker-image browser-operator:v1 --name browsermesh
kind load docker-image browser-pod:v1      --name browsermesh
```

### Install the pieces (order matters)

```bash
kubectl create namespace browser
kubectl apply -f crds/browsers.crd.yaml   # register the "Browser" resource type
kubectl apply -f operator/operator.yaml   # deploy the operator (reconciler)
kubectl rollout status deployment/browser-operator -n browser --timeout=120s
kubectl apply -f control/control.yaml     # deploy the control plane (API/gateway)
kubectl rollout status deployment/browser-control  -n browser --timeout=120s
```

Check it once:

```bash
curl http://127.0.0.1:30080/browsers      # -> {"browsers":[]}
```

That's it — setup done. You won't re-run this unless you tear the cluster down.

---

## 2. Normal change cycle (when you edit code)

Same 3 steps, for whichever component you changed:

```bash
# 1) rebuild that one image
docker build -t browser-control:v1 -f control/Dockerfile control
#    (or: browser-operator:v1 / browser-pod:v1 for the other two)

# 2) push the new image into the cluster
kind load docker-image browser-control:v1 --name browsermesh
#    (minikube: minikube image load browser-control:v1)

# 3) restart the running service so it uses the new image
kubectl rollout restart deployment/browser-control -n browser
```

That's the entire loop:

```
edit code  →  docker build  →  kind load  →  kubectl rollout restart
```

If you changed the **browser-pod** image, restart a browser (delete + recreate it)
rather than a deployment — Pods are created on demand.

---

## Auth (single admin + API keys)

The control service has a built-in, contained auth system: one admin account
(email + password) and any number of API keys, stored in SQLite on a PVC.

```bash
# 1) create the admin account (once)
curl -X POST http://127.0.0.1:30080/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"changeme123"}'

# 2) log in (stores a session cookie)
curl -c cookies.txt -X POST http://127.0.0.1:30080/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"changeme123"}'

# 3) mint an API key for the SDK/drivers (plaintext shown once, also viewable later)
curl -b cookies.txt -X POST http://127.0.0.1:30080/keys -H 'Content-Type: application/json' -d '{"name":"quickcrawl"}'
curl -b cookies.txt http://127.0.0.1:30080/keys                 # list (masked)
curl -b cookies.txt http://127.0.0.1:30080/keys/1/reveal        # view the key again
curl -b cookies.txt -X DELETE http://127.0.0.1:30080/keys/1     # revoke (soft)
curl -b cookies.txt -X DELETE "http://127.0.0.1:30080/keys/1?permanent=true"  # delete permanently
```

**Enforcement is off by default** (self-hosted, localhost). To require a session
cookie or `Authorization: Bearer bmsk_...` key on `/browsers*`, set
`BROWSERMESH_REQUIRE_AUTH=true` in the control Deployment (or env) and restart.
API clients then send:

```bash
curl -H "Authorization: Bearer bmsk_..." http://127.0.0.1:30080/browsers
```

The browser VNC WebSocket can't send headers, so the dashboard mints a
short-lived viewer token via `POST /browsers/{id}/viewer-token` and appends
`?token=...` to the ws URL. CDP clients use the API key.

---

## Everyday usage (the app, not deploys)

```bash
# Create / list / delete a browser (through the API, like the dashboard)
# timeout_seconds auto-destroys the browser after N seconds (omit -> 20 min default).
curl -X POST http://127.0.0.1:30080/browsers -H 'Content-Type: application/json' -d '{"type":"cloak","timeout_seconds":300}'
curl http://127.0.0.1:30080/browsers
curl -X DELETE http://127.0.0.1:30080/browsers/<id>            # delete (Pod GC'd)

# Or via kubectl directly
kubectl apply -f - <<'EOF'
apiVersion: browsermesh.dev/v1
kind: Browser
metadata: { name: demo, namespace: browser }
spec: { type: cloak }
EOF
kubectl delete browser demo -n browser

# Logs / status when debugging
kubectl get all -n browser
kubectl logs -n browser deploy/browser-control
kubectl logs -n browser deploy/browser-operator
kubectl logs <browser-pod> -n browser
kubectl get browser -n browser
```

---

## Toolbox (what these tools are)

| Tool | Role |
|---|---|
| **kind** | A whole Kubernetes cluster running inside Docker on your laptop (the cluster itself). |
| **kubectl** | The remote control that talks to the cluster (`apply`, `get`, `delete`, `logs`). |
| **helm** | An installer that installs pre-packaged apps (charts) into Kubernetes. You only needed it for Kuberay, which this project no longer uses. |

---

## Mental model

- **Setup** (first time): make a cluster, load images, install CRD + operator + control.
- **Change cycle** (daily): edit → rebuild one image → reload → restart.
- **Use**: create/view/delete browsers through `:30080`.
