# BrowserMesh on a single VPS with k3s

The full BrowserMesh (CRD + operator + control plane + dashboard) needs a
Kubernetes API. A single cheap **x86_64** VPS running **k3s** gives you exactly
that — real Pods, one per browser, each with its own viewer URL — for ~$5/mo.
No managed-cluster fees, no NAT gateway, no per-node markup.

For a managed alternative, see [gke.md](./gke.md).

## Requirements

- A VPS with **x86_64** (Hetzner CX22, DigitalOcean, Oracle x86, Linode, …),
  2 vCPU / 4 GB, Debian or Ubuntu.
- Open inbound TCP **30080** (control API) — and 6443 only if you want remote
  `kubectl`.
- The browser image is x86_64; on an ARM VPS you'd have to build an ARM image.

## 1. Install k3s

```bash
curl -sfL https://get.k3s.io | sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes
```

k3s ships a local-path storage class, so the control plane's SQLite PVC works
out of the box.

## 2. Get the code and build the images

Build on the VPS (Docker must be installed: `apt-get install -y docker.io`), or
build locally and copy the tarballs over.

```bash
git clone <your-repo> browsermesh && cd browsermesh

docker build -t browser-control:v1  -f control/Dockerfile        control
docker build -t browser-operator:v1 -f operator/Dockerfile       operator
docker build -t browser-pod:v1      -f infra/browser/Dockerfile  .
```

k3s uses containerd, not Docker, so import the images into k3s:

```bash
for img in browser-control:v1 browser-operator:v1 browser-pod:v1; do
  docker save "$img" | sudo k3s ctr images import -
done
```

(Alternatively push to a registry and update the image names.)

## 3. Deploy

```bash
kubectl create namespace browser
kubectl apply -f crds/browsers.crd.yaml
kubectl apply -f operator/operator.yaml
kubectl rollout status deployment/browser-operator -n browser --timeout=120s
kubectl apply -f control/control.yaml
kubectl rollout status deployment/browser-control  -n browser --timeout=120s
```

## 4. Create the admin + API key

```bash
IP=<your-vps-public-ip>
curl -X POST "http://$IP:30080/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"admin@browsermesh.local","password":"<a-real-password>"}'
curl -c /tmp/cookies.txt -X POST "http://$IP:30080/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@browsermesh.local","password":"<a-real-password>"}'
curl -b /tmp/cookies.txt -X POST "http://$IP:30080/keys" -H 'Content-Type: application/json' -d '{"name":"prod"}'
```

## 5. Use it

```bash
KEY=bmsk_...
curl -H "Authorization: Bearer $KEY" -X POST "http://$IP:30080/browsers" \
  -H 'Content-Type: application/json' -d '{"type":"cloak","timeout_seconds":600}'
curl -H "Authorization: Bearer $KEY" "http://$IP:30080/browsers"
```

Each browser gets its own viewer at `/browsers/{id}/vnc` (via the dashboard) —
real per-browser isolation and routing.

### Dashboard

The dashboard rewrites `/api` to `127.0.0.1:30080` for local dev. On a VPS,
point it at the public control URL before building:

- edit `dashboard/next.config.js` to rewrite `/api/:path*` to
  `http://<VPS_IP>:30080/:path*`, or
- run the dashboard on the VPS and access it through a tunnel/reverse proxy.

Then `cd dashboard && npm install && npm run build && npm start`.

## Cost

Hetzner CX22 (2 vCPU / 4 GB) ≈ €4.59/mo runs the control plane, operator, and a
couple of browsers. Browsers are Pods you create/delete on demand, so idle cost
is just the one node. (Oracle Always Free is $0 but ARM — see the image note.)

## Teardown

```bash
kubectl delete namespace browser
# and/or: /usr/local/bin/k3s-uninstall.sh
```
