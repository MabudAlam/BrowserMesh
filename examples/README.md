# BrowserMesh examples

Small demos showing how to drive a BrowserMesh browser. They all do the same
core thing:

```
create a Browser  →  wait until Running  →  drive it over CDP  →  delete it
```

The two control-plane demos talk to `http://127.0.0.1:30080` (override via the
`BROWSERMESH_API_URL` / `API_URL` at the top of each file). The serverless demo
targets a single Cloud Run browser instead — no create/delete.

This folder is a self-contained **uv project** — set it up once:

```bash
cd examples
uv sync          # creates examples/.venv and installs the locked dependencies
```

Then run any example with `uv run` (from `examples/`):

```bash
# 1. raw_cdp.py — no AI/browser libraries (control plane)
uv run python raw_cdp.py

# 2. browser_use_agent.py — an AI agent driving a control-plane browser
export OPENAI_API_KEY="sk-..."          # read by ChatOpenAI
export BROWSERMESH_API_KEY="bmsk_..."   # create one in the dashboard (/keys)
uv run python browser_use_agent.py

# 3. browser_use_serverless.py — the same agent against a Cloud Run browser
export BROWSERMESH_URL="https://browsermesh-browser-xxxx.run.app"
uv run python browser_use_serverless.py
```

> The browser-use examples use the **BrowserMesh Python SDK** (`browsermesh`),
> added as a path dependency (`../sdk/python`). Control-plane mode requires a
> base URL and an API key; serverless mode needs only the service URL.

## `raw_cdp.py`
Uses only `requests` + `websockets`. Creates a browser, navigates to
example.com, prints the page title, then deletes the browser.

## `browser_use_agent.py`
Runs a **browser-use** agent that drives a control-plane BrowserMesh browser to
visit `mabud.dev` and `dejan.works` and extract their portfolio info (about,
experience, projects, skills, education, links).

Optional env vars:

| Env var | Default | Meaning |
|---|---|---|
| `BROWSERMESH_API_URL` | `http://127.0.0.1:30080` | BrowserMesh control plane |
| `BROWSER_TYPE` | `cloak` | engine to launch |
| `OPENAI_MODEL` | `gpt-4o` | LLM used by the agent |

## `browser_use_serverless.py`
The same portfolio-extraction agent against a **Cloud Run** browser (see
`deploy/cloudrun.md`). The service URL is one on-demand browser, so there is no
create/delete — the SDK waits until Chrome's CDP answers, then the agent drives
it. Cloud Run scales the instance to zero when the connection ends.

| Env var | Default | Meaning |
|---|---|---|
| `BROWSERMESH_URL` | — | Cloud Run service URL (required) |
| `BROWSERMESH_TOKEN` | — | Google identity token, only if the service is private |
| `OPENAI_MODEL` | `gpt-5.6-luna` | LLM used by the agent |

Open `BROWSERMESH_URL/watch` in a browser to watch the run live. This requires
the service to be in **watchable mode** (`--max-instances 1 --concurrency 10`,
the `cloudbuild.yaml` default) so the viewer attaches to the same browser the
agent drives.

## Notes

- Each control-plane run provisions a fresh browser and **deletes it in
  `finally`** — no leaks. The serverless run has nothing to clean up.
- Browsers take a few seconds to become ready; the demos **poll** until Chrome's
  CDP answers before driving.
- The control plane must be reachable (dashboard → `New Browser` → `View`
  proves the same path works).
