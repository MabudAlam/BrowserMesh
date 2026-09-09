# One browser per Pod. Combined image: headed CloakBrowser + KasmVNC in a single
# container. Reuses the CloakBrowser runtime (engine + Xvnc) as the base so we
# don't re-download the engine or KasmVNC; this layer only adds the boot entry.
FROM cloakhq/cloakbrowser-manager

COPY infra/browser/boot.py /boot.py

ENV SCREEN_W=1920 \
    SCREEN_H=1080 \
    KASM_WS_PORT=6080 \
    CDP_PORT=9222

# VNC websocket + CDP (via in-pod forwarder). Referenced by the control gateway.
EXPOSE 6080 9223

ENTRYPOINT ["python", "/boot.py"]
