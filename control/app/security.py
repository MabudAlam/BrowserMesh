"""Password hashing, API-key generation, and signed tokens.

- Passwords: argon2 (slow, salted) via argon2-cffi.
- API keys: high-entropy random; we store only a SHA-256 hash + a display prefix.
- Sessions & viewer tokens: short signed strings via itsdangerous (no session table).
"""
import hashlib
import secrets
import base64

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import API_KEY_PREFIX, SESSION_SECRET

_ph = PasswordHasher()
_session_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="browsermesh-session")
_viewer_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="browsermesh-viewer")


# ---- passwords ------------------------------------------------------------
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


# ---- API keys -------------------------------------------------------------
def new_api_key() -> tuple[str, str, str]:
    """Return (plaintext, prefix, hash). Show plaintext once; store prefix+hash."""
    secret = secrets.token_urlsafe(32)
    prefix = secrets.token_hex(4)
    plaintext = f"{API_KEY_PREFIX}_{prefix}_{secret}"
    return plaintext, prefix, hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


# ---- reversible storage (so the key can be viewed again) ------------------
# The key is encrypted with a key derived from SESSION_SECRET, so the DB file
# alone does not reveal it. NOTE: changing SESSION_SECRET makes old keys
# undecryptable (they'd need to be recreated).
def _fernet() -> Fernet:
    derived = base64.urlsafe_b64encode(hashlib.sha256(SESSION_SECRET.encode()).digest())
    return Fernet(derived)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


# ---- sessions -------------------------------------------------------------
def make_session_token(user_id: int) -> str:
    return _session_serializer.dumps({"uid": user_id})


def read_session_token(token: str, max_age: int = 7 * 24 * 3600) -> int | None:
    try:
        data = _session_serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("uid")


# ---- viewer tokens (for the noVNC WebSocket, which can't send headers) -----
def make_viewer_token(browser_id: str) -> str:
    return _viewer_serializer.dumps({"bid": browser_id})


def read_viewer_token(token: str, max_age: int) -> str | None:
    try:
        data = _viewer_serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("bid")
