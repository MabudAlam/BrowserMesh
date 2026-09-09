
from fastapi import APIRouter, Depends, WebSocket
from fastapi.security import APIKeyHeader

from . import controller, rfb
from .config import VNC_PORT
from .models import (
    BrowserCreated,
    BrowserInfo,
    BrowserList,
    CreateBrowserRequest,
    DeleteBrowserResponse,
)

router = APIRouter()

API_KEY = None
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Depends(api_key_header)):
    if API_KEY and api_key != API_KEY:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


# ---- browser lifecycle ----------------------------------------------------
@router.post("/browsers", response_model=BrowserCreated)
async def create_browser(payload: CreateBrowserRequest):
    """Declare a new browser. The operator turns it into a Pod asynchronously."""
    return controller.create_browser(payload.type)


@router.get("/browsers", response_model=BrowserList)
async def list_browsers():
    return controller.list_browsers()


@router.get("/browsers/{browser_id}", response_model=BrowserInfo)
async def get_browser(browser_id: str):
    return controller.get_browser(browser_id)


@router.delete("/browsers/{browser_id}", response_model=DeleteBrowserResponse)
async def delete_browser(browser_id: str):
    return controller.delete_browser(browser_id)


# ---- WebSocket gateway -----------------------------------------------------
@router.websocket("/browsers/{browser_id}/vnc")
async def vnc_proxy(websocket: WebSocket, browser_id: str):
    # noVNC requests the "binary" subprotocol and aborts unless the server echoes it.
    await websocket.accept(subprotocol="binary")
    ip = await controller.wait_ready_pod_ip(browser_id)
    await rfb.proxy(websocket, f"ws://{ip}:{VNC_PORT}/websockify", mode="vnc")


@router.websocket("/browsers/{browser_id}/cdp")
async def cdp_proxy(websocket: WebSocket, browser_id: str):
    await websocket.accept()
    ip = await controller.wait_ready_pod_ip(browser_id)
    target = await controller.cdp_target(ip)
    if not target:
        await websocket.close(code=1011, reason="CDP not ready")
        return
    await rfb.proxy(websocket, target, mode="cdp")
