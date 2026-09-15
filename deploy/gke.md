# BrowserMesh on GKE (zonal Standard, free control plane)

GKE's free tier gives **$74.40/month of credit per billing account — one free
*zonal Standard* (or Autopilot) cluster's management fee** ($0.10/cluster/hour).
It covers the **control plane only, not compute**. So the control plane is
effectively free and you pay only for the nodes your browsers run on.

Full BrowserMesh (CRD + operator + control plane) runs unmodified, giving real
per-browser Pods and per-browser viewer URLs.

## Shape (cheap, on-demand)

- **Zonal** Standard cluster — regional clusters get **no** free credit (~$73/mo).
- **System node pool** — one small on-demand node (control + operator).
- **Browser node pool** — **Spot**, autoscaling **0↔N**, tainted so only
  browsers land there.
- Expose the control API with **Cloudflare Tunnel** (free) instead of a
  LoadBalancer (~$18/mo), or a LoadBalancer if you prefer.

Idle ≈ one `e2-small` (~$13/mo) + cluster fee (covered) ≈ **~$13/mo**. Browsers
cost only while a Pod runs, on spot.

> Avoid **GKE Enterprise** and **Extended support** (extra fees), and **regional**
> clusters (no free-tier credit).

## 1. Create the cluster

```bash
PROJECT=my-project
ZONE=us-central1-a
gcloud config set project $PROJECT

gcloud container clusters create browsermesh \
  --zone $ZONE --num-nodes 1 --machine-type e2-small \
  --release-channel regular
```

The $0.10/hr management fee is covered by the free-tier credit (one zonal
cluster).

## 2. Browser node pool (scales to zero)

```bash
gcloud container node-pools create browsers \
  --cluster browsermesh --zone $ZONE \
  --machine-type e2-medium \
  --num-nodes 0 --min-nodes 0 --max-nodes 5 \
  --node-taints browsers=true:NoSchedule \
  --enable-autoscaling
```

Idle = **0 nodes = $0**; a browser only costs while it runs (~$0.05/hr for
`e2-medium` on-demand).

> **Spot is cheaper (~60–80% off) but not guaranteed.** If you add `--spot` and
> the zone is out of spot capacity, the autoscaler fails with
> `FailedScaleUp: GCE out of resources` and browser Pods stay **Pending** until
> capacity frees up. For a reliable on-demand service, use **on-demand** (as
> above) and rely on scale-to-zero for the idle savings. If you want spot, try a
> different machine type/size or retry later.

## 3. Build and push the images

```bash
REG=us-central1-docker.pkg.dev/$PROJECT/browsermesh
gcloud artifacts repositories create browsermesh \
  --repository-format=docker --location=us-central1
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build for linux/amd64. GKE nodes are amd64, so on an Apple Silicon Mac this is
# required (otherwise: "exec format error"). --push builds and pushes at once.
docker buildx build --platform linux/amd64 -t $REG/browser-control:v1  -f control/Dockerfile control --push
docker buildx build --platform linux/amd64 -t $REG/browser-operator:v1 -f operator/Dockerfile operator --push
docker buildx build --platform linux/amd64 -t $REG/browser-pod:v1      -f infra/browser/Dockerfile . --push
```

Then point the manifests at the registry:
- `control/control.yaml` → `image: $REG/browser-control:v1`
- `operator/operator.yaml` → `image: $REG/browser-operator:v1`
- set the browser image via the operator env `BROWSER_IMAGE_CLOAK=$REG/browser-pod:v1`

## 4. Pin browser Pods to the spot pool

Uncomment the env block in `operator/operator.yaml`:

```yaml
        env:
        - name: BROWSER_IMAGE_CLOAK
          value: us-central1-docker.pkg.dev/PROJECT/browsermesh/browser-pod:v1
        - name: BROWSER_NODE_SELECTOR
          value: '{"cloud.google.com/gke-nodepool":"browsers"}'
        - name: BROWSER_TOLERATIONS
          value: '[{"key":"browsers","operator":"Equal","value":"true","effect":"NoSchedule"}]'
```

The operator adds these to each browser Pod (empty by default, so kind is
unaffected).

## 5. Deploy

```bash
kubectl create namespace browser
kubectl apply -f crds/browsers.crd.yaml
kubectl apply -f operator/operator.yaml
kubectl rollout status deployment/browser-operator -n browser --timeout=120s
kubectl apply -f control/control.yaml
kubectl rollout status deployment/browser-control  -n browser --timeout=120s
```

## 6. Expose the control API

**LoadBalancer (simple):**

```bash
kubectl -n browser patch svc browser-control -p '{"spec":{"type":"LoadBalancer"}}'
kubectl -n browser get svc browser-control -w   # wait for EXTERNAL-IP
```

**Cloudflare Tunnel (free):** run `cloudflared` in-cluster pointing at
`http://browser-control.browser.svc.cluster.local:8000`.

## 7. Use it

```bash
IP=<EXTERNAL-IP or tunnel host>
curl -X POST "http://$IP/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"admin@browsermesh.local","password":"<a-real-password>"}'
curl -c /tmp/c -X POST "http://$IP/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@browsermesh.local","password":"<a-real-password>"}'
KEY=$(curl -s -b /tmp/c -X POST "http://$IP/keys" -H 'Content-Type: application/json' -d '{"name":"gke"}' \
  | sed -E 's/.*"key":"([^"]+)".*/\1/')

curl -H "Authorization: Bearer $KEY" -X POST "http://$IP/browsers" \
  -H 'Content-Type: application/json' -d '{"type":"cloak","timeout_seconds":600}'
```

## Cost summary

| Item | Cost |
|---|---|
| Cluster management (zonal Standard) | **$0** (covered by $74.40/mo free credit) |
| System node (e2-small, on-demand) | ~$13/mo |
| Browser nodes (e2-medium, **spot**, scale 0↔N) | only while a browser runs |
| LoadBalancer | ~$18/mo (skip with Cloudflare Tunnel) |
| Egress | varies (scraping can dominate) |

## Autopilot instead?

Autopilot also gets the free-tier credit, and bills per Pod (vCPU + memory per
second; spot compute classes are ~60–90% off). But our operator creates **bare
Pods** with `restartPolicy: Never`, which Autopilot manages differently — it may
inject defaults or reject fields. **Standard zonal is the safer fit** for
BrowserMesh today; Autopilot would need operator changes (a controller/Job per
browser).

## vs k3s on a VPS

k3s on a ~$5 VPS has no control-plane fee and is simpler; GKE gives a managed
control plane, autoscaling, and cheap spot nodes. With the free tier the GKE
control plane is $0, but you still run a system node (~$13/mo) vs ~$5/mo total
for k3s.
