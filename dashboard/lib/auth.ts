// Auth + API-key client. Talks to the control plane via the same-origin
// `/api` proxy, so the session cookie set on login is sent automatically.

export interface User {
  id: number
  email: string
}

export interface ApiKey {
  id: number
  name: string
  prefix: string
  created_at?: string | null
  last_used_at?: string | null
  revoked_at?: string | null
}

export interface ApiKeyCreated {
  id: number
  name: string
  prefix: string
  key: string
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => "")
    const err = new Error(`${res.status}: ${body.slice(0, 200)}`) as Error & { status?: number }
    err.status = res.status
    throw err
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// Returns the current user, or null if not logged in.
export async function getMe(): Promise<User | null> {
  try {
    return await req<User>("/auth/me")
  } catch (e: any) {
    if (e?.status === 401) return null
    throw e
  }
}

export async function login(email: string, password: string): Promise<User> {
  return req<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) })
}

export async function register(email: string, password: string): Promise<User> {
  return req<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) })
}

export async function logout(): Promise<void> {
  await req("/auth/logout", { method: "POST" })
}

export async function listKeys(): Promise<ApiKey[]> {
  return req<ApiKey[]>("/keys")
}

export async function createKey(name: string): Promise<ApiKeyCreated> {
  return req<ApiKeyCreated>("/keys", { method: "POST", body: JSON.stringify({ name }) })
}

export async function revokeKey(id: number, permanent = false): Promise<void> {
  await req(`/keys/${id}${permanent ? "?permanent=true" : ""}`, { method: "DELETE" })
}

// Reveal the plaintext of an existing key (decrypted server-side).
export async function revealKey(id: number): Promise<string> {
  const r = await req<{ id: number; key: string }>(`/keys/${id}/reveal`)
  return r.key
}

// Short-lived token so the browser can open the noVNC WebSocket (which can't
// send headers). The control plane exposes it on the API.
export async function viewerToken(browserId: string): Promise<string> {
  const r = await req<{ token: string }>(`/browsers/${browserId}/viewer-token`, { method: "POST" })
  return r.token
}
