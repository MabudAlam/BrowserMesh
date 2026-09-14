from dataclasses import dataclass, field


@dataclass
class Browser:
    """A browser and its operator-reported status."""

    id: str = ""  # empty in serverless mode (no control plane)
    name: str = ""
    status: str = ""  # Pending | Running | Failed | Expired
    pod_ip: str = ""
    cdp_url: str = ""  # path, e.g. /browsers/<id>/cdp
    vnc_url: str = ""  # path, e.g. /browsers/<id>/vnc
    expires_at: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Browser":
        return cls(
            id=d.get("browser_id", ""),
            name=d.get("name", ""),
            status=d.get("status", ""),
            pod_ip=d.get("pod_ip") or "",
            cdp_url=d.get("cdp_url") or "",
            vnc_url=d.get("vnc_url") or "",
            expires_at=d.get("expires_at") or "",
        )


@dataclass
class CreateOptions:
    """Options for creating a browser."""

    type: str = "cloak"
    timeout_seconds: int = 0  # 0 = server default (20 min)

    def to_body(self) -> dict:
        body: dict = {"type": self.type}
        if self.timeout_seconds > 0:
            body["timeout_seconds"] = self.timeout_seconds
        return body
