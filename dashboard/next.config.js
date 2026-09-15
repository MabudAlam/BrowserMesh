/** @type {import('next').NextConfig} */
// Point the dashboard at any BrowserMesh control plane:
//   BROWSERMESH_CONTROL_URL=http://34.30.38.64:30080 npm run dev
// Defaults to the local kind control on :30080.
const CONTROL = process.env.BROWSERMESH_CONTROL_URL || "http://127.0.0.1:30080"

const nextConfig = {
  serverExternalPackages: ["@novnc/novnc"],
  // Proxy the control plane so the dashboard calls it same-origin (no CORS, and
  // the session cookie set on login is sent automatically).
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${CONTROL}/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
