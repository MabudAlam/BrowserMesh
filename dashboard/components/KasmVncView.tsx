"use client"

import { useEffect, useRef, useState } from "react"
import { ClipboardCopy, Loader2, Maximize2, Minimize2, X } from "lucide-react"
import { vncWsUrl, cdpWsUrl } from "@/lib/mgr"

interface KasmVncViewProps {
  profileId: string
  profileName?: string
  onClose?: () => void
}

// Smooth live view of a headed browser Pod via the control-plane VNC gateway.
export function KasmVncView({ profileId, profileName, onClose }: KasmVncViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const rfbRef = useRef<any>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const [copied, setCopied] = useState(false)

  // Connect once per profileId, and auto-reconnect on an unexpected drop. The
  // effect is idempotent (React StrictMode double-invokes it in dev); only the
  // cleanup disconnects, and never a second time on an already-closed RFB.
  useEffect(() => {
    let cancelled = false
    let inFlight = false

    async function attempt() {
      if (cancelled || inFlight) return
      if (rfbRef.current) return // already have a live client
      inFlight = true
      let RFB: any
      try {
        const mod = await import("@novnc/novnc/core/rfb.js")
        RFB = mod.default
      } catch (err: any) {
        inFlight = false
        if (!cancelled) setError(err?.message || "Failed to load viewer")
        schedule()
        return
      }
      inFlight = false
      if (cancelled) return

      const el = containerRef.current
      if (!el) return
      let rfb: any
      try {
        rfb = new RFB(el, vncWsUrl(profileId), { wsProtocols: ["binary"] })
      } catch (err: any) {
        if (!cancelled) setError(err?.message || "Failed to start viewer")
        schedule()
        return
      }
      rfbRef.current = rfb
      rfb.scaleViewport = true
      rfb.resizeSession = false
      rfb.showDotCursor = true

      rfb.addEventListener("connect", () => {
        if (!cancelled) {
          setConnected(true)
          setError(null)
        }
      })
      rfb.addEventListener("disconnect", () => {
        if (cancelled) return
        setConnected(false)
        if (rfbRef.current === rfb) rfbRef.current = null
        schedule()
      })
      rfb.addEventListener("securityfailure", (e: any) => {
        setError(`Security failure: ${e?.detail?.reason || "unknown"}`)
      })
    }

    function schedule() {
      if (cancelled) return
      timerRef.current = setTimeout(attempt, 2000)
    }

    attempt()

    return () => {
      cancelled = true
      if (timerRef.current) clearTimeout(timerRef.current)
      const rfb = rfbRef.current
      rfbRef.current = null
      if (rfb) {
        try {
          rfb.disconnect()
        } catch {
          /* already closed */
        }
      }
    }
  }, [profileId])

  useEffect(() => {
    const h = () => setFullscreen(!!document.fullscreenElement)
    document.addEventListener("fullscreenchange", h)
    return () => document.removeEventListener("fullscreenchange", h)
  }, [])

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      containerRef.current?.closest(".kasm-screen")?.requestFullscreen?.()
    } else {
      document.exitFullscreen()
    }
  }

  async function copyCdp() {
    try {
      await navigator.clipboard.writeText(cdpWsUrl(profileId))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="kasm-screen relative flex flex-col h-full rounded-lg overflow-hidden border border-gray-200 bg-black">
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-900 text-gray-200 z-10">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`h-2 w-2 rounded-full shrink-0 ${connected ? "bg-emerald-400" : "bg-yellow-400 animate-pulse"}`} />
          <span className="text-xs font-medium truncate">{profileName || "Browser"}</span>
          <span className="text-[11px] text-gray-400">{connected ? "Live" : "Connecting…"}</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={copyCdp} className={`p-1 rounded hover:bg-gray-700 ${copied ? "text-emerald-400" : "text-gray-400"}`} title="Copy CDP URL">
            <ClipboardCopy className="h-3.5 w-3.5" />
          </button>
          <button onClick={toggleFullscreen} className="p-1 rounded text-gray-400 hover:bg-gray-700" title="Fullscreen">
            {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
          {onClose && (
            <button onClick={onClose} className="p-1 rounded text-gray-400 hover:bg-gray-700" title="Close">
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
      <div ref={containerRef} className="relative flex-1 w-full" />
      {!connected && !error && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="h-6 w-6 text-gray-400 animate-spin" />
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80 text-red-300 text-sm p-4 text-center">{error}</div>
      )}
    </div>
  )
}
