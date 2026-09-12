"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, LogIn, UserPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { BrowserLogo } from "@/components/browser-logo"
import { getMe, login, register } from "@/lib/auth"

export default function LoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(true)

  // Already logged in? Skip the login screen.
  useEffect(() => {
    getMe()
      .then((u) => {
        if (u) router.replace("/")
        else setChecking(false)
      })
      .catch(() => setChecking(false))
  }, [router])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === "register") {
        await register(email, password)
      }
      await login(email, password)
      router.replace("/")
    } catch (e: any) {
      setError(e?.message || "Authentication failed")
    } finally {
      setBusy(false)
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm border-2 border-border shadow-shadow">
        <CardHeader className="items-center text-center">
          <span className="mb-2 flex h-12 w-12 items-center justify-center rounded-base border-2 border-border bg-main text-main-foreground shadow-shadow">
            <BrowserLogo className="h-7 w-7" />
          </span>
          <CardTitle className="font-heading">BrowserMesh</CardTitle>
          <CardDescription>
            {mode === "login" ? "Sign in to your control plane" : "Create the admin account"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <Input
              type="email"
              required
              autoComplete="username"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              placeholder={mode === "register" ? "Password (min 8 chars)" : "Password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && (
              <div className="rounded-base border-2 border-red-500 bg-red-950 px-3 py-2 text-xs text-red-200">
                {error}
              </div>
            )}
            <Button type="submit" variant="default" className="w-full shadow-shadow" disabled={busy}>
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : mode === "login" ? (
                <LogIn className="h-4 w-4" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              {mode === "login" ? "Sign in" : "Create admin & sign in"}
            </Button>
          </form>

          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login")
              setError(null)
            }}
            className="mt-4 w-full text-center text-xs text-muted-foreground hover:text-foreground"
          >
            {mode === "login" ? "First run? Create the admin account" : "Already have an account? Sign in"}
          </button>
        </CardContent>
      </Card>
    </div>
  )
}
