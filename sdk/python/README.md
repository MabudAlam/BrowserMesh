# browsermesh (Python SDK)

Small, dependency-light Python client for BrowserMesh. Two modes:

- **Control plane** (Kubernetes): create a browser, drive it over CDP, let the
  client clean it up.
- **Serverless** (Cloud Run): drive a single on-demand browser at a service URL.

## Install

```bash
pip install ./sdk/python          # or: uv add --editable ./sdk/python
```

## Usage

Both the base URL and an API key are required (create a key in the dashboard).

```python
from browsermesh import Client, CreateOptions

client = Client("http://127.0.0.1:30080", "bmsk_...")
with client.with_browser(CreateOptions(type="cloak", timeout_seconds=300)) as browser:
    print("drive this browser over CDP at", client.cdp_url(browser.id))
```

Async variant (used by the browser-use example):

```python
from browsermesh import AsyncClient, CreateOptions

async with AsyncClient("http://127.0.0.1:30080", "bmsk_...") as client:
    async with client.with_browser(CreateOptions(type="cloak")) as browser:
        cdp = await client.cdp_url(browser.id)
```

### Serverless mode (Cloud Run)

A Cloud Run browser has no control plane: the service URL *is* one on-demand
browser. Pass `serverless=True`; the API key is optional (only if the service
requires auth). There is nothing to create or delete — `with_browser` just waits
until Chrome answers and yields the endpoint.

```python
from browsermesh import Client

with Client("https://browsermesh-browser-xxxx.run.app", serverless=True) as client:
    with client.with_browser() as browser:
        print("view the live feed at", browser.vnc_url)   # https://.../watch
        print("drive it over CDP at", browser.cdp_url)    # wss://.../devtools/browser/<id>
```

`client.cdp_url()` (no id) resolves the WebSocket URL from the container's
`/json/version`; `client.vnc_url()` returns the self-contained viewer page
(`/watch`, which streams the browser). `create`, `list`, `get`, `delete`, and
`viewer_token` raise `APIError` in serverless mode.

### Low-level methods

```python
b = client.create(CreateOptions(type="cloak"))
client.list()
client.get(b.id)
client.wait_ready(b.id)          # poll until Running
client.delete(b.id)
client.viewer_token(b.id)        # for the noVNC WebSocket
```

Non-2xx responses raise `browsermesh.APIError` (with `.status`, `.kind`,
`.detail`, `.is_not_found`, `.is_unauthorized`).

## Notes

- The API key is sent as `Authorization: Bearer <key>`; `cdp_url()` also embeds
  `?api_key=` so header-less WebSocket clients can authenticate.
- Browsers auto-expire server-side (default 20 min); `with_browser` deletes them
  explicitly as well.
