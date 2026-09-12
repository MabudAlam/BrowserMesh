
from typing import Optional

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, SQLModel


# ---- request body ---------------------------------------------------------

class CreateBrowserRequest(BaseModel):
    """Payload for declaring a new browser."""

    type: str = Field("cloak", description="Browser engine/provider to run")
    timeout_seconds: int = Field(
        0,
        ge=0,
        description="Auto-destroy after N seconds (0 = use the default, currently 20 min)",
    )


# ---- responses ------------------------------------------------------------

class BrowserCreated(BaseModel):
    """Returned immediately after a Browser is declared (operator creates it async)."""

    browser_id: str = Field(description="Short id; the gateway routes on this")
    name: str = Field(description="Browser/Pod name, e.g. br-abc12345")
    status: str = Field(default="starting")
    type: str = Field(default="cloak")


class BrowserInfo(BaseModel):
    """A single browser and its current, operator-reported status."""

    browser_id: str
    name: str
    status: str
    pod_ip: Optional[str] = None
    cdp_url: Optional[str] = None
    vnc_url: Optional[str] = None
    expires_at: Optional[str] = None


class BrowserList(BaseModel):
    """Collection of all known browsers."""

    browsers: list[BrowserInfo]


class DeleteBrowserResponse(BaseModel):
    """Returned when a Browser has been told to stop."""

    browser_id: str
    status: str


# ---- error response -------------------------------------------------------

class ErrorResponse(BaseModel):
    """Structured error body returned on any failed request."""

    error: str = Field(description="Machine-readable error kind")
    detail: Optional[str] = Field(None, description="Human-readable message")


# ---- Kubernetes custom-resource payload ------------------------------------

class ObjectMeta(BaseModel):
    """The metadata block of a Kubernetes object."""

    name: str
    namespace: str


class BrowserSpec(BaseModel):
    """The spec of a Browser custom resource."""

    type: str = Field("cloak", description="Browser engine/provider to run")
    timeoutSeconds: int = Field(
        0, ge=0, description="Auto-destroy after N seconds (0 = operator default)"
    )


class BrowserManifest(BaseModel):
    """A full Browser custom resource as sent to the Kubernetes API."""

    apiVersion: str
    kind: str = Field("Browser", description="Always 'Browser'")
    metadata: ObjectMeta
    spec: BrowserSpec


# ---- database tables (SQLite) ----------------------------------------------

class User(SQLModel, table=True):
    """The single admin user (email + password)."""

    id: Optional[int] = SQLField(default=None, primary_key=True)
    email: str = SQLField(index=True, unique=True)
    password_hash: str
    created_at: str = SQLField(default="")


class ApiKey(SQLModel, table=True):
    """An API key owned by a user. Hash for auth, encrypted copy to reveal."""

    id: Optional[int] = SQLField(default=None, primary_key=True)
    user_id: int = SQLField(index=True)
    name: str = SQLField(default="default")
    prefix: str = SQLField(default="")
    key_hash: str = SQLField(index=True, unique=True)
    key_enc: Optional[str] = SQLField(default=None)  # encrypted plaintext (viewable)
    created_at: str = SQLField(default="")
    last_used_at: Optional[str] = SQLField(default=None)
    revoked_at: Optional[str] = SQLField(default=None)


# ---- auth request/response models ------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str


class ApiKeyCreate(BaseModel):
    name: str = "default"


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    prefix: str
    key: str = Field(description="Shown once; store it securely")


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    revoked_at: Optional[str] = None


class ViewerTokenResponse(BaseModel):
    token: str
    expires_in: int


class ApiKeyReveal(BaseModel):
    id: int
    key: str
