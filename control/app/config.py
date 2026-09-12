
import os

# Namespace the operator + browser Pods live in.
NAMESPACE = os.environ.get("BROWSER_NAMESPACE", "browser")

# Ports exposed inside a browser Pod (must match infra/browser/Dockerfile).
CDP_PORT = 9223  # in-pod forwarder -> chrome loopback :9222
VNC_PORT = 6080  # KasmVNC websocket (noVNC)

# The browser-agnostic seam: type -> engine image. Add a new engine here and the
# whole platform (dashboard, driver, gateway) works unchanged.
PROVIDERS = {
    "cloak": os.environ.get("BROWSER_IMAGE_CLOAK", "browser-pod:v1"),
}

# The custom resource the operator reconciles.
CRD_GROUP = "browsermesh.dev"
CRD_VERSION = "v1"
CRD_PLURAL = "browsers"

# Default auto-destroy timeout (seconds) when the caller doesn't specify one.
# Keeps on-demand browsers from leaking if a client dies.
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("BROWSER_DEFAULT_TIMEOUT", str(20 * 60)))

# ---- auth ----
# SQLite file for the single admin user + their API keys (put it on a PVC).
DB_PATH = os.environ.get("BROWSERMESH_DB", "/data/browsermesh.db")
# Signing secret for session cookies and viewer tokens. MUST be set in production.
SESSION_SECRET = os.environ.get("BROWSERMESH_SESSION_SECRET", "dev-insecure-change-me")
# When true, /browsers* require a session cookie or API key.
REQUIRE_AUTH = os.environ.get("BROWSERMESH_REQUIRE_AUTH", "false").lower() in ("1", "true", "yes")
# API key format: bmsk_<prefix>_<secret>
API_KEY_PREFIX = "bmsk"
# How long a browser viewer token (for the noVNC WebSocket) stays valid.
VIEWER_TOKEN_TTL = int(os.environ.get("BROWSERMESH_VIEWER_TTL", "600"))
