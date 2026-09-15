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
from pathlib import Path

from dotenv import load_dotenv

from browsermesh import BrowserMeshAsyncClient, BrowserMeshOptions
from browser_use import Agent, BrowserSession
from browser_use.llm import ChatOpenAI

# Load the repo-root .env (BROWSERMESH_URL / BROWSERMESH_API_KEY / OPENAI_API_KEY).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = (
    os.environ.get("BROWSERMESH_API_URL")
    or os.environ.get("BROWSERMESH_URL")
    or "http://127.0.0.1:30080"
)
API_KEY = os.environ.get("BROWSERMESH_API_KEY", "")
BROWSER_TYPE = os.environ.get("BROWSER_TYPE", "cloak")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
# Auto-destroy safety net (seconds). 0 = server default (20 min).
TIMEOUT_SECONDS = int(os.environ.get("BROWSERMESH_TIMEOUT", "600"))


async def main() -> None:
    if not API_KEY:
        raise SystemExit("Set BROWSERMESH_API_KEY (create a key in the dashboard).")

    client = BrowserMeshAsyncClient(API_URL, API_KEY)
    try:
        async with client.with_browser(
            BrowserMeshOptions(type=BROWSER_TYPE, timeout_seconds=TIMEOUT_SECONDS)
        ) as browser:
            cdp_url = client.cdp_url(browser.id)  # ws://.../cdp?api_key=...
            print(f"Browser {browser.id} ready; driving over CDP")
            # Watch live: open the dashboard (http://localhost:4003) and click
            # View, or connect a noVNC client to the viewer URL below.
            print(f"Watch live:      {await client.watch_url(browser.id)}")
            print(f"Driving over CDP: {cdp_url}")

            session = BrowserSession(cdp_url=cdp_url)
            try:
                agent = Agent(
                    task="Visit BOTH https://mabud.dev and https://dejan.works — do not finish "
                    "until you have visited both. For each site, open its projects page if there "
                    "is one, and extract: name and title, about/summary, work experience (roles, "
                    "companies, dates), projects (name, description, link, technologies), skills, "
                    "education, and contact/social links (with their actual URLs).",
                    llm=ChatOpenAI(model=MODEL),
                    browser_session=session,
                    use_vision=False,
                    save_conversation_path="logs/portfolio",
                    extend_system_message=(
                        "Return a structured markdown summary per site with headings and "
                        "bullet lists, and cite the source URL for each section. Do not "
                        "invent details that are not on the pages."
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
