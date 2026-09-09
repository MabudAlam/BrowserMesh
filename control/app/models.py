
from typing import Optional

from pydantic import BaseModel, Field


# ---- request body ---------------------------------------------------------

class CreateBrowserRequest(BaseModel):
    """Payload for declaring a new browser."""

    type: str = Field("cloak", description="Browser engine/provider to run")


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


class BrowserManifest(BaseModel):
    """A full Browser custom resource as sent to the Kubernetes API."""

    apiVersion: str
    kind: str = Field("Browser", description="Always 'Browser'")
    metadata: ObjectMeta
    spec: BrowserSpec
