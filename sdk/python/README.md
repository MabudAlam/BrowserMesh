# browsermesh (Python SDK)

Small, dependency-light Python client for the [BrowserMesh](../../) control
plane. Create a browser, drive it over CDP, and let the client clean it up.

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
        cdp = client.cdp_url(browser.id)
```

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
