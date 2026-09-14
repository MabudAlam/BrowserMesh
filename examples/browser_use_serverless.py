# BrowserMesh + Browser-Use demo (serverless / Cloud Run)
#
# Same agent as browser_use_agent.py, but against a single on-demand Cloud Run
# browser instead of the Kubernetes control plane. There is nothing to create or
# delete: the service URL *is* one browser, and Cloud Run scales the instance
# down when the connection ends.
#
# Flow (handled by the SDK's `with_browser`):
#   wait until Chrome's CDP answers -> run the agent over CDP
#
# Requires:
#   * a deployed Cloud Run browser (see deploy/cloudrun.md) — its URL in
#     BROWSERMESH_URL
#   * OPENAI_API_KEY for the LLM
#   * `uv sync` in examples/ (installs browser-use, openai, browsermesh)
#
# Watch the agent live: open BROWSERMESH_URL/watch in a browser.

import asyncio
import os

from browsermesh import AsyncClient
from browser_use import Agent, BrowserSession
from browser_use.llm import ChatOpenAI

# Cloud Run service URL (e.g. https://browsermesh-browser-xxxx.run.app).
URL = os.environ.get("BROWSERMESH_URL", "")
# Optional: a Google identity token, only if the service requires auth
# (--no-allow-unauthenticated). Public services need nothing here.
TOKEN = os.environ.get("BROWSERMESH_TOKEN", "")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")


async def main() -> None:
    if not URL:
        raise SystemExit("Set BROWSERMESH_URL to your Cloud Run service URL.")

    client = AsyncClient(URL, TOKEN or None, serverless=True)
    try:
        async with client.with_browser() as browser:
            # The viewer is built into the container; open it to watch the run.
            print(f"Live feed: {browser.vnc_url}")
            print(f"Driving over CDP: {browser.cdp_url}")

            session = BrowserSession(cdp_url=browser.cdp_url)
            try:
                agent = Agent(
                    task="Visit https://mabud.dev and https://dejan.works and extract the "
                    "portfolio information from each site. For every site collect: name and "
                    "title, about/summary, work experience (roles, companies, dates), projects "
                    "(name, description, link, technologies), skills, education, and "
                    "contact/social links.",
                    llm=ChatOpenAI(model=MODEL),
                    browser_session=session,
                    use_vision=False,
                    save_conversation_path="logs/portfolio_serverless",
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
