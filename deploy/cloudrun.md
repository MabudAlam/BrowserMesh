# BrowserMesh on Cloud Run

Run the **browser container** on Cloud Run as a standalone, scale-to-zero,
on-demand browser (CDP + live VNC on one URL). This uses the same
`infra/browser` image as Kubernetes — no second codebase.

The **control plane, operator, and CRD are Kubernetes-only** (they need the
k8s API). On Cloud Run you get one browser per instance, autoscaled by Cloud
Run; connect to it directly.

## How it works

Cloud Run exposes exactly one port (`$PORT`), so the image ships a small
**single-port gateway** (`infra/browser/gateway.conf`) that fronts the two
internal servers:

```
$PORT (8080)
  ├── /json, /devtools  -> 127.0.0.1:9223   CDP (version JSON + browser WS)
  ├── /                 -> 127.0.0.1:6080   KasmVNC (noVNC page + /websockify)
  └── /healthz          -> 200
```

The gateway starts only when `$PORT` is set (Cloud Run) or
`BROWSER_GATEWAY=1`. In Kubernetes it does not start, so the existing
two-port contract (`6080`/`9223`) and control gateway are unchanged.

## One-shot: build, push, deploy

`cloudbuild.yaml` does all three (build → push to GCR → `gcloud run deploy`):

```bash
gcloud builds submit --config cloudbuild.yaml .
```

Grant the Cloud Build service account (`<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com`)
these roles once:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role=roles/storage.admin
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role=roles/run.admin
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role=roles/iam.serviceAccountUser
```

Override defaults with substitutions, e.g. a different region or Artifact
Registry instead of GCR:

```bash
gcloud builds submit --config cloudbuild.yaml . \
  --substitutions=_REGION=us-central1,_REGISTRY=us-central1-docker.pkg.dev,_REPO_IMAGE=browsermesh/browser-pod
```

`cloudbuild.yaml` deploys with `--allow-unauthenticated` so the noVNC page and
CDP work without tokens. Change that flag for anything non-test.

## Build and push (manual)

```bash
PROJECT=my-project
REGION=us-central1
IMAGE=$REGION-docker.pkg.dev/$PROJECT/browsermesh/browser-pod:v1

gcloud artifacts repositories create browsermesh \
  --repository-format=docker --location=$REGION 2>/dev/null || true

docker build -f infra/browser/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"
```

## Deploy

```bash
gcloud run deploy browsermesh-browser \
  --image "$IMAGE" \
  --region "$REGION" \
  --port 8080 \
  --cpu 1 --memory 2Gi \
  --concurrency 1 \
  --min-instances 0 --max-instances 5 \
  --timeout 3600 \
  --no-cpu-throttling \
  --session-affinity \
  --no-allow-unauthenticated
```

- `--concurrency 1` — one browser per instance (a browser is stateful).
- `--min-instances 0` — **scale to zero, $0 when idle**; a request cold-starts
  one browser.
- `--timeout 3600` — max request/WebSocket lifetime (60 min).
- `--no-cpu-throttling` — keeps CPU allocated while the instance is up (the
  browser keeps rendering between requests).
- `--no-allow-unauthenticated` — require a Google identity token. Add
  `--allow-unauthenticated` only if you front it with your own auth.

## Connect

Get the URL:

```bash
URL=$(gcloud run services describe browsermesh-browser \
  --region "$REGION" --format='value(status.url)')
```

**Live VNC:** open `$URL` in a browser (noVNC). If the service requires auth,
use `gcloud run services proxy browsermesh-browser --region "$REGION"` and open
`http://localhost:8080`.

**CDP (Playwright):**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # The gateway rewrites Chrome's loopback ws URL to the public host, so the
    # service URL works directly.
    browser = p.chromium.connect_over_cdp(f"{URL}")
    page = browser.contexts[0].pages[0]
    page.goto("https://example.com")
    print(page.title())
```

`GET $URL/json/version` returns `webSocketDebuggerUrl` already rewritten to
`wss://<host>/devtools/browser/<id>` if a client needs the raw ws URL.

## Caveats

- **60-minute cap** per CDP/VNC WebSocket (Cloud Run request timeout max).
  Reconnect to continue.
- **Cold start** ~ Chrome boot + Cloud Run (~5–15s); the first request after
  scale-to-zero is slower.
- **Stateless**: the profile is in `/tmp`; add a Cloud Run volume (GCS FUSE) if
  you need persistence.
- **No multi-browser API**: each instance is one browser; on-demand = Cloud Run
  autoscaling, not a `Browser` object.

## Free tier

Cloud Run's always-free monthly allowance (per billing account) is
**180,000 vCPU-seconds** and **360,000 GiB-seconds** — about **50 hours of a
1 vCPU / 2 GiB browser**. Scale-to-zero means idle costs nothing.
