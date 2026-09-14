# BrowserMesh

Run **real, headed browsers on demand** — each one isolated, drivable, and
watchable live. BrowserMesh is browser-agnostic: add an engine (CloakBrowser
today, stock Chromium or Firefox tomorrow) and the whole platform works unchanged.

## Why it exists

Automation tools (scrapers, agents) need a real browser they can **drive** (CDP)
and **watch** (live video). BrowserMesh makes "give me a browser" a simple,
scalable platform primitive instead of a per-app headache.

```
 one browser  =  one isolated Pod  =  KasmVNC (video) + headed engine (CDP)
```

BrowserMesh runs two ways:

- **Kubernetes (full platform)** — a control plane + operator create, list, and
  destroy browsers on demand, each with its own viewer URL. Best for multi-user
  and long-lived setups.
- **Serverless (Cloud Run)** — one container = one browser, deployed as a single
  service. Scale-to-zero, pay only while connected, no cluster to run. Best for
  **single-use / occasional automation** (a scrape, one agent run) at near-zero
  cost. See [Serverless (Cloud Run)](#serverless-cloud-run--cheap-single-use-browsers).

## How it works

```
 dashboard ──►  control service ──►  writes a "Browser"  ──►  operator creates the Pod
 driver     ──►   (:30080)             custom resource         (and keeps it alive)
                        └── gateways CDP + VNC to the Pod ──►  you watch + drive it
```

- **Declare, don't script.** You ask for a `Browser`; a controller makes it real
  and keeps it real (recreates it if it dies, cleans up when you delete it).
- **One browser = one Pod.** Crash/OOM isolated, with its own memory limit.
- **Browser-agnostic.** The Pod is the unit; only the engine image inside varies.

## Layout

| Folder | What it is |
|---|---|
| `crds/` | The `Browser` custom-resource definition (the "order slip") |
| `operator/` | The reconciler: turns a `Browser` object into a Pod |
| `control/` | The API + gateway (manage browsers, relay CDP/VNC) |
| `infra/browser/` | The per-browser engine image (KasmVNC + a headed browser) |
| `dashboard/` | The web UI (list, view, delete) |
| `sdk/` | Go + Python clients (control-plane **and** serverless modes) |
| `examples/` | Runnable demos (`raw_cdp.py`, browser-use agents) |
| `deploy/` | Cloud Run deploy guide + live stats script |
| `cloudbuild.yaml` | Cloud Build: build → push → deploy the browser image |
| `commands.md` | Setup + change-cycle commands |
| `architecture.md` | Plain-English design notes |

## Quick start

See **[commands.md](./commands.md)** — it has the two things you'll run:
**first-time setup** and the **normal change cycle**.

High level:

```bash
# one command: clean cluster -> build -> load -> deploy -> smoke test
./start.sh

# daily: dashboard
cd dashboard && npm install && npm run dev     # http://localhost:4003
```

`./stop.sh` tears the cluster down; `./stats.sh` shows live Cloud Run stats
(see the serverless section below).

## Using it

- **Dashboard:** open `http://localhost:4003` → **New Browser** → **View** to
  watch it live; **Copy CDP URL** to drive it with QuickCrawl / chromedp.
- **API:**
  ```bash
  curl -X POST http://127.0.0.1:30080/browsers -H 'Content-Type: application/json' -d '{"type":"cloak"}'
  curl http://127.0.0.1:30080/browsers
  curl -X DELETE http://127.0.0.1:30080/browsers/<id>
  ```
- **SDK** (Go + Python):
  ```python
  from browsermesh import Client, CreateOptions
  client = Client("http://127.0.0.1:30080", "bmsk_...")
  with client.with_browser(CreateOptions(type="cloak", timeout_seconds=300)) as b:
      print("drive:", client.cdp_url(b.id))
  ```

## Serverless (Cloud Run) — cheap single-use browsers

For occasional, single-use work (one scrape, one agent run) a whole cluster is
overkill. The **same `infra/browser` image** runs on Cloud Run as a single
container with a built-in single-port gateway: **scale-to-zero**, pay only while
a browser is connected, and the free tier covers ~50 browser-hours/month.

```
one Cloud Run instance = one browser = noVNC viewer (/) + CDP (/json/version, /devtools)
```

Deploy — Cloud Build builds, pushes, and deploys in one step:

```bash
gcloud builds submit --config cloudbuild.yaml .
```

Use it with the SDK's **serverless mode** — no control plane, no API key needed
for a public service:

```python
from browsermesh import Client
with Client("https://<your-service>.run.app", serverless=True) as c:
    with c.with_browser() as b:
        print("watch:", b.vnc_url)   # https://<service>/watch  (live view)
        print("drive:", b.cdp_url)   # wss://<service>/devtools/browser/<id>
```

Or run the ready-made agent:

```bash
cd examples
BROWSERMESH_URL=https://<your-service>.run.app uv run python browser_use_serverless.py
```

How it's used here: one Cloud Run service, triggered on demand by a request,
each connection getting its own isolated browser, used for single-shot
automation and paid per second — no cluster, near-zero idle cost.

Notes / limits:

- **Watchable single-use mode.** Deploy with `--max-instances 1 --concurrency 10`
  (the `cloudbuild.yaml` default) so the SDK's CDP connection and your viewer
  share one instance — open `https://<service>/watch` to watch the browser being
  driven. For isolated one-browser-per-connection instead, use
  `--concurrency 1 --max-instances 5` (then you can't watch a specific browser).
- 60-minute max per CDP/VNC WebSocket; cold start ~5–15s; scales to zero when idle.
- Full guide: **[deploy/cloudrun.md](./deploy/cloudrun.md)**. Live instance count:
  `./stats.sh` or `./deploy/instances.sh`.

## Adding a browser engine

A browser is just a Pod that boots a **headed** engine on `DISPLAY=:0` with
KasmVNC and a CDP socket. To add stock Chromium:

1. Build an image like `infra/browser/` that does that (Chromium instead of Cloak).
2. Register its image under `PROVIDERS` in `control/app/config.py`.
3. Done — dashboard, driver, gateway all work unchanged.

## License

[MIT](./LICENSE)
