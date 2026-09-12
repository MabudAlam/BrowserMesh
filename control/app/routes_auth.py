"""Auth + API-key management endpoints.

Single admin user (email+password) and their API keys, stored in SQLite.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from .auth import current_user
from .db import get_session
from .models import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    ApiKeyReveal,
    LoginRequest,
    RegisterRequest,
    User,
    UserOut,
)
from .security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    make_session_token,
    new_api_key,
    verify_password,
)

COOKIE_NAME = "browsermesh_session"
COOKIE_MAX_AGE = 7 * 24 * 3600

auth_router = APIRouter(prefix="/auth", tags=["auth"])
keys_router = APIRouter(prefix="/keys", tags=["keys"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@auth_router.post("/register", response_model=UserOut)
def register(req: RegisterRequest, session: Session = Depends(get_session)):
    """Create the single admin account. Refused once an account exists."""
    if session.exec(select(User)).first() is not None:
        raise HTTPException(status_code=403, detail="Admin already registered")
    user = User(email=req.email.lower(), password_hash=hash_password(req.password), created_at=_now())
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserOut(id=user.id, email=user.email)


@auth_router.post("/login", response_model=UserOut)
def login(req: LoginRequest, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == req.email.lower())).first()
    if user is None or not verify_password(user.password_hash, req.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    response.set_cookie(
        COOKIE_NAME,
        make_session_token(user.id),
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )
    return UserOut(id=user.id, email=user.email)


@auth_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"status": "ok"}


@auth_router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, email=user.email)


@keys_router.post("", response_model=ApiKeyCreated)
def create_key(body: ApiKeyCreate, user: User = Depends(current_user), session: Session = Depends(get_session)):
    plaintext, prefix, key_hash = new_api_key()
    row = ApiKey(
        user_id=user.id,
        name=body.name,
        prefix=prefix,
        key_hash=key_hash,
        key_enc=encrypt_secret(plaintext),  # keep a viewable (encrypted) copy
        created_at=_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    # The plaintext key is returned exactly once here (and can be revealed later).
    return ApiKeyCreated(id=row.id, name=row.name, prefix=row.prefix, key=plaintext)


@keys_router.get("/{key_id}/reveal", response_model=ApiKeyReveal)
def reveal_key(key_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Return the plaintext of a key (decrypted) so it can be viewed again."""
    row = session.get(ApiKey, key_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Key not found")
    if not row.key_enc:
        raise HTTPException(status_code=409, detail="Key was created before reveal was enabled")
    plaintext = decrypt_secret(row.key_enc)
    if plaintext is None:
        raise HTTPException(status_code=409, detail="Key cannot be decrypted (session secret changed)")
    return ApiKeyReveal(id=row.id, key=plaintext)


@keys_router.get("", response_model=list[ApiKeyOut])
def list_keys(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(ApiKey).where(ApiKey.user_id == user.id)).all()
    return [
        ApiKeyOut(
            id=r.id,
            name=r.name,
            prefix=r.prefix,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
            revoked_at=r.revoked_at,
        )
        for r in rows
    ]


@keys_router.delete("/{key_id}")
def revoke_key(
    key_id: int,
    permanent: bool = False,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Revoke a key (soft). With `?permanent=true`, delete it permanently."""
    row = session.get(ApiKey, key_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Key not found")
    if permanent:
        session.delete(row)
        session.commit()
        return {"id": key_id, "status": "deleted"}
    row.revoked_at = _now()
    session.add(row)
    session.commit()
    return {"id": key_id, "status": "revoked"}
