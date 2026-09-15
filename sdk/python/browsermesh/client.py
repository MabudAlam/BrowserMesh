"""Sync and async clients for the BrowserMesh control plane.

Create a browser, drive it over CDP, and watch it live. Both the base URL and an
API key are required.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Optional
from urllib.parse import urlparse

import httpx

from .errors import APIError
from .types import Browser, BrowserMeshOptions


def _cdp_url(base_url: str, api_key: str, browser_id: str) -> str:
    """Build the CDP WebSocket URL, carrying the key as ?api_key=."""
    u = urlparse(base_url)
    scheme = "wss" if u.scheme == "https" else "ws"
    return f"{scheme}://{u.netloc}/browsers/{browser_id}/cdp?api_key={api_key}"


def _vnc_url(base_url: str, browser_id: str, token: str) -> str:
    """Build the viewer (noVNC) WebSocket URL, carrying the token as ?token=."""
    u = urlparse(base_url)
    scheme = "wss" if u.scheme == "https" else "ws"
    return f"{scheme}://{u.netloc}/browsers/{browser_id}/vnc?token={token}"


def _require(base_url: str, api_key: str) -> None:
    if not base_url or not base_url.strip():
        raise ValueError("browsermesh: base URL is required")
    if not api_key or not api_key.strip():
        raise ValueError("browsermesh: API key is required")


class _Common:
    """Shared helpers for both clients."""

    base_url: str
    api_key: str

    def _raise(self, res: httpx.Response) -> None:
        if res.status_code >= 300:
            raise APIError.from_response(res.status_code, res.text)


class BrowserMeshClient(_Common):
    """Synchronous client. Both base_url and api_key are required."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        _require(base_url, api_key)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BrowserMeshClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def cdp_url(self, browser_id: str) -> str:
        """WebSocket URL to drive the browser over CDP."""
        return _cdp_url(self.base_url, self.api_key, browser_id)

    def watch_url(self, browser_id: str) -> str:
        """Viewer (noVNC) WebSocket URL, with a fresh short-lived token."""
        return _vnc_url(self.base_url, browser_id, self.viewer_token(browser_id))

    def create(self, opts: Optional[BrowserMeshOptions] = None) -> Browser:
        res = self._http.post("/browsers", json=(opts or BrowserMeshOptions()).to_body())
        self._raise(res)
        return Browser.from_dict(res.json())

    def list(self) -> list[Browser]:
        res = self._http.get("/browsers")
        self._raise(res)
        return [Browser.from_dict(b) for b in res.json().get("browsers", [])]

    def get(self, browser_id: str) -> Browser:
        res = self._http.get(f"/browsers/{browser_id}")
        self._raise(res)
        return Browser.from_dict(res.json())

    def delete(self, browser_id: str) -> None:
        res = self._http.delete(f"/browsers/{browser_id}")
        self._raise(res)

    def viewer_token(self, browser_id: str) -> str:
        res = self._http.post(f"/browsers/{browser_id}/viewer-token")
        self._raise(res)
        return res.json()["token"]

    def wait_ready(self, browser_id: str, timeout: float = 60.0, interval: float = 2.0) -> Browser:
        """Poll until the browser reports Running (or fail on Failed/Expired)."""
        deadline = time.monotonic() + timeout
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
    def with_browser(self, opts: Optional[BrowserMeshOptions] = None) -> Iterator[Browser]:
        """Create -> wait ready -> yield -> always delete."""
        created = self.create(opts)
        try:
            yield self.wait_ready(created.id)
        finally:
            self.delete(created.id)


class BrowserMeshAsyncClient(_Common):
    """Asynchronous client. Both base_url and api_key are required."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        _require(base_url, api_key)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "BrowserMeshAsyncClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    def cdp_url(self, browser_id: str) -> str:
        """WebSocket URL to drive the browser over CDP."""
        return _cdp_url(self.base_url, self.api_key, browser_id)

    async def watch_url(self, browser_id: str) -> str:
        """Viewer (noVNC) WebSocket URL, with a fresh short-lived token."""
        return _vnc_url(self.base_url, browser_id, await self.viewer_token(browser_id))

    async def create(self, opts: Optional[BrowserMeshOptions] = None) -> Browser:
        res = await self._http.post("/browsers", json=(opts or BrowserMeshOptions()).to_body())
        self._raise(res)
        return Browser.from_dict(res.json())

    async def list(self) -> list[Browser]:
        res = await self._http.get("/browsers")
        self._raise(res)
        return [Browser.from_dict(b) for b in res.json().get("browsers", [])]

    async def get(self, browser_id: str) -> Browser:
        res = await self._http.get(f"/browsers/{browser_id}")
        self._raise(res)
        return Browser.from_dict(res.json())

    async def delete(self, browser_id: str) -> None:
        res = await self._http.delete(f"/browsers/{browser_id}")
        self._raise(res)

    async def viewer_token(self, browser_id: str) -> str:
        res = await self._http.post(f"/browsers/{browser_id}/viewer-token")
        self._raise(res)
        return res.json()["token"]

    async def wait_ready(self, browser_id: str, timeout: float = 60.0, interval: float = 2.0) -> Browser:
        import asyncio

        deadline = time.monotonic() + timeout
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
    async def with_browser(self, opts: Optional[BrowserMeshOptions] = None) -> AsyncIterator[Browser]:
        """Create -> wait ready -> yield -> always delete."""
        created = await self.create(opts)
        try:
            yield await self.wait_ready(created.id)
        finally:
            await self.delete(created.id)
