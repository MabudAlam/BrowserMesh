# BrowserMesh examples

Small demos showing how to drive a BrowserMesh browser. They all do the same
core thing:

```
create a Browser  →  wait until Running  →  drive it over CDP  →  delete it
```

Both talk to the control plane at `http://127.0.0.1:30080` (override via the
`BROWSERMESH_API_URL` / `API_URL` at the top of each file).

This folder is a self-contained **uv project** — set it up once:

```bash
cd examples
uv sync          # creates examples/.venv and installs the locked dependencies
```

Then run either example with `uv run` (from `examples/`):

```bash
# 1. raw_cdp.py — no AI/browser libraries
uv run python raw_cdp.py

# 2. browser_use_agent.py — an AI agent driving a BrowserMesh browser
export OPENAI_API_KEY="sk-..."          # read by ChatOpenAI
uv run python browser_use_agent.py
```

## `raw_cdp.py`
Uses only `requests` + `websockets`. Creates a browser, navigates to
example.com, prints the page title, then deletes the browser.

## `browser_use_agent.py`
Runs a **browser-use** agent that drives a BrowserMesh browser to research and
summarize the top AI breakthroughs.

Optional env vars:

| Env var | Default | Meaning |
|---|---|---|
| `BROWSERMESH_API_URL` | `http://127.0.0.1:30080` | BrowserMesh control plane |
| `BROWSER_TYPE` | `cloak` | engine to launch |
| `OPENAI_MODEL` | `gpt-4o` | LLM used by the agent |

## Notes

- Each run provisions a fresh browser and **deletes it in `finally`** — no leaks.
- Browsers take a few seconds to become ready; both demos **poll** status until
  it reports `Running` before driving.
- The control plane must be reachable (dashboard → `New Browser` → `View`
  proves the same path works).
