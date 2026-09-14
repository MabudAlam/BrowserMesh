# One browser per Pod. Combined image: headed CloakBrowser + KasmVNC in a single
# container. Reuses the CloakBrowser runtime (engine + Xvnc) as the base so we
# don't re-download the engine or KasmVNC; this layer only adds the boot entry.
FROM cloakhq/cloakbrowser-manager

# nginx fronts KasmVNC + CDP on one port for single-port hosts (Cloud Run).
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

COPY infra/browser/boot.py /boot.py
COPY infra/browser/gateway.conf /etc/nginx/nginx.conf
COPY infra/browser/watch.html /usr/share/browsermesh/watch.html

# Fail the build if the gateway config is invalid.
RUN mkdir -p /tmp/nginx-client-body /tmp/nginx-proxy /tmp/nginx-fastcgi \
        /tmp/nginx-uwsgi /tmp/nginx-scgi \
    && nginx -t -c /etc/nginx/nginx.conf

ENV SCREEN_W=1920 \
    SCREEN_H=1080 \
    KASM_WS_PORT=6080 \
    CDP_PORT=9222

# VNC websocket + CDP (via in-pod forwarder). Referenced by the control gateway.
# 8080 is the single-port gateway, used only when BROWSER_GATEWAY is enabled.
EXPOSE 6080 9223 8080

ENTRYPOINT ["python", "/boot.py"]
