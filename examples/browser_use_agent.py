# BrowserMesh + Browser-Use demo
#
# Runs an AI browser agent against a browser provisioned by BrowserMesh, using
# the BrowserMesh Python SDK for the browser lifecycle.
#
# Flow (handled by the SDK's `with_browser`):
#   create browser -> wait until Running -> run the agent over CDP -> delete it
#
# Requires:
#   * BrowserMesh running locally (control plane on http://127.0.0.1:30080)
#   * a BrowserMesh API key in BROWSERMESH_API_KEY (create one in the dashboard)
#   * OPENAI_API_KEY for the LLM
#   * `uv sync` in examples/ (installs browser-use, openai, browsermesh)

import asyncio
import os

from browsermesh import AsyncClient, CreateOptions
from browser_use import Agent, BrowserSession
from browser_use.llm import ChatOpenAI

API_URL = os.environ.get("BROWSERMESH_API_URL", "http://127.0.0.1:30080")
API_KEY = os.environ.get("BROWSERMESH_API_KEY", "")
BROWSER_TYPE = os.environ.get("BROWSER_TYPE", "cloak")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
# Auto-destroy safety net (seconds). 0 = server default (20 min).
TIMEOUT_SECONDS = int(os.environ.get("BROWSERMESH_TIMEOUT", "600"))


async def main() -> None:
    if not API_KEY:
        raise SystemExit("Set BROWSERMESH_API_KEY (create a key in the dashboard).")

    client = AsyncClient(API_URL, API_KEY)
    try:
        async with client.with_browser(
            CreateOptions(type=BROWSER_TYPE, timeout_seconds=TIMEOUT_SECONDS)
        ) as browser:
            cdp_url = client.cdp_url(browser.id)  # ws://.../cdp?api_key=...
            print(f"Browser {browser.id} ready; driving over CDP")

            session = BrowserSession(cdp_url=cdp_url)
            try:
                agent = Agent(
                    task="Find the top three AI breakthroughs announced in the last week "
                    "and summarize their security implications",
                    llm=ChatOpenAI(model=MODEL),
                    browser_session=session,
                    use_vision=False,
                    save_conversation_path="logs/ai_news",
                    extend_system_message=(
                        "When summarizing, focus on potential privacy or security risks "
                        "and keep each summary under 150 words"
                    ),
                )
                history = await agent.run()
                print("\nAgent result:\n", history.final_result())
            finally:
                try:
                    await session.close()
                except Exception:  # noqa: BLE001
                    pass
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
