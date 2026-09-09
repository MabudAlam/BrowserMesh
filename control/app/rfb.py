
import asyncio
import struct

import websockets
from fastapi import WebSocket, WebSocketDisconnect

# --- RFB client message parsing -------------------------------------------
# Standard client->server message sizes (fixed except SetEncodings=2 and
# ClientCutText=6 which encode their own length).
_RFB_MSG_SIZE = {0: 20, 2: None, 3: 10, 4: 8, 5: 6, 6: None}
# noVNC extension types KasmVNC 1.3.3 does not support; sized so we can skip them.
_RFB_EXT_SIZE = {150: 10, 248: 10, 252: 4, 255: 4}
# Encodings KasmVNC can render; anything else is stripped from SetEncodings.
_ALLOWED_ENCODINGS = {0, 1, 2, 5, 7, 16, -239, -224, *range(-32, -22), *range(-256, -246)}


def _rfb_len(data: bytes, off: int) -> int | None:
    """Length of the RFB message starting at `off`, or None if unrecognized."""
    if off >= len(data):
        return None
    t = data[off]
    fixed = _RFB_MSG_SIZE.get(t)
    if fixed is not None:
        return fixed
    rem = len(data) - off
    if t == 2 and rem >= 4:  # SetEncodings
        return 4 + struct.unpack_from(">H", data, off + 2)[0] * 4
    if t == 6 and rem >= 8:  # ClientCutText
        return 8 + struct.unpack_from(">I", data, off + 4)[0]
    ext = _RFB_EXT_SIZE.get(t)
    return ext  # None => unknown type -> drop rest of frame


def _rewrite_encodings(data: bytes, off: int) -> bytes:
    """Keep only KasmVNC-safe encodings from a SetEncodings message."""
    n = struct.unpack_from(">H", data, off + 2)[0]
    kept = [
        struct.unpack_from(">i", data, off + 4 + i * 4)[0]
        for i in range(n)
        if struct.unpack_from(">i", data, off + 4 + i * 4)[0] in _ALLOWED_ENCODINGS
    ]
    out = struct.pack(">BxH", 2, len(kept))
    for enc in kept:
        out += struct.pack(">i", enc)
    return out


def _rewrite_pointer(data: bytes, off: int) -> bytes:
    """Standard 6-byte PointerEvent -> KasmVNC 11-byte: [5][mask:u16][x][y][sx][sy]."""
    mask = data[off + 1]
    x = struct.unpack_from(">H", data, off + 2)[0]
    y = struct.unpack_from(">H", data, off + 4)[0]
    return struct.pack(">BHHHhh", 5, mask, x, y, 0, 0)


def filter_rfb_client(data: bytes) -> bytes:
    """Parse concatenated client RFB messages; keep only what KasmVNC supports."""
    out = bytearray()
    off = 0
    while off < len(data):
        t = data[off]
        ln = _rfb_len(data, off)
        if ln is None or off + ln > len(data):
            break  # unknown / incomplete -> don't forward (would desync the stream)
        if t in _RFB_MSG_SIZE:
            if t == 2:
                out.extend(_rewrite_encodings(data, off))
            elif t == 5:
                out.extend(_rewrite_pointer(data, off))
            else:
                out.extend(data[off : off + ln])
        off += ln
    return bytes(out)


def filter_rfb_server(frame: bytes) -> bytes:
    """Drop KasmVNC's BinaryClipboard frames noVNC can't parse (type 180)."""
    if len(frame) > 0 and frame[0] == 180:
        return b""
    return frame


async def proxy(ws: WebSocket, target_uri: str, mode: str = "vnc") -> None:
    """Relay a client WebSocket to an upstream browser Pod, adapting RFB if VNC.

    Connects to the upstream server-side (no browser Origin) and pipes bytes
    both ways. For `vnc` the RFB stream is filtered/rewritten; `cdp` is relayed
    verbatim.
    """
    kwargs = {"max_size": None}
    if mode == "vnc":
        # KasmVNC needs its legacy origin header and can't do permessage-deflate
        # or WebSocket pings.
        kwargs["additional_headers"] = {"Origin": f"http://{target_uri}", "Sec-WebSocket-Origin": f"http://{target_uri}"}
        kwargs["subprotocols"] = ["binary"]
        kwargs["compression"] = None
        kwargs["ping_interval"] = None
        kwargs["ping_timeout"] = None

    # A freshly created Pod reports Running before KasmVNC is listening, so retry.
    upstream = None
    for _ in range(20):
        try:
            upstream = await websockets.connect(target_uri, **kwargs)
            break
        except Exception:
            await asyncio.sleep(1)
    if upstream is None:
        await ws.close(code=1011, reason="browser not ready")
        return

    try:
        async def client_to_up():
            handshake = 0  # first client frames are RFB handshake, not message types
            try:
                while True:
                    msg = await ws.receive()
                    if msg.get("type") == "websocket.disconnect":
                        break
                    if msg.get("bytes"):
                        data = msg["bytes"]
                        if mode == "vnc":
                            handshake += 1
                            if handshake > 3:
                                data = filter_rfb_client(data)
                                if not data:
                                    continue  # dropped unsupported/noVNC types
                        await upstream.send(data)
                    elif msg.get("text") and mode != "vnc":
                        await upstream.send(msg["text"])
                    # vnc: noVNC only sends binary frames; drop any text.
            except WebSocketDisconnect:
                pass
            except Exception:
                pass

        async def up_to_client():
            try:
                async for m in upstream:
                    if isinstance(m, bytes):
                        if mode == "vnc":
                            m = filter_rfb_server(m)
                            if not m:
                                continue
                        await ws.send_bytes(m)
                    else:
                        await ws.send_text(m)
            except Exception:
                pass

        await asyncio.gather(client_to_up(), up_to_client())
    finally:
        await upstream.close()
