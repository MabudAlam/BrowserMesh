# BrowserMesh — architecture (plain English)

## What this is

BrowserMesh is a small platform that runs **headed browsers on demand** —
each one isolated, drivable, and watchable live. It's built to be **browser
agnostic**: it doesn't care whether a browser is CloakBrowser, stock Chromium,
or Firefox. It only cares that each browser:

1. runs **headed** on a virtual display, and
2. exposes a **CDP** socket (the protocol tools use to control it).

If a new browser can do those two things, it can be added to the platform.

---

## The big picture

```
                 ┌─────────────────────────────────────────────┐
  dashboard ────►│            CONTROL PLANE                    │
  driver ───────►│   control service  (FastAPI, :30080)        │
                 │      · declares Browsers                    │
                 │      · gateways CDP + VNC to them           │
                 └───────────────────┬─────────────────────────┘
                                     │ Kubernetes API
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │          OPERATOR  (the "watcher")           │
                 │   sees a Browser declared ──► creates Pod    │
                 └───────────────────┬─────────────────────────┘
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │          BROWSER POD  (one per browser)      │
                 │   ┌───────────────────────────────────────┐  │
                 │   │  KasmVNC   = a virtual screen + video │  │
                 │   │  CloakBrowser = draws onto that screen│  │
                 │   │  CDP       = a socket for control     │  │
                 │   └───────────────────────────────────────┘  │
                 └─────────────────────────────────────────────┘
```

Three ideas to hold onto:

1. **Control plane vs. data plane**
   The control plane *decides* (API + operator). The Pods *do* the work.
   They scale independently — you can have 2 control replicas and 100 browser Pods.

2. **Declarative, not imperative**
   You don't tell the system "create a Pod". You **declare a Browser**, and a
   controller makes that real and keeps it real. This is how big platforms work:
   state in, reality follows.

3. **Gateway = one front door**
   All traffic to a browser flows through the control service, which connects to
   the Pod *server-side*. Clients never touch Pod IPs directly, and we solve
   networking quirks (like noVNC vs KasmVNC) in exactly one place.

---

## What each part does

| Part | Role | Folder |
|---|---|---|
| **Browser** (custom resource) | The *declared goal*: "I want a browser of type X" | `crds/` |
| **Operator** | Watches Browsers; creates/deletes the Pod that backs each one | `operator/` |
| **Control service** | The API + gateway: manage Browsers, relay CDP/VNC | `control/` |
| **Browser image** | What runs in a Pod: KasmVNC + a headed engine | `infra/browser/` |
| **Dashboard** | The UI you click (list, view, delete) | `dashboard/` |

---

## The lifecycle of a browser (walkthrough)

1. You click **New Browser** → the dashboard calls `POST /browsers`.
2. The control service writes a `Browser` custom resource (it does *not* create a Pod).
3. The **operator** sees the new `Browser`, builds a matching Pod, and watches it.
4. When the Pod is ready, the operator writes its IP + URLs into `Browser.status`.
5. The dashboard reads that status and shows it as **Running**.
6. Click **View** → the dashboard opens a VNC websocket through the control
   service, which relays to the Pod's KasmVNC → you see it live.
7. Drive it → a driver (QuickCrawl/chromedp) connects over CDP through the gateway.
8. Click **Delete** → the control service deletes the `Browser`. Because the Pod
   *belongs to* the Browser (ownerReference), Kubernetes deletes the Pod too.

---

## Why "one browser = one Pod" is a good idea

- **Isolation** — a crashed or out-of-memory browser only hurts itself.
- **Fair resource use** — each Pod has a memory limit; many fit on a machine.
- **Scale** — add browsers and they spread across machines; the cluster autoscaler
  adds machines when browsers are waiting for space.
- **Browser-agnostic** — the Pod is the unit; only the image inside changes.

---

## Scaling (short version)

- **Many browsers**: the Kubernetes scheduler places each browser Pod on a machine
  that has room.
- **More machines than you have**: when browser Pods are *waiting* for space, a
  **cluster autoscaler** (e.g. Karpenter) adds a machine automatically.
- **Many users/requests**: the control service is stateless — run a few replicas
  behind a load balancer.

On a single local node (kind/minikube) you're limited to that one machine; the
pattern unlocks its real power on a multi-node cluster (EKS/GKE/AKS).

---

## Repo map

```
browsermesh/
├── commands.md            # copy-paste setup/run commands
├── architecture.md        # this file
├── crds/
│   └── browsers.crd.yaml  # the Browser custom resource
├── control/               # control plane (FastAPI, uv-managed)
│   ├── app/
│   │   ├── main.py        # app entry (CORS + router)
│   │   ├── routes.py      # HTTP/WebSocket endpoints (thin)
│   │   ├── controller.py  # business logic: Kubernetes / Browser CRs
│   │   ├── rfb.py         # transport: relay + adapt the VNC stream
│   │   └── config.py      # constants / env
│   ├── pyproject.toml     # uv project
│   ├── Dockerfile
│   └── control.yaml       # k8s manifests (RBAC + Deployment + Service)
├── operator/              # the reconciler (kopf, uv-managed)
│   ├── controller.py      # turns Browser objects into Pods
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── operator.yaml      # k8s manifests (RBAC + Deployment)
├── infra/
│   ├── browser/           # per-browser engine image
│   │   ├── boot.py        # boots KasmVNC + headed engine + CDP forwarder
│   │   └── Dockerfile
│   └── kind-config.yaml   # local kind cluster config
└── dashboard/             # Next.js UI (dark, sidebar layout)
```

---

## Design notes (why we chose what we chose)

- **Python (FastAPI + kopf)** — the existing code was Python; fastest to a working,
  correct platform. (A bank might standardize on Go operators, but the pattern is
  identical.)
- **Browser as a CRD** — this is what turns a bunch of scripts into a *platform*:
  state is declarative, reconcile-able, and auditable.
- **Gateway in the control plane** — keeps Pod IPs private and concentrates the
  one gnarly protocol problem (noVNC ↔ KasmVNC RFB) into one maintainable file.
