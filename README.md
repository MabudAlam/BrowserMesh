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
| `commands.md` | Setup + change-cycle commands |
| `architecture.md` | Plain-English design notes |

## Quick start

See **[commands.md](./commands.md)** — it has the two things you'll run:
**first-time setup** and the **normal change cycle**.

High level:

```bash
# 1. one-time: cluster, CRD, operator, control (see commands.md for detail)
kind create cluster --config infra/kind-config.yaml
kubectl create namespace browser
kubectl apply -f crds/browsers.crd.yaml
kubectl apply -f operator/operator.yaml
kubectl apply -f control/control.yaml

# 2. daily: dashboard
cd dashboard && npm install && npm run dev     # http://localhost:4003
```

## Using it

- **Dashboard:** open `http://localhost:4003` → **New Browser** → **View** to
  watch it live; **Copy CDP URL** to drive it with QuickCrawl / chromedp.
- **API:**
  ```bash
  curl -X POST http://127.0.0.1:30080/browsers -H 'Content-Type: application/json' -d '{"type":"cloak"}'
  curl http://127.0.0.1:30080/browsers
  curl -X DELETE http://127.0.0.1:30080/browsers/<id>
  ```

## Adding a browser engine

A browser is just a Pod that boots a **headed** engine on `DISPLAY=:0` with
KasmVNC and a CDP socket. To add stock Chromium:

1. Build an image like `infra/browser/` that does that (Chromium instead of Cloak).
2. Register its image under `PROVIDERS` in `control/app/config.py`.
3. Done — dashboard, driver, gateway all work unchanged.

## License

[MIT](./LICENSE)
