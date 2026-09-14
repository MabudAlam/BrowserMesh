"""Minimal tests for the BrowserMesh Python SDK (stdlib unittest + httpx MockTransport)."""
import unittest

import httpx

from browsermesh import APIError, Browser, Client, CreateOptions


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "POST" and path == "/browsers":
        return httpx.Response(200, json={"browser_id": "abc", "name": "br-abc", "status": "starting"})
    if request.method == "GET" and path == "/browsers/abc":
        return httpx.Response(200, json={"browser_id": "abc", "name": "br-abc", "status": "Running", "pod_ip": "10.0.0.1"})
    if request.method == "DELETE" and path == "/browsers/abc":
        return httpx.Response(200, json={"browser_id": "abc", "status": "deleted"})
    if request.method == "GET" and path == "/browsers/missing":
        return httpx.Response(404, json={"error": "http_error", "detail": "Browser not found"})
    return httpx.Response(404, json={"error": "not_found", "detail": path})


class TestClient(unittest.TestCase):
    def setUp(self) -> None:
        transport = httpx.MockTransport(_handler)
        self.client = Client("http://x", "bmsk_test", transport=transport)

    def test_requires_base_url_and_key(self) -> None:
        with self.assertRaises(ValueError):
            Client("", "k")
        with self.assertRaises(ValueError):
            Client("http://x", "")

    def test_create_wait_delete(self) -> None:
        created = self.client.create(CreateOptions(type="cloak", timeout_seconds=60))
        self.assertEqual(created.id, "abc")
        ready = self.client.wait_ready("abc")  # first GET is already Running
        self.assertIsInstance(ready, Browser)
        self.assertEqual(ready.status, "Running")
        self.client.delete("abc")

    def test_cdp_url(self) -> None:
        url = self.client.cdp_url("abc")
        self.assertTrue(url.startswith("ws://x/browsers/abc/cdp?"))
        self.assertIn("api_key=bmsk_test", url)

    def test_api_error(self) -> None:
        with self.assertRaises(APIError) as ctx:
            self.client.get("missing")
        self.assertTrue(ctx.exception.is_not_found)
        self.assertEqual(ctx.exception.detail, "Browser not found")


def _serverless_handler(request: httpx.Request) -> httpx.Response:
    if request.method == "GET" and request.url.path == "/json/version":
        return httpx.Response(
            200,
            json={
                "Browser": "Chrome/146",
                "webSocketDebuggerUrl": "wss://run.example/devtools/browser/abc",
            },
        )
    return httpx.Response(404, json={"error": "not_found", "detail": request.url.path})


class TestServerlessClient(unittest.TestCase):
    def setUp(self) -> None:
        transport = httpx.MockTransport(_serverless_handler)
        self.client = Client("https://run.example", serverless=True, transport=transport)

    def test_no_api_key_needed(self) -> None:
        self.assertEqual(self.client.base_url, "https://run.example")
        self.assertTrue(self.client.serverless)

    def test_cdp_url_resolves_from_version(self) -> None:
        self.assertEqual(self.client.cdp_url(), "wss://run.example/devtools/browser/abc")

    def test_vnc_url_is_watch_page(self) -> None:
        self.assertEqual(self.client.vnc_url(), "https://run.example/watch")

    def test_with_browser_yields_running(self) -> None:
        with self.client.with_browser() as b:
            self.assertEqual(b.status, "Running")
            self.assertEqual(b.cdp_url, "wss://run.example/devtools/browser/abc")
            self.assertEqual(b.vnc_url, "https://run.example/watch")

    def test_control_plane_methods_rejected(self) -> None:
        with self.assertRaises(APIError):
            self.client.create()
        with self.assertRaises(APIError):
            self.client.list()
        with self.assertRaises(APIError):
            self.client.delete("abc")


if __name__ == "__main__":
    unittest.main()
