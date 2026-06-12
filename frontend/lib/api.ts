import type {
  AgentRunStatus,
  AuthResponse,
  ListingDetail,
  ListingsMeta,
  ListingSummary,
  OAuthInitiate,
  Optimization,
  RegisterData,
  SeoAnalysis,
  Store,
  SubscriptionPlan,
  UserProfile,
} from '@/types'

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/v1'

export class ApiError extends Error {
  code?: string
  status: number

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function apiFetch<T, M = Record<string, number>>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<{ data: T; meta?: M }> {
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
  stores: {
    list: (token: string) => apiFetch<Store[]>('/stores', { token }),
    connectInitiate: (token: string) =>
      apiFetch<OAuthInitiate>('/stores/connect/initiate', {
        method: 'POST',
        token,
      }),
    sync: (token: string, storeId: string) =>
      apiFetch<{ job_id: string; status: string }>(`/stores/${storeId}/sync`, {
        method: 'POST',
        token,
      }),
  },
  listings: {
    list: (
      token: string,
      storeId: string,
      params: { page?: number; per_page?: number; sort?: string; q?: string } = {}
    ) => {
      const search = new URLSearchParams()
      if (params.page) search.set('page', String(params.page))
      if (params.per_page) search.set('per_page', String(params.per_page))
      if (params.sort) search.set('sort', params.sort)
      if (params.q) search.set('q', params.q)
      const qs = search.toString()
      return apiFetch<ListingSummary[], ListingsMeta>(
        `/stores/${storeId}/listings${qs ? `?${qs}` : ''}`,
        { token }
      )
    },
    get: (token: string, storeId: string, listingId: string) =>
      apiFetch<ListingDetail>(`/stores/${storeId}/listings/${listingId}`, {
        token,
      }),
  },
  seo: {
    get: (token: string, listingId: string) =>
      apiFetch<SeoAnalysis>(`/listings/${listingId}/seo`, { token }),
    analyze: (token: string, listingId: string) =>
      apiFetch<{ run_id: string; status: string; credits_reserved: number }>(
        `/listings/${listingId}/seo/analyze`,
        { method: 'POST', token }
      ),
    apply: (token: string, listingId: string, fields?: string[]) =>
      apiFetch<{ optimization_ids: string[]; skipped: string[]; message: string }>(
        `/listings/${listingId}/seo/apply`,
        {
          method: 'POST',
          token,
          ...(fields ? { body: JSON.stringify({ fields }) } : {}),
        }
      ),
  },
  optimizations: {
    list: (token: string, storeId: string, status = 'pending') =>
      apiFetch<Optimization[]>(
        `/stores/${storeId}/optimizations?status=${status}`,
        { token }
      ),
    approve: (token: string, id: string) =>
      apiFetch<Optimization>(`/optimizations/${id}/approve`, {
        method: 'POST',
        token,
      }),
    reject: (token: string, id: string, reason?: string) =>
      apiFetch<Optimization>(`/optimizations/${id}/reject`, {
        method: 'POST',
        token,
        ...(reason ? { body: JSON.stringify({ reason }) } : {}),
      }),
    apply: (token: string, id: string) =>
      apiFetch<{ id: string; status: string }>(`/optimizations/${id}/apply`, {
        method: 'POST',
        token,
      }),
  },
  agent: {
    run: (token: string, runId: string) =>
      apiFetch<AgentRunStatus>(`/agent/runs/${runId}`, { token }),
  },
  billing: {
    plans: () => apiFetch<SubscriptionPlan[]>('/billing/plans'),
  },
}
