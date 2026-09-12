
from fastapi import APIRouter, Depends, WebSocket
from sqlmodel import Session

from . import controller, rfb
from .auth import guard, ws_api_key_ok, ws_viewer_ok
from .config import VIEWER_TOKEN_TTL, VNC_PORT
from .db import get_session
from .models import (
    BrowserCreated,
    BrowserInfo,
    BrowserList,
    CreateBrowserRequest,
    DeleteBrowserResponse,
    ViewerTokenResponse,
)
from .security import make_viewer_token

router = APIRouter()


@router.post("/browsers", response_model=BrowserCreated, dependencies=[Depends(guard)])
async def create_browser(payload: CreateBrowserRequest):
    """Declare a new browser. The operator turns it into a Pod asynchronously."""
    return controller.create_browser(payload.type, payload.timeout_seconds)


@router.get("/browsers", response_model=BrowserList, dependencies=[Depends(guard)])
async def list_browsers():
    return controller.list_browsers()


@router.get("/browsers/{browser_id}", response_model=BrowserInfo, dependencies=[Depends(guard)])
async def get_browser(browser_id: str):
    return controller.get_browser(browser_id)


@router.delete("/browsers/{browser_id}", response_model=DeleteBrowserResponse, dependencies=[Depends(guard)])
async def delete_browser(browser_id: str):
    return controller.delete_browser(browser_id)


@router.post(
    "/browsers/{browser_id}/viewer-token",
    response_model=ViewerTokenResponse,
    dependencies=[Depends(guard)],
)
async def viewer_token(browser_id: str):
    """Mint a short-lived token so the browser can open the noVNC WebSocket."""
    return ViewerTokenResponse(token=make_viewer_token(browser_id), expires_in=VIEWER_TOKEN_TTL)


@router.websocket("/browsers/{browser_id}/vnc")
async def vnc_proxy(websocket: WebSocket, browser_id: str):
    # Browsers can't set WS headers, so noVNC passes a short-lived viewer token.
    if not ws_viewer_ok(browser_id, websocket.query_params.get("token")):
        await websocket.close(code=1008, reason="unauthorized")
        return
    # noVNC requests the "binary" subprotocol and aborts unless the server echoes it.
    await websocket.accept(subprotocol="binary")
    ip = await controller.wait_ready_pod_ip(browser_id)
    await rfb.proxy(websocket, f"ws://{ip}:{VNC_PORT}/websockify", mode="vnc")


@router.websocket("/browsers/{browser_id}/cdp")
async def cdp_proxy(websocket: WebSocket, browser_id: str, session: Session = Depends(get_session)):
    # Drivers can set headers, so the CDP channel uses the API key.
    if not ws_api_key_ok(websocket, session):
        await websocket.close(code=1008, reason="unauthorized")
        return
    await websocket.accept()
    ip = await controller.wait_ready_pod_ip(browser_id)
    target = await controller.cdp_target(ip)
    if not target:
        await websocket.close(code=1011, reason="CDP not ready")
        return
    await rfb.proxy(websocket, target, mode="cdp")
