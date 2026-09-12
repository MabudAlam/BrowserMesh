"""Errors raised by the BrowserMesh SDK."""


class APIError(Exception):
    """A non-2xx response from the control plane."""

    def __init__(self, status: int, kind: str = "", detail: str = ""):
        self.status = status
        self.kind = kind
        self.detail = detail
        super().__init__(f"browsermesh: {status} {kind}: {detail}")

    @property
    def is_not_found(self) -> bool:
        return self.status == 404

    @property
    def is_unauthorized(self) -> bool:
        return self.status == 401

    @classmethod
    def from_response(cls, status: int, body: str) -> "APIError":
        import json

        kind, detail = "", body[:200]
        try:
            data = json.loads(body)
            kind = data.get("error", "")
            detail = data.get("detail", detail)
        except (ValueError, AttributeError):
            pass
        return cls(status, kind, detail)
