"""Minimal tests for the BrowserMesh Python SDK (stdlib unittest + httpx MockTransport)."""
import unittest

import httpx

from browsermesh import APIError, Browser, BrowserMeshClient, BrowserMeshOptions


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "POST" and path == "/browsers":
        return httpx.Response(200, json={"browser_id": "abc", "name": "br-abc", "status": "starting"})
    if request.method == "GET" and path == "/browsers/abc":
        return httpx.Response(200, json={"browser_id": "abc", "name": "br-abc", "status": "Running", "pod_ip": "10.0.0.1"})
    if request.method == "DELETE" and path == "/browsers/abc":
        return httpx.Response(200, json={"browser_id": "abc", "status": "deleted"})
    if request.method == "POST" and path == "/browsers/abc/viewer-token":
        return httpx.Response(200, json={"token": "vtok"})
    if request.method == "GET" and path == "/browsers/missing":
        return httpx.Response(404, json={"error": "http_error", "detail": "Browser not found"})
    return httpx.Response(404, json={"error": "not_found", "detail": path})


class TestBrowserMeshClient(unittest.TestCase):
    def setUp(self) -> None:
        transport = httpx.MockTransport(_handler)
        self.client = BrowserMeshClient("http://x", "bmsk_test", transport=transport)

    def test_requires_base_url_and_key(self) -> None:
        with self.assertRaises(ValueError):
            BrowserMeshClient("", "k")
        with self.assertRaises(ValueError):
            BrowserMeshClient("http://x", "")

    def test_create_wait_delete(self) -> None:
        created = self.client.create(BrowserMeshOptions(type="cloak", timeout_seconds=60))
        self.assertEqual(created.id, "abc")
        ready = self.client.wait_ready("abc")  # first GET is already Running
        self.assertIsInstance(ready, Browser)
        self.assertEqual(ready.status, "Running")
        self.client.delete("abc")

    def test_cdp_url(self) -> None:
        url = self.client.cdp_url("abc")
        self.assertTrue(url.startswith("ws://x/browsers/abc/cdp?"))
        self.assertIn("api_key=bmsk_test", url)

    def test_watch_url(self) -> None:
        url = self.client.watch_url("abc")
        self.assertTrue(url.startswith("ws://x/browsers/abc/vnc?"))
        self.assertIn("token=vtok", url)

    def test_api_error(self) -> None:
        with self.assertRaises(APIError) as ctx:
            self.client.get("missing")
        self.assertTrue(ctx.exception.is_not_found)
        self.assertEqual(ctx.exception.detail, "Browser not found")


if __name__ == "__main__":
    unittest.main()
