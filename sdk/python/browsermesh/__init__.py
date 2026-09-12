"""BrowserMesh Python SDK.

    from browsermesh import Client

    client = Client("http://127.0.0.1:30080", "bmsk_...")
    with client.with_browser(CreateOptions(type="cloak")) as browser:
        print(client.cdp_url(browser.id))
"""

from .client import AsyncClient, Client
from .errors import APIError
from .types import Browser, CreateOptions

__all__ = ["Client", "AsyncClient", "Browser", "CreateOptions", "APIError"]
