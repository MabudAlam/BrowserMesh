# kopf (Kubernetes Operator Framework) controller for BrowserMesh.
#
# Job: reconcile each `Browser` custom resource to reality.
#   - a Browser declares "I want a headed browser running" (spec.type)
#   - this controller turns that into a Pod running the matching engine image
#   - it keeps the Pod alive (recreates if it dies) and mirrors state into .status
#   - because the Pod carries an ownerReference to the Browser, deleting the
#     Browser automatically garbage-collects the Pod (no manual cleanup needed)

import logging

import kopf
import kubernetes

# Kinds / labels used across the operator.
CRD_GROUP = "browsermesh.dev"
CRD_VERSION = "v1"
CRD_PLURAL = "browsers"

# Each engine maps to a Pod image. This is the browser-agnostic seam: add an
# engine by adding its image here (and booting it headed on :0 with CDP).
ENGINE_IMAGES = {
    "cloak": "browser-pod:v1",
}

# Exposed ports inside the browser Pod (must match infra/browser/Dockerfile).
CDP_PORT = 9223  # in-pod forwarder -> chrome loopback :9222
VNC_PORT = 6080  # KasmVNC websocket

# Per-browser isolation budget.
MEMORY_LIMIT = "2Gi"
MEMORY_REQUEST = "1Gi"

logger = logging.getLogger("browsermesh.operator")


def _api() -> kubernetes.client.CoreV1Api:
    """Lazily build an in-cluster k8s API client (cached by kubernetes module)."""
    try:
        kubernetes.config.load_incluster_config()
    except kubernetes.config.ConfigException:
        # Allow running the operator locally against a kind kubeconfig for dev.
        kubernetes.config.load_kube_config()
    return kubernetes.client.CoreV1Api()


def _pod_spec(name: str, namespace: str, engine: str, browser_uid: str) -> dict:
    """Build the Pod manifest for a Browser (mirrors infra/browser boot contract)."""
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,  # pod name == browser name, so the gateway can find it by id
            "namespace": namespace,
            "labels": {"app": "browsermesh", "browser": "true"},
            # Tie the Pod's lifecycle to the Browser: deleting the Browser
            # garbage-collects this Pod automatically.
            "ownerReferences": [
                {
                    "apiVersion": f"{CRD_GROUP}/{CRD_VERSION}",
                    "kind": "Browser",
                    "name": name,
                    "uid": browser_uid,
                }
            ],
        },
        "spec": {
            "containers": [
                {
                    "name": "browser",
                    "image": ENGINE_IMAGES.get(engine, ENGINE_IMAGES["cloak"]),
                    "imagePullPolicy": "IfNotPresent",
                    "ports": [
                        {"containerPort": CDP_PORT, "name": "cdp"},
                        {"containerPort": VNC_PORT, "name": "vnc"},
                    ],
                    "resources": {
                        "requests": {"memory": MEMORY_REQUEST},
                        "limits": {"memory": MEMORY_LIMIT},
                    },
                }
            ],
            # Let each browser OOM/exit without dragging the Pod through restarts,
            # and finish deletes quickly.
            "restartPolicy": "Never",
            "terminationGracePeriodSeconds": 5,
        },
    }


def _ensure_pod(name: str, namespace: str, body: dict) -> str:
    """Create the Pod if it is missing; return its current phase."""
    api = _api()
    try:
        pod = api.read_namespaced_pod(name, namespace)
        return pod.status.phase
    except kubernetes.client.rest.ApiException as e:
        if e.status != 404:
            raise
    api.create_namespaced_pod(namespace, body)
    return "Pending"


def _set_status(namespace: str, name: str, patch: dict) -> None:
    """Merge status fields onto the Browser object."""
    custom = kubernetes.client.CustomObjectsApi()
    try:
        custom.patch_namespaced_custom_object_status(
            CRD_GROUP, CRD_VERSION, namespace, CRD_PLURAL, name, {"status": patch}
        )
    except kubernetes.client.rest.ApiException as e:
        logger.warning("status update failed for %s: %s", name, e)


@kopf.timer(CRD_GROUP, CRD_VERSION, CRD_PLURAL, interval=3.0)
def reconcile(body, spec, meta, namespace, **kwargs):
    """Periodic convergence loop (the core of the operator).

    Runs every few seconds and brings reality in line with the Browser's goal.
    """
    name = meta["name"]
    engine = (spec or {}).get("type", "cloak")
    uid = meta.get("uid", "")

    pod_body = _pod_spec(name, namespace, engine, uid)
    phase = _ensure_pod(name, namespace, pod_body)

    # Look up the Pod's IP + endpoint urls so the gateway can reach it.
    pod_ip = None
    try:
        pod = _api().read_namespaced_pod(name, namespace)
        pod_ip = pod.status.pod_ip
    except kubernetes.client.rest.ApiException:
        pod = None

    status = {"phase": phase, "type": engine}
    if pod is not None and pod_ip:
        status["phase"] = "Running"
        status["podIP"] = pod_ip
        status["cdpUrl"] = f"/browsers/{name}/cdp"
        status["vncUrl"] = f"/browsers/{name}/vnc"
    elif pod is not None and pod.status.phase == "Failed":
        status["phase"] = "Failed"

    _set_status(namespace, name, status)
    # Return None: status is written explicitly via _set_status. Returning a dict
    # would make kopf nest it under status.reconcile, which we don't want.
    return None
