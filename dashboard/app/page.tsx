"use client"

import { useCallback, useEffect, useState } from "react"
import {
  ClipboardCopy,
  Trash2,
  RefreshCw,
  PanelLeft,
  ArrowLeft,
  Play,
  Loader2,
  Eye,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"
import { KasmVncView } from "@/components/KasmVncView"
import { BrowserLogo } from "@/components/browser-logo"
import { listBrowsers, createBrowser, deleteBrowser, isRunning, cdpWsUrl, type Browser } from "@/lib/mgr"

export default function Dashboard() {
  const [browsers, setBrowsers] = useState<Browser[]>([])
  const [loading, setLoading] = useState(true)
  const [busyDelete, setBusyDelete] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState("")
  const [view, setView] = useState<Browser | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const list = await listBrowsers()
      setBrowsers(list)
      setError(null)
    } catch (e: any) {
      setError(e?.message || "Failed to load browsers")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [refresh])

  async function handleCreate() {
    if (creating) return
    setCreating(true)
    setError(null)
    try {
      const b = await createBrowser("cloak")
      setBrowsers((p) => [b, ...p])
      setView(b)
      setName("")
    } catch (e: any) {
      setError(e?.message || "Failed to create browser")
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(b: Browser) {
    if (busyDelete) return
    setBusyDelete(b.id)
    setError(null)
    try {
      await deleteBrowser(b.id)
      setBrowsers((p) => p.filter((x) => x.id !== b.id))
      if (view?.id === b.id) setView(null)
    } catch (e: any) {
      setError(e?.message || "Failed to delete browser")
    } finally {
      setBusyDelete(null)
    }
  }

  async function copyCdp(b: Browser) {
    try {
      await navigator.clipboard.writeText(cdpWsUrl(b.id))
      setCopied(b.id)
      setTimeout(() => setCopied(null), 2000)
    } catch {
      /* noop */
    }
  }

  const sorted = [...browsers].sort((a, b) => (isRunning(a) ? -1 : 1) - (isRunning(b) ? -1 : 1))
  const running = browsers.filter(isRunning).length

  return (
    <SidebarProvider>
      <AppSidebar running={running} total={browsers.length} onNew={handleCreate} onRefresh={refresh} />
      <SidebarInset className="min-w-0 bg-background">
        <header className="flex items-center gap-3 border-b-2 border-border px-4 py-2.5">
          <SidebarTrigger>
            <PanelLeft className="h-5 w-5" />
          </SidebarTrigger>
          <div className="min-w-0">
            <h1 className="text-base font-bold font-heading">Browsers</h1>
            <p className="text-xs text-muted-foreground">
              {running} running · {browsers.length} total
            </p>
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            <Button variant="neutral" onClick={refresh} disabled={loading} title="Refresh">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              placeholder="Name (optional)"
              className="hidden w-40 md:block md:w-44"
            />
            <Button variant="default" onClick={handleCreate} disabled={creating}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {creating ? "Launching…" : "New Browser"}
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl space-y-5 overflow-x-hidden px-4 py-5 md:px-6">
          {error && <div className="rounded-base border-2 border-red-500 bg-red-950 px-3 py-2 text-sm text-red-200">{error}</div>}

          {loading && browsers.length === 0 ? (
            <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" /> Loading browsers…
            </div>
          ) : browsers.length === 0 ? (
            <Card className="border-2 border-dashed">
              <CardContent className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
                <BrowserLogo className="h-12 w-12 opacity-60" />
                <p>No browsers yet. Click “New Browser” to launch an isolated headed browser.</p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Live viewer for the selected browser */}
              {view && isRunning(view) && (
                <section className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Button variant="neutral" size="sm" onClick={() => setView(null)}>
                      <ArrowLeft className="h-4 w-4" /> Back to list
                    </Button>
                    <div className="flex flex-1 flex-wrap items-center justify-end gap-1.5">
                      {browsers.filter(isRunning).map((b) => (
                        <Button
                          key={b.id}
                          size="sm"
                          variant={view.id === b.id ? "default" : "noShadow"}
                          onClick={() => setView(b)}
                          title={b.name}
                        >
                          {b.name}
                        </Button>
                      ))}
                    </div>
                  </div>
                  <div className="h-[58vh]">
                    <KasmVncView key={view.id} profileId={view.id} profileName={view.name} onClose={() => setView(null)} />
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="neutral" onClick={() => copyCdp(view)}>
                      <ClipboardCopy className="h-4 w-4" /> {copied === view.id ? "Copied!" : "Copy CDP URL"}
                    </Button>
                    <Button variant="reverse" onClick={() => handleDelete(view)} disabled={busyDelete === view.id}>
                      {busyDelete === view.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      Delete
                    </Button>
                  </div>
                </section>
              )}

              {/* Table of browsers */}
              <div className="overflow-x-auto rounded-base border-2 border-border bg-secondary-background">
                <table className="w-full min-w-[560px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b-2 border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-4 py-3 font-bold">Status</th>
                      <th className="px-4 py-3 font-bold">Browser</th>
                      <th className="px-4 py-3 font-bold">Endpoint</th>
                      <th className="px-4 py-3 text-right font-bold">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((b) => {
                      const up = isRunning(b)
                      return (
                        <tr key={b.id} className="border-b border-border last:border-0 hover:bg-background/70">
                          <td className="px-4 py-3">
                            <span className="flex items-center gap-2">
                              <span className={`h-2.5 w-2.5 rounded-full ${up ? "bg-green-400" : "bg-gray-400"}`} />
                              <span className={up ? "font-medium text-foreground" : "text-muted-foreground"}>
                                {up ? "Running" : (b.status || "Stopped").toLowerCase()}
                              </span>
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <p className="font-bold font-heading">{b.name}</p>
                            <p className="font-mono text-[11px] text-muted-foreground">#{b.id}</p>
                          </td>
                          <td className="px-4 py-3">
                            {up ? (
                              <span className="font-mono text-[11px] text-muted-foreground">
                                {b.pod_ip ? `pod ${b.pod_ip}` : "…"}
                              </span>
                            ) : (
                              <span className="text-muted-foreground/60">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-end gap-1.5">
                              {up && (
                                <Button size="sm" variant="default" onClick={() => setView(b)}>
                                  <Eye className="h-4 w-4" /> View
                                </Button>
                              )}
                              {up && (
                                <Button size="sm" variant="neutral" onClick={() => copyCdp(b)} title="Copy CDP URL">
                                  <ClipboardCopy className={`h-4 w-4 ${copied === b.id ? "text-green-400" : ""}`} />
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="reverse"
                                onClick={() => handleDelete(b)}
                                disabled={busyDelete === b.id}
                                title="Delete"
                              >
                                {busyDelete === b.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
