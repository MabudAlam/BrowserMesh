
import asyncio
import uuid

import httpx
from fastapi import HTTPException
from kubernetes import client, config

from .config import CDP_PORT, CRD_GROUP, CRD_PLURAL, CRD_VERSION, NAMESPACE, PROVIDERS
from .models import (
    BrowserCreated,
    BrowserInfo,
    BrowserList,
    BrowserManifest,
    BrowserSpec,
    DeleteBrowserResponse,
    ObjectMeta,
)

__all__ = [
    "create_browser",
    "list_browsers",
    "get_browser",
    "delete_browser",
    "wait_ready_pod_ip",
    "cdp_target",
]


def _api() -> client.CoreV1Api:
    """Build a Kubernetes API client (in-cluster when deployed, else kubeconfig)."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


def _custom() -> client.CustomObjectsApi:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CustomObjectsApi()


def _browser_name(browser_id: str) -> str:
    # Pod name == Browser name == "br-<short-id>", so the gateway can locate the Pod.
    return f"br-{browser_id}"


def create_browser(browser_type: str = "cloak") -> BrowserCreated:
    """Declare a new Browser. The operator reconciles it into a Pod."""
    if browser_type not in PROVIDERS:
        raise HTTPException(400, f"unknown browser type '{browser_type}' (known: {list(PROVIDERS)})")

    browser_id = str(uuid.uuid4())[:8]
    name = _browser_name(browser_id)
    manifest = BrowserManifest(
        apiVersion=f"{CRD_GROUP}/{CRD_VERSION}",
        metadata=ObjectMeta(name=name, namespace=NAMESPACE),
        spec=BrowserSpec(type=browser_type),
    )
    try:
        _custom().create_namespaced_custom_object(
            CRD_GROUP, CRD_VERSION, NAMESPACE, CRD_PLURAL, manifest.model_dump(exclude_none=True)
        )
    except client.exceptions.ApiException as e:
        raise HTTPException(500, f"create browser failed: {e}")
    return BrowserCreated(browser_id=browser_id, name=name, status="starting", type=browser_type)


def list_browsers() -> BrowserList:
    """List Browser custom resources (the declared, reconciled source of truth)."""
    try:
        items = _custom().list_namespaced_custom_object(
            CRD_GROUP, CRD_VERSION, NAMESPACE, CRD_PLURAL
        ).get("items", [])
    except client.exceptions.ApiException as e:
        raise HTTPException(500, f"k8s error: {e}")
    return BrowserList(browsers=[_describe(cr) for cr in items])


def get_browser(browser_id: str) -> BrowserInfo:
    """Read a single Browser custom resource."""
    name = _browser_name(browser_id)
    try:
        cr = _custom().get_namespaced_custom_object(CRD_GROUP, CRD_VERSION, NAMESPACE, CRD_PLURAL, name)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            raise HTTPException(404, "Browser not found")
        raise HTTPException(500, f"k8s error: {e}")
    return _describe(cr)


def _describe(cr: dict) -> BrowserInfo:
    """Flatten a Browser CR into the typed API response."""
    name = cr["metadata"]["name"]
    # Gateway routes on the short id and re-derives the Pod name ("br-<id>").
    browser_id = name.split("-", 1)[1] if name.startswith("br-") else name
    status = cr.get("status") or {}
    return BrowserInfo(
        browser_id=browser_id,
        name=name,
        status=status.get("phase") or "Pending",
        pod_ip=status.get("podIP"),
        cdp_url=f"/browsers/{browser_id}/cdp",
        vnc_url=f"/browsers/{browser_id}/vnc",
    )


def delete_browser(browser_id: str) -> DeleteBrowserResponse:
    """Delete the Browser custom resource (the Pod is garbage-collected by owner ref)."""
    name = _browser_name(browser_id)
    try:
        _custom().delete_namespaced_custom_object(CRD_GROUP, CRD_VERSION, NAMESPACE, CRD_PLURAL, name)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            raise HTTPException(404, "Browser not found")
        raise HTTPException(500, f"k8s error: {e}")
    return DeleteBrowserResponse(browser_id=browser_id, status="deleted")


async def wait_ready_pod_ip(browser_id: str) -> str:
    """Poll until the browser Pod has an IP (Chrome may still be booting)."""
    api = _api()
    name = _browser_name(browser_id)
    for _ in range(60):
        try:
            pod = api.read_namespaced_pod(name, NAMESPACE)
        except client.exceptions.ApiException:
            raise HTTPException(404, "Browser not found")
        if pod.status.pod_ip:
            return pod.status.pod_ip
        if pod.status.phase == "Failed":
            raise HTTPException(500, "Browser pod failed")
        await asyncio.sleep(1)
    raise HTTPException(408, "Timed out waiting for browser")


async def cdp_target(pod_ip: str) -> str:
    """Return the browser-level CDP websocket URL for a Pod (needs its IP)."""
    try:
        async with httpx.AsyncClient() as client:
            version = (await client.get(f"http://{pod_ip}:{CDP_PORT}/json/version", timeout=5)).json()
    except Exception:
        version = {}
    ws_url = version.get("webSocketDebuggerUrl")
    if not ws_url:
        return ""
    return ws_url.replace("localhost", pod_ip)
