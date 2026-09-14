"""Sync and async clients for BrowserMesh.

Two deployment modes:

- **Control plane** (Kubernetes): create/list/delete browsers, drive them over
  CDP through the control-plane gateway. Requires a base URL and an API key.
- **Serverless** (Cloud Run): the service URL *is* one on-demand browser; there
  is no create/delete. Resolve CDP from `/json/version` and view it at `/`.
  `api_key` is optional (send one only if the service requires auth).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Optional
from urllib.parse import urlparse

import httpx

from .errors import APIError
from .types import Browser, CreateOptions


def _cdp_url(base_url: str, api_key: str, browser_id: str) -> str:
    """Build the CDP WebSocket URL, carrying the key as ?api_key=."""
    u = urlparse(base_url)
    scheme = "wss" if u.scheme == "https" else "ws"
    return f"{scheme}://{u.netloc}/browsers/{browser_id}/cdp?api_key={api_key}"


def _require(base_url: str, api_key: str, serverless: bool) -> None:
    if not base_url or not base_url.strip():
        raise ValueError("browsermesh: base URL is required")
    if not serverless and (not api_key or not api_key.strip()):
        raise ValueError("browsermesh: API key is required")


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _ws_from_version(payload: dict) -> str:
    ws = (payload or {}).get("webSocketDebuggerUrl")
    if not ws:
        raise APIError(0, "no_cdp", "browser has no CDP endpoint yet")
    return ws


class _Common:
    """Shared helpers for both clients."""

    base_url: str
    api_key: str
    serverless: bool = False

    def _raise(self, res: httpx.Response) -> None:
        if res.status_code >= 300:
            raise APIError.from_response(res.status_code, res.text)

    def _require_control_plane(self) -> None:
        if self.serverless:
            raise APIError(
                0,
                "unsupported",
                "not available in serverless mode (a Cloud Run browser has no control plane)",
            )

    def vnc_url(self) -> str:
        """Live viewer URL.

        Serverless (Cloud Run): the container serves a self-contained viewer at
        `/watch` that streams the browser (open it to watch). Control-plane:
        mint a viewer token with `viewer_token(id)` and append `?token=` to the
        browser's `vnc_url` (the WebSocket can't send headers).
        """
        if not self.serverless:
            raise ValueError(
                "browsermesh: vnc_url() is serverless-only; in control-plane mode use "
                "viewer_token(id) + the browser's vnc_url"
            )
        return f"{self.base_url}/watch"


class Client(_Common):
    """Synchronous client.

    Control plane: both base_url and api_key are required.
    Serverless:  `Client(url, serverless=True)`; api_key optional.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
        serverless: bool = False,
    ):
        _require(base_url, api_key or "", serverless)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.serverless = serverless
        self._http = httpx.Client(
            base_url=self.base_url,
            headers=_headers(self.api_key),
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def cdp_url(self, browser_id: Optional[str] = None) -> str:
        """WebSocket URL to drive the browser over CDP.

        Serverless: resolved from the container's `/json/version` (the gateway
        rewrites it to `wss://<host>/devtools/browser/<id>`).
        """
        if self.serverless:
            return self._resolve_cdp()
        return _cdp_url(self.base_url, self.api_key, browser_id)

    def _resolve_cdp(self) -> str:
        res = self._http.get("/json/version")
        self._raise(res)
        return _ws_from_version(res.json())

    def create(self, opts: Optional[CreateOptions] = None) -> Browser:
        self._require_control_plane()
        res = self._http.post("/browsers", json=(opts or CreateOptions()).to_body())
        self._raise(res)
        return Browser.from_dict(res.json())

    def list(self) -> list[Browser]:
        self._require_control_plane()
        res = self._http.get("/browsers")
        self._raise(res)
        return [Browser.from_dict(b) for b in res.json().get("browsers", [])]

    def get(self, browser_id: str) -> Browser:
        self._require_control_plane()
        res = self._http.get(f"/browsers/{browser_id}")
        self._raise(res)
        return Browser.from_dict(res.json())

    def delete(self, browser_id: str) -> None:
        self._require_control_plane()
        res = self._http.delete(f"/browsers/{browser_id}")
        self._raise(res)

    def viewer_token(self, browser_id: str) -> str:
        self._require_control_plane()
        res = self._http.post(f"/browsers/{browser_id}/viewer-token")
        self._raise(res)
        return res.json()["token"]

    def wait_ready(
        self, browser_id: Optional[str] = None, timeout: float = 60.0, interval: float = 2.0
    ) -> Browser:
        """Wait until the browser is ready.

        Serverless: poll `/json/version` until Chrome's CDP answers.
        Control plane: poll the Browser resource until it reports Running.
        """
        deadline = time.monotonic() + timeout
        if self.serverless:
            while True:
                try:
                    cdp = self._resolve_cdp()
                    return Browser(status="Running", cdp_url=cdp, vnc_url=self.vnc_url())
                except (APIError, httpx.HTTPError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"browsermesh: browser not ready within {timeout}s")
                    time.sleep(interval)
        while True:
            b = self.get(browser_id)
            if b.status == "Running":
                return b
            if b.status in ("Failed", "Expired"):
                raise APIError(0, "browser_state", f"browser {browser_id} is {b.status}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"browser {browser_id} not ready within {timeout}s")
            time.sleep(interval)

    @contextmanager
    def with_browser(self, opts: Optional[CreateOptions] = None) -> Iterator[Browser]:
        """Yield a ready browser.

        Serverless: yields the endpoint (nothing to create or delete).
        Control plane: create -> wait ready -> yield -> always delete.
        """
        if self.serverless:
            yield self.wait_ready()
            return
        created = self.create(opts)
        try:
            yield self.wait_ready(created.id)
        finally:
            self.delete(created.id)


class AsyncClient(_Common):
    """Asynchronous client.

    Control plane: both base_url and api_key are required.
    Serverless:  `AsyncClient(url, serverless=True)`; api_key optional.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        serverless: bool = False,
    ):
        _require(base_url, api_key or "", serverless)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.serverless = serverless
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers=_headers(self.api_key),
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def cdp_url(self, browser_id: Optional[str] = None) -> str:
        """WebSocket URL to drive the browser over CDP (serverless resolves it)."""
        if self.serverless:
            return await self._resolve_cdp()
        return _cdp_url(self.base_url, self.api_key, browser_id)

    async def _resolve_cdp(self) -> str:
        res = await self._http.get("/json/version")
        self._raise(res)
        return _ws_from_version(res.json())

    async def create(self, opts: Optional[CreateOptions] = None) -> Browser:
        self._require_control_plane()
        res = await self._http.post("/browsers", json=(opts or CreateOptions()).to_body())
        self._raise(res)
        return Browser.from_dict(res.json())

    async def list(self) -> list[Browser]:
        self._require_control_plane()
        res = await self._http.get("/browsers")
        self._raise(res)
        return [Browser.from_dict(b) for b in res.json().get("browsers", [])]

    async def get(self, browser_id: str) -> Browser:
        self._require_control_plane()
        res = await self._http.get(f"/browsers/{browser_id}")
        self._raise(res)
        return Browser.from_dict(res.json())

    async def delete(self, browser_id: str) -> None:
        self._require_control_plane()
        res = await self._http.delete(f"/browsers/{browser_id}")
        self._raise(res)

    async def viewer_token(self, browser_id: str) -> str:
        self._require_control_plane()
        res = await self._http.post(f"/browsers/{browser_id}/viewer-token")
        self._raise(res)
        return res.json()["token"]

    async def wait_ready(
        self, browser_id: Optional[str] = None, timeout: float = 60.0, interval: float = 2.0
    ) -> Browser:
        import asyncio

        deadline = time.monotonic() + timeout
        if self.serverless:
            while True:
                try:
                    cdp = await self._resolve_cdp()
                    return Browser(status="Running", cdp_url=cdp, vnc_url=self.vnc_url())
                except (APIError, httpx.HTTPError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"browsermesh: browser not ready within {timeout}s")
                    await asyncio.sleep(interval)
        while True:
            b = await self.get(browser_id)
            if b.status == "Running":
                return b
            if b.status in ("Failed", "Expired"):
                raise APIError(0, "browser_state", f"browser {browser_id} is {b.status}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"browser {browser_id} not ready within {timeout}s")
            await asyncio.sleep(interval)

    @asynccontextmanager
    async def with_browser(self, opts: Optional[CreateOptions] = None) -> AsyncIterator[Browser]:
        if self.serverless:
            yield await self.wait_ready()
            return
        created = await self.create(opts)
        try:
            yield await self.wait_ready(created.id)
        finally:
            await self.delete(created.id)
