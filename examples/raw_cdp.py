"""BrowserMesh raw-CDP demo (no browser-use / AI).

Shows the core platform flow with only `requests` + `websockets`:
create a browser, wait until ready, drive it over CDP (navigate + read title),
then delete it. A good sanity check before wiring an AI agent.

Run from anywhere with a running BrowserMesh:
    uv run --no-project python examples/raw_cdp.py
"""
import asyncio
import json
import time

import requests
import websockets

API_URL = "http://127.0.0.1:30080"


def create_browser() -> str:
    resp = requests.post(API_URL + "/browsers", json={"type": "cloak"}, timeout=30)
    resp.raise_for_status()
    return resp.json()["browser_id"]


def wait_ready(browser_id: str, timeout: int = 120) -> str:
    """Poll until Running; return the browser-level CDP websocket url."""
    start = time.time()
    while time.time() - start < timeout:
        b = requests.get(f"{API_URL}/browsers/{browser_id}", timeout=30).json()
        if b.get("status") == "Running" and b.get("cdp_url"):
            host = API_URL.split("//")[1]
            return f"ws://{host}{b['cdp_url']}"
        time.sleep(2)
    raise TimeoutError(f"browser {browser_id} not ready")


async def drive(ws_url: str) -> None:
    async with websockets.connect(ws_url, max_size=None) as ws:
        # Browser-level CDP: list targets and attach to the first page.
        await ws.send(json.dumps({"id": 1, "method": "Target.getTargets"}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                page = next(t for t in msg["result"]["targetInfos"] if t["type"] == "page")
                target_id = page["targetId"]
                break

        await ws.send(json.dumps({"id": 2, "method": "Target.attachToTarget",
                                  "params": {"targetId": target_id, "flatten": True}}))
        session_id = None
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("method") == "Target.attachedToTarget":
                session_id = msg["params"]["sessionId"]
                break

        def cmd(cid, method, params=None):
            return {"id": cid, "sessionId": session_id, "method": method, "params": params or {}}

        await ws.send(json.dumps(cmd(3, "Page.navigate", {"url": "https://example.com"})))

        # Poll document.title until the page has loaded (or give up after ~20s).
        for attempt in range(20):
            await ws.send(json.dumps(cmd(4 + attempt, "Runtime.evaluate",
                                         {"expression": "document.title", "returnByValue": True})))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == 4 + attempt:
                    title = (msg["result"]["result"].get("value") or "").strip()
                    break
            if title:
                print("Page title:", title)
                return
            await asyncio.sleep(1)
        print("Page title: (empty — page did not finish loading)")


async def main() -> None:
    bid = create_browser()
    print("created", bid)
    try:
        ws_url = wait_ready(bid)
        print("cdp", ws_url)
        await drive(ws_url)
    finally:
        requests.delete(f"{API_URL}/browsers/{bid}", timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
