# Deploying BrowserMesh (production, cheap)

BrowserMesh runs **headed browsers** (a container with KasmVNC + Chrome), so it
must run on Linux containers — not serverless functions. The cost levers are the
same everywhere:

1. **Spot / preemptible nodes** for the browser Pods (the operator self-heals if
   one is reclaimed).
2. **Scale to zero** when idle — browsers auto-expire (default 20 min), and the
   operator runs no browser Pods when none are declared.
3. **Right-size memory** (each browser is ~1–2 GiB) and **pack** browsers per node.
4. **Watch egress** — for scrapers, network egress often costs more than compute.

> Architecture is unchanged from local: `crds/` + `operator/` + `control/` +
> `infra/browser/`. Only the image registry, ingress, and node pools change.

---

## Cheapest host options

| Option | Rough cost | Ops | Notes |
|---|---|---|---|
| **Hetzner Cloud + k3s** | ~€5–15/mo per VM | medium | Cheapest real option; one VM runs control+operator, add VMs for browsers. |
| **Oracle Cloud Always Free (ARM)** | **$0** | medium | 4 ARM cores / 24 GB free; enough for a few browsers + control. |
| **GKE Autopilot** | pay per Pod, scales to zero | low | Simplest; browser Pods cost only while running. |
| **GKE Standard + spot node pool** | low | low | Free zonal control plane; spot VMs ~60–80% off. |
| **DigitalOcean DOKS** | from $12/mo/node | low | Simple managed k8s; add a spot-ish pool. |
| **Fly.io / Railway / Render** | usage | low | Great for the control plane, **not** for browser Pods. |

**Recommendation:** for "cheap but managed", use **GKE with a spot browser node
pool + autoscaler**; for "cheapest overall", **Hetzner (or Oracle free) + k3s**.

---

## GKE, step by step

### 1. Push images to a registry
```bash
# One-time: create a repo
gcloud artifacts repositories create browsermesh --repository-format=docker --location=us-central1

REG=us-central1-docker.pkg.dev/$PROJECT_ID/browsermesh
docker build -t $REG/browser-control:v1  -f control/Dockerfile        control
docker build -t $REG/browser-operator:v1 -f operator/Dockerfile       operator
docker build -t $REG/browser-pod:v1      -f infra/browser/Dockerfile  .
docker push $REG/browser-control:v1
docker push $REG/browser-operator:v1
docker push $REG/browser-pod:v1
```
Update the `image:` fields in `control/control.yaml`, `operator/operator.yaml`,
and `operator/controller.py` (`ENGINE_IMAGES["cloak"]`) to the `$REG/...` paths.

### 2. Create the cluster with a spot browser pool
```bash
gcloud container clusters create browsermesh --zone us-central1-a \
  --num-nodes 1 --machine-type e2-small --enable-autoscaling --min-nodes 1 --max-nodes 1

# Browser worker pool on spot (cheap), autoscaled, memory-leaning
gcloud container node-pools create browsers --cluster browsermesh --zone us-central1-a \
  --machine-type e2-standard-4 --spot --num-nodes 0 \
  --enable-autoscaling --min-nodes 0 --max-nodes 10 \
  --node-taints browsers=true:NoSchedule
```
Then have the operator put browser Pods on that pool (add the toleration +
nodeSelector to `_pod_spec` in `operator/controller.py`):
```python
"nodeSelector": {"cloud.google.com/gke-spot": "true"},
"tolerations": [{"key": "browsers", "operator": "Exists", "effect": "NoSchedule"}],
```
The cluster autoscaler adds a spot node when browsers are `Pending` and removes
it when idle → you pay only while browsers run.

### 3. Secrets + namespace + deploy
```bash
kubectl create namespace browser
kubectl -n browser create secret generic browsermesh-auth \
  --from-literal=session-secret="$(openssl rand -hex 32)"

kubectl apply -f crds/browsers.crd.yaml
kubectl apply -f operator/operator.yaml
kubectl apply -f control/control.yaml
```
(The control Deployment already reads `BROWSERMESH_SESSION_SECRET` from that secret.)

### 4. Expose the control plane (pick one)
- **Cheapest:** Cloudflare Tunnel (`cloudflared`) → no load balancer bill, free TLS.
- **Native:** change the control `Service` from `NodePort` to `LoadBalancer`
  (or add an `Ingress`). Then set the dashboard's `NEXT_PUBLIC_API_URL`.

### 5. Dashboard
Host it off-cluster (cheapest + no build in k8s):
- **Vercel** / **Cloudflare Pages**: point `NEXT_PUBLIC_API_URL` at the control
  plane's public URL, and set `NEXT_PUBLIC_API_KEY`... **no** — with auth on, the
  dashboard logs in (session cookie) and mints keys; do **not** embed a key.

---

## Hetzner (or Oracle free) + k3s — cheapest overall

```bash
# On a fresh Ubuntu VM:
curl -sfL https://get.k3s.io | sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Build + import images locally (no registry needed on a single node):
docker build -t browser-control:v1  -f control/Dockerfile        control
docker build -t browser-operator:v1 -f operator/Dockerfile       operator
docker build -t browser-pod:v1      -f infra/browser/Dockerfile  .
docker save browser-control:v1 browser-operator:v1 browser-pod:v1 | k3s ctr images import -

kubectl create namespace browser
kubectl -n browser create secret generic browsermesh-auth --from-literal=session-secret="$(openssl rand -hex 32)"
kubectl apply -f crds/browsers.crd.yaml -f operator/operator.yaml -f control/control.yaml
```
Put it behind **Cloudflare Tunnel** for TLS + public access without a load
balancer. Scale browsers by adding VMs to the k3s cluster (k3s agent) — the
scheduler spreads browser Pods automatically.

---

## Cost checklist

- [ ] Browser Pods run on **spot/preemptible** nodes (operator self-heals kills).
- [ ] **Scale to zero**: no browser Pods when idle (auto-expiry + autoscaler to 0).
- [ ] Right-size memory; pack ~6–7 browsers per 16 GB node.
- [ ] Use **Cloudflare Tunnel** instead of a cloud LoadBalancer.
- [ ] Dashboard on **Vercel/Cloudflare Pages** (free tier).
- [ ] Set budgets/alerts; monitor **egress** (scraping traffic).
- [ ] Rotate `browsermesh-auth/session-secret`; never commit real secrets.
