"use client"

import { useCallback, useEffect, useState } from "react"
import { KeyRound, Loader2, PanelLeft, Plus, Trash2, Copy, Check, Eye, EyeOff, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { createKey, listKeys, revealKey, revokeKey, type ApiKey } from "@/lib/auth"

// Human-friendly "time ago" for last-used timestamps.
function timeAgo(iso?: string | null): string {
  if (!iso) return "never"
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return "never"
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState("")
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<number | null>(null)
  // id -> plaintext, once revealed
  const [revealed, setRevealed] = useState<Record<number, string>>({})

  const refresh = useCallback(async () => {
    try {
      setKeys(await listKeys())
      setError(null)
    } catch (e: any) {
      setError(e?.message || "Failed to load keys")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    // Poll so "last used" reflects keys used elsewhere (SDK/drivers).
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [refresh])

  async function handleCreate() {
    if (creating) return
    setCreating(true)
    setError(null)
    try {
      const created = await createKey(name.trim() || "default")
      setRevealed((r) => ({ ...r, [created.id]: created.key })) // newly created is revealed
      setName("")
      await refresh()
    } catch (e: any) {
      setError(e?.message || "Failed to create key")
    } finally {
      setCreating(false)
    }
  }

  async function toggleReveal(k: ApiKey) {
    if (revealed[k.id]) {
      setRevealed((r) => {
        const next = { ...r }
        delete next[k.id]
        return next
      })
      return
    }
    setBusy(k.id)
    setError(null)
    try {
      const plaintext = await revealKey(k.id)
      setRevealed((r) => ({ ...r, [k.id]: plaintext }))
    } catch (e: any) {
      setError(e?.message || "Failed to reveal key")
    } finally {
      setBusy(null)
    }
  }

  async function copyValue(id: number, value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(id)
      setTimeout(() => setCopied(null), 2000)
    } catch {
      /* noop */
    }
  }

  async function handleRevoke(k: ApiKey) {
    setBusy(k.id)
    try {
      await revokeKey(k.id)
      setRevealed((r) => {
        const next = { ...r }
        delete next[k.id]
        return next
      })
      await refresh()
    } catch (e: any) {
      setError(e?.message || "Failed to revoke key")
    } finally {
      setBusy(null)
    }
  }

  // Permanently remove an already-revoked key.
  async function handleDelete(k: ApiKey) {
    setBusy(k.id)
    try {
      await revokeKey(k.id, true)
      setKeys((p) => p.filter((x) => x.id !== k.id))
    } catch (e: any) {
      setError(e?.message || "Failed to delete key")
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b-2 border-border px-4 py-2.5">
        <SidebarTrigger>
          <PanelLeft className="h-5 w-5" />
        </SidebarTrigger>
        <div className="min-w-0">
          <h1 className="text-base font-bold font-heading">API Keys</h1>
          <p className="text-xs text-muted-foreground">Use these with the SDK / drivers</p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <Button variant="neutral" onClick={refresh} disabled={loading} title="Refresh">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder="Key name (optional)"
            className="hidden w-48 md:block"
          />
          <Button variant="default" onClick={handleCreate} disabled={creating}>
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Create key
          </Button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl space-y-5 overflow-x-hidden px-4 py-5 md:px-6">
        {error && <div className="rounded-base border-2 border-red-500 bg-red-950 px-3 py-2 text-sm text-red-200">{error}</div>}

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading keys…
          </div>
        ) : keys.length === 0 ? (
          <Card className="border-2 border-dashed">
            <CardContent className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
              <KeyRound className="h-12 w-12 opacity-60" />
              <p>No API keys yet. Create one for your SDK or scraper.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {keys.map((k) => {
              const revoked = !!k.revoked_at
              const value = revealed[k.id]
              const shown = value ?? `bmsk_${k.prefix}••••••••••••••••`
              return (
                <Card key={k.id} className={`border-2 ${revoked ? "border-border opacity-70" : "border-border"}`}>
                  <CardContent className="space-y-3 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${revoked ? "bg-gray-400" : "bg-green-400"}`} />
                        <span className="truncate font-bold font-heading">{k.name}</span>
                        {revoked && (
                          <span className="rounded-base border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                            revoked
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {!revoked ? (
                          <>
                            <Button size="sm" variant="neutral" onClick={() => toggleReveal(k)} disabled={busy === k.id} title={value ? "Hide" : "Reveal"}>
                              {busy === k.id ? <Loader2 className="h-4 w-4 animate-spin" /> : value ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                            <Button size="sm" variant="neutral" onClick={() => copyValue(k.id, value ?? shown)} title="Copy">
                              {copied === k.id ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
                            </Button>
                            <Button size="sm" variant="reverse" onClick={() => handleRevoke(k)} disabled={busy === k.id} title="Revoke">
                              {busy === k.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                            </Button>
                          </>
                        ) : (
                          <Button size="sm" variant="reverse" onClick={() => handleDelete(k)} disabled={busy === k.id} title="Delete permanently">
                            {busy === k.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                            Delete
                          </Button>
                        )}
                      </div>
                    </div>

                    <code className="block truncate rounded-base border-2 border-border bg-secondary-background px-3 py-2 font-mono text-xs">
                      {shown}
                    </code>

                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                      <span>created {k.created_at ? new Date(k.created_at).toLocaleString() : "—"}</span>
                      <span title={k.last_used_at ?? undefined}>last used {timeAgo(k.last_used_at)}</span>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </main>
    </>
  )
}
