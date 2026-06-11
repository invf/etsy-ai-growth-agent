import type { AuthResponse, RegisterData, UserProfile } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/v1'

export class ApiError extends Error {
  code?: string
  status: number

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<{ data: T; meta?: Record<string, number> }> {
  const { token, ...fetchOptions } = options
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((fetchOptions.headers as Record<string, string>) ?? {}),
  }

  const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = body?.detail ?? body?.error ?? {}
    throw new ApiError(detail?.message ?? 'API error', res.status, detail?.code)
  }

  return res.json()
}

export const api = {
  auth: {
    me: (token: string) => apiFetch<UserProfile>('/auth/me', { token }),
    login: (email: string, password: string) =>
      apiFetch<AuthResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    register: (data: RegisterData) =>
      apiFetch<AuthResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
}
