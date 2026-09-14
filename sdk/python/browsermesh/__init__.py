"""BrowserMesh Python SDK.

Control plane (Kubernetes):

    from browsermesh import Client

    client = Client("http://127.0.0.1:30080", "bmsk_...")
    with client.with_browser(CreateOptions(type="cloak")) as browser:
        print(client.cdp_url(browser.id))

Serverless (Cloud Run) — pass serverless=True; no API key needed:

    client = Client("https://browsermesh-browser-xxxx.run.app", serverless=True)
    with client.with_browser() as browser:
        print(browser.vnc_url)   # watch here
        print(browser.cdp_url)   # drive here
"""

from .client import AsyncClient, Client
from .errors import APIError
from .types import Browser, CreateOptions

__all__ = ["Client", "AsyncClient", "Browser", "CreateOptions", "APIError"]
