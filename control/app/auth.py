"""Authentication: session cookie (dashboard) or API key (SDK/drivers).

When REQUIRE_AUTH is off (default for local self-hosting), everything is allowed.
When on, `/browsers*` require a valid session cookie or `Authorization: Bearer`
API key. WebSockets authenticate via an API key (CDP) or a short-lived viewer
token (noVNC can't send headers).
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, WebSocket
from sqlmodel import Session, select

from .config import REQUIRE_AUTH, VIEWER_TOKEN_TTL
from .db import get_session
from .models import ApiKey, User
from .security import hash_api_key, read_session_token, read_viewer_token


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_from_api_key(session: Session, key: str) -> Optional[User]:
    row = session.exec(select(ApiKey).where(ApiKey.key_hash == hash_api_key(key))).first()
    if row is None or row.revoked_at:
        return None
    row.last_used_at = _now()
    session.add(row)
    session.commit()
    return session.get(User, row.user_id)


def _user_from_request(request: Request, session: Session) -> Optional[User]:
    token = request.cookies.get("browsermesh_session")
    if token:
        uid = read_session_token(token)
        if uid is not None:
            user = session.get(User, uid)
            if user:
                return user
    auth = request.headers.get("authorization", "")
    key = auth[7:].strip() if auth.lower().startswith("bearer ") else request.headers.get("x-api-key")
    if key:
        return _user_from_api_key(session, key)
    return None


async def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Require a valid session cookie or API key."""
    user = _user_from_request(request, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def guard(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    """Dependency for /browsers: enforces auth only when REQUIRE_AUTH is on."""
    if not REQUIRE_AUTH:
        return None
    return await current_user(request, session)


# ---- WebSocket auth --------------------------------------------------------

def ws_api_key_ok(websocket: WebSocket, session: Session) -> bool:
    """True if the WS carries a valid API key (header) or auth is disabled."""
    if not REQUIRE_AUTH:
        return True
    auth = websocket.headers.get("authorization", "")
    key = auth[7:].strip() if auth.lower().startswith("bearer ") else websocket.headers.get("x-api-key")
    key = key or websocket.query_params.get("api_key")
    return bool(key) and _user_from_api_key(session, key) is not None


def ws_viewer_ok(browser_id: str, token: Optional[str]) -> bool:
    """True if the token is a valid, unexpired viewer token for this browser."""
    if not REQUIRE_AUTH:
        return True
    if not token:
        return False
    return read_viewer_token(token, max_age=VIEWER_TOKEN_TTL) == browser_id
