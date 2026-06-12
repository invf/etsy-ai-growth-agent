'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useTranslations } from 'next-intl'
import { ArrowRight, Check, Upload, X } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { Optimization } from '@/types'

const STATUS_STYLES: Record<Optimization['status'], string> = {
  pending: 'bg-amber-100 text-amber-700',
  approved: 'bg-blue-100 text-blue-700',
  rejected: 'bg-zinc-100 text-zinc-500',
  applying: 'bg-blue-100 text-blue-700',
  applied: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

function Value({ value }: { value: string | string[] | null }) {
  if (value === null) return <span className="text-zinc-400">—</span>
  if (Array.isArray(value)) {
    return (
      <span className="flex flex-wrap gap-1">
        {value.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700"
          >
            {tag}
          </span>
        ))}
      </span>
    )
  }
  return <span>{value}</span>
}

export default function OptimizationCard({ optimization }: { optimization: Optimization }) {
  const t = useTranslations('optimizations')
  const router = useRouter()
  const { data: session } = useSession()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function act(action: 'approve' | 'reject' | 'apply') {
    const token = session?.accessToken
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      if (action === 'approve') await api.optimizations.approve(token, optimization.id)
      if (action === 'reject') await api.optimizations.reject(token, optimization.id)
      if (action === 'apply') await api.optimizations.apply(token, optimization.id)
      router.refresh()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'ETSY_UPDATE_FAILED') {
        setError(t('errors.etsyRejected'))
      } else if (err instanceof ApiError && err.code === 'ETSY_UNAVAILABLE') {
        setError(t('errors.etsyUnavailable'))
      } else if (err instanceof ApiError && err.code === 'STORE_NOT_CONNECTED') {
        setError(t('errors.storeDisconnected'))
      } else {
        setError(t('errors.generic'))
      }
      router.refresh()
    } finally {
      setBusy(false)
    }
  }

  const { status } = optimization

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold capitalize text-zinc-900">
          {t(`types.${optimization.type}`)}
        </span>
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-xs font-medium',
            STATUS_STYLES[status]
          )}
        >
          {t(`status.${status}`)}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-1 items-start gap-2 text-sm md:grid-cols-[1fr_auto_1fr]">
        <div className="text-zinc-500 line-through decoration-zinc-300">
          <Value value={optimization.old_value} />
        </div>
        <ArrowRight className="hidden h-4 w-4 shrink-0 self-center text-zinc-400 md:block" aria-hidden />
        <div className="font-medium text-zinc-900">
          <Value value={optimization.new_value} />
        </div>
      </div>

      {optimization.change_summary && (
        <p className="mt-2 text-xs text-zinc-500">{optimization.change_summary}</p>
      )}
      {status === 'rejected' && optimization.rejection_reason && (
        <p className="mt-2 text-xs text-zinc-500">
          {t('rejectedReason', { reason: optimization.rejection_reason })}
        </p>
      )}

      {(status === 'pending' || status === 'approved') && (
        <div className="mt-3 flex items-center gap-2">
          {status === 'pending' && (
            <>
              <Button size="sm" onClick={() => act('approve')} disabled={busy}>
                <Check className="h-4 w-4" aria-hidden />
                {t('actions.approve')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => act('reject')}
                disabled={busy}
              >
                <X className="h-4 w-4" aria-hidden />
                {t('actions.reject')}
              </Button>
            </>
          )}
          {status === 'approved' && (
            <Button size="sm" onClick={() => act('apply')} disabled={busy}>
              <Upload className="h-4 w-4" aria-hidden />
              {busy ? t('actions.applying') : t('actions.apply')}
            </Button>
          )}
        </div>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}
