
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
