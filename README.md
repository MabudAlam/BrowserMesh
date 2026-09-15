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
| `sdk/` | Go + Python clients for the control plane |
| `examples/` | Runnable demos (`raw_cdp.py`, browser-use agent) |
| `deploy/` | Deployment guides (GKE, k3s) |
| `commands.md` | Setup + change-cycle commands |
| `architecture.md` | Plain-English design notes |

## Quick start (local, kind)

See **[commands.md](./commands.md)** for the details.

```bash
# one command: clean cluster -> build -> load -> deploy -> smoke test
./start.sh

# daily: dashboard
cd dashboard && npm install && npm run dev     # http://localhost:4003
```

`./stop.sh` tears the cluster down.

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
  from browsermesh import BrowserMeshClient, BrowserMeshOptions
  client = BrowserMeshClient("http://127.0.0.1:30080", "bmsk_...")
  with client.with_browser(BrowserMeshOptions(type="cloak", timeout_seconds=300)) as b:
      print("drive:", client.cdp_url(b.id))
      print("watch:", client.watch_url(b.id))
  ```

## Deploying

BrowserMesh runs on any Kubernetes (the Pod is the unit). Guides:

- **[deploy/gke.md](./deploy/gke.md)** — GKE **zonal Standard** with the free-tier
  control plane + a **spot** browser node pool that scales to zero.
- **[deploy/k3s.md](./deploy/k3s.md)** — the cheapest option: k3s on a single
  small x86 VPS.
- **[deploy/README.md](./deploy/README.md)** — cost levers and host comparison.

## Adding a browser engine

A browser is just a Pod that boots a **headed** engine on `DISPLAY=:0` with
KasmVNC and a CDP socket. To add stock Chromium:

1. Build an image like `infra/browser/` that does that (Chromium instead of Cloak).
2. Register its image under `PROVIDERS` in `control/app/config.py`.
3. Done — dashboard, driver, gateway all work unchanged.

## License

[MIT](./LICENSE)
