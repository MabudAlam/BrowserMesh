"""Boot a single headed browser Pod: KasmVNC (Xvnc) virtual display + headed
CloakBrowser, exposing a VNC websocket and a CDP port. One browser = one Pod.

Provider image built on the CloakBrowser runtime. To add another engine, build a
thin image that boots its own headed browser on DISPLAY=:0 the same way.
"""
import asyncio
import logging
import os
import shutil
import signal
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s boot %(message)s")
log = logging.getLogger("boot")

SCREEN_W = int(os.environ.get("SCREEN_W", "1920"))
SCREEN_H = int(os.environ.get("SCREEN_H", "1080"))
KASM_WS_PORT = int(os.environ.get("KASM_WS_PORT", "6080"))
CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))   # chrome binds CDP on loopback
CDP_EXT = int(os.environ.get("CDP_EXT", "9223"))     # exposed to the control plane
DISPLAY = ":0"
KASM_HTTPD = os.environ.get("KASM_HTTPD", "/usr/share/kasmvnc/www")
USER_DATA = os.environ.get("USER_DATA_DIR", "/tmp/browser-profile")


def start_xvnc() -> subprocess.Popen:
    """Start KasmVNC (Xvnc) owning display :0 with a websocket for noVNC."""
    xvnc = shutil.which("Xvnc") or "/usr/bin/Xvnc"
    cmd = [
        xvnc,
        DISPLAY,
        "-websocketPort", str(KASM_WS_PORT),
        "-rfbport", "-1",  # websocket only
        "-geometry", f"{SCREEN_W}x{SCREEN_H}",
        "-depth", "24",
        "-SecurityTypes", "None",
        "-DisableBasicAuth",
        "-interface", "0.0.0.0",  # reachable from the control gateway on pod net
        "-AlwaysShared",
        "-httpd", KASM_HTTPD,
    ]
    log.info("starting Xvnc: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd)
    return proc


async def _pump(src, dst):
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except Exception:
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass


async def _forward(client_reader, client_writer):
    """Bidirectional TCP proxy: exposes loopback CDP on 0.0.0.0:CDP_EXT so the
    control gateway (a different Pod) can reach Chrome's CDP socket."""
    try:
        up_reader, up_writer = await asyncio.open_connection("127.0.0.1", CDP_PORT)
    except Exception:
        client_writer.close()
        return
    await asyncio.gather(
        _pump(client_reader, up_writer),
        _pump(up_reader, client_writer),
    )


async def start_cdp_forward() -> asyncio.AbstractServer:
    return await asyncio.start_server(_forward, "0.0.0.0", CDP_EXT)


async def launch_browser() -> None:
    from cloakbrowser import launch_persistent_context_async

    args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-debugging-address=0.0.0.0",
    ]
    env = {**os.environ, "DISPLAY": DISPLAY}
    log.info("launching headed CloakBrowser (DISPLAY=%s cdp=%s)", DISPLAY, CDP_PORT)
    await launch_persistent_context_async(
        user_data_dir=USER_DATA,
        headless=False,
        args=args,
        env=env,
        viewport={"width": SCREEN_W, "height": SCREEN_H - 133},
    )
    log.info("browser context up")


async def main() -> None:
    # Exit promptly on termination so k8s deletes complete instead of hanging.
    stop = asyncio.Event()

    def _handle_signal(sig, frame):  # noqa: ARG001
        log.info("termination signal received (%s); exiting", sig)
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    xvnc = start_xvnc()
    try:
        await asyncio.sleep(1.5)
        if xvnc.poll() is not None:
            raise RuntimeError(f"Xvnc exited early (code {xvnc.returncode})")
        await launch_browser()
        server = await start_cdp_forward()
        log.info("CDP forward %s -> 127.0.0.1:%s; keeping pod alive", CDP_EXT, CDP_PORT)
        await stop.wait()
        log.info("shutting down")
        server.close()
        await server.wait_closed()
    finally:
        xvnc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
