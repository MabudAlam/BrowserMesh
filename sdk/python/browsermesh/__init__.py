"""BrowserMesh Python SDK.

    from browsermesh import BrowserMeshClient, BrowserMeshOptions

    client = BrowserMeshClient("http://127.0.0.1:30080", "bmsk_...")
    with client.with_browser(BrowserMeshOptions(type="cloak")) as browser:
        print(client.cdp_url(browser.id))
"""

from .client import BrowserMeshAsyncClient, BrowserMeshClient
from .errors import APIError
from .types import Browser, BrowserMeshOptions

__all__ = [
    "BrowserMeshClient",
    "BrowserMeshAsyncClient",
    "Browser",
    "BrowserMeshOptions",
    "APIError",
]
