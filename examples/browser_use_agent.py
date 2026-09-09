# BrowserMesh + Browser-Use demo
#
# Runs an AI browser agent against a browser provisioned by BrowserMesh.
#
# Flow:
#   1. Ask BrowserMesh for a new browser (declares a "Browser" -> operator -> Pod)
#   2. Wait until it is Running and a CDP websocket is available
#   3. Point a browser-use Agent at that browser via its CDP endpoint
#   4. Clean the browser up (delete the "Browser", the Pod is removed automatically)
#
# Requires:
#   * BrowserMesh running locally (control plane on http://127.0.0.1:30080)
#   * OPENAI_API_KEY in your environment (used by ChatOpenAI)
#   * `pip install browser-use openai requests` (adjust to your browser-use build)

import asyncio
import os
import time

import requests

from browser_use import BrowserSession, Agent
from browser_use.llm import ChatOpenAI

# Control plane of BrowserMesh (dashboard proxies to this).
API_URL = os.environ.get("BROWSERMESH_API_URL", "http://127.0.0.1:30080")
# Which engine to launch ("cloak" today).
BROWSER_TYPE = os.environ.get("BROWSER_TYPE", "cloak")
# Model used by the agent. ChatOpenAI reads OPENAI_API_KEY automatically.
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")

SLEEP = float(os.environ.get("BROWSERMESH_POLL", "2"))


def _create_browser() -> str:
    """Ask BrowserMesh for a browser; returns its short browser_id."""
    resp = requests.post(
        f"{API_URL}/browsers",
        json={"type": BROWSER_TYPE},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["browser_id"]


def _wait_until_ready(browser_id: str, timeout: int = 120) -> str:
    """Poll the Browser until it reports Running; return the CDP ws url."""
    start = time.time()
    while time.time() - start < timeout:
        details = requests.get(f"{API_URL}/browsers/{browser_id}", timeout=30).json()
        if details.get("status") == "Running":
            cdp_path = details.get("cdp_url")  # e.g. "/browsers/<id>/cdp"
            if cdp_path:
                if cdp_path.startswith("ws"):
                    return cdp_path
                # BrowserMesh exposes ws on the same host as the API.
                return f"ws://{API_URL.split('//')[1]}{cdp_path}"
        time.sleep(SLEEP)
    raise RuntimeError(f"Browser {browser_id} did not become ready in {timeout}s")


def _delete_browser(browser_id: str) -> None:
    """Tell BrowserMesh to stop the browser (the Pod is garbage-collected)."""
    try:
        requests.delete(f"{API_URL}/browsers/{browser_id}", timeout=10)
    except Exception as e:  # noqa: BLE001 - cleanup should never raise
        print(f"[cleanup] delete failed: {e}")


async def main() -> None:
    browser_id = None
    session = None
    try:
        browser_id = _create_browser()
        print(f"Browser declared: {browser_id}")

        cdp_url = _wait_until_ready(browser_id)
        print(f"Browser ready at {cdp_url}")

        session = BrowserSession(cdp_url=cdp_url)

        agent = Agent(
            task="Find all the projects of Mabud Alam"
            "Find his resume as well"
            "Go to his portfolio at Mabud.dev",
            llm=ChatOpenAI(model=MODEL),
            browser_session=session,
            use_vision=False,
            save_conversation_path="logs/ai_news",
            extend_system_message=(
               "You are an AI agent that can use a browser to find information. "
               "You should be able to navigate the web and extract relevant information."
            ),
        )

        print("Starting agent with the remote browser session...")
        history = await agent.run()
        print("\nAgent result:\n", history.final_result())

    except Exception as e:  # noqa: BLE001 - surface any failure clearly
        print(f"\nError: {e}")
    finally:
        if session is not None:
            try:
                await session.close()
            except Exception:  # noqa: BLE001
                pass
        if browser_id is not None:
            _delete_browser(browser_id)


if __name__ == "__main__":
    asyncio.run(main())
