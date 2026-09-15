// Client for the BrowserMesh control plane (pod-per-browser, browser-agnostic).
// REST is proxied same-origin via Next rewrites (/api -> 127.0.0.1:8000).
// VNC/CDP connect directly to the control service gateway ws (no origin gate).

export type BrowserStatus = "Pending" | "Running" | "Succeeded" | "Failed" | string

export interface Browser {
  id: string
  name: string
  status: BrowserStatus
  pod_ip?: string | null
  cdp_path?: string
  vnc_path?: string
}

export interface BrowserList {
  browsers: Browser[]
}

// Control-plane REST is proxied same-origin via the Next rewrite (/api ->
// BROWSERMESH_CONTROL_URL). VNC/CDP connect directly to the control gateway ws
// (Next dev does not reliably proxy WebSockets), so this URL must be set too.
//   NEXT_PUBLIC_BROWSERMESH_CONTROL_WS=ws://34.30.38.64:30080
// (NEXT_PUBLIC_* is inlined at build time; set it before `npm run build`.)
const CONTROL_WS =
  process.env.NEXT_PUBLIC_BROWSERMESH_CONTROL_WS || "ws://127.0.0.1:30080"

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  })
  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new Error(`API ${init?.method || "GET"} ${path} -> ${res.status}: ${body.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

// Normalize control-service responses to {id,name,status,...}.
function norm(b: any): Browser {
  return {
    id: b.browser_id ?? b.name,
    name: b.name ?? b.browser_id ?? b.id,
    status: b.status ?? "Pending",
    pod_ip: b.pod_ip,
    cdp_path: b.cdp_url,
    vnc_path: b.vnc_url,
  }
}

export async function listBrowsers(): Promise<Browser[]> {
  const r = await req<BrowserList>("/browsers")
  return (r.browsers || []).map(norm)
}

export async function createBrowser(type = "cloak", timeoutSeconds?: number): Promise<Browser> {
  const body: Record<string, unknown> = { type }
  if (timeoutSeconds && timeoutSeconds > 0) body.timeout_seconds = timeoutSeconds
  const b = await req<any>("/browsers", { method: "POST", body: JSON.stringify(body) })
  return norm(b)
}

export async function deleteBrowser(id: string): Promise<void> {
  await req(`/browsers/${id}`, { method: "DELETE" })
}

export async function getBrowser(id: string): Promise<Browser> {
  return norm(await req(`/browsers/${id}`))
}

// The viewer connects directly to the control gateway (which echoes the "binary"
// subprotocol noVNC needs). Next dev does NOT reliably proxy WebSockets, so we
// don't route VNC through the /api rewrite.
export function vncWsUrl(id: string): string {
  return `${CONTROL_WS}/browsers/${id}/vnc`
}

// Drivers (QuickCrawl/chromedp) are non-browser and connect to the control plane
// directly.
export function cdpWsUrl(id: string): string {
  return `${CONTROL_WS}/browsers/${id}/cdp`
}

export const isRunning = (b: Browser) => b.status === "Running"
