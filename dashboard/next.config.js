/** @type {import('next').NextConfig} */
const nextConfig = {
  serverExternalPackages: ["@novnc/novnc"],
  // Proxy the BrowserMesh control plane (pod-per-browser) so the browser at
  // :4003 calls it same-origin. Control is exposed on a stable host port
  // (:30080 via kind extraPortMappings -> NodePort) — no kubectl port-forward.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:30080/:path*",
      },
    ]
  },
}

module.exports = nextConfig
