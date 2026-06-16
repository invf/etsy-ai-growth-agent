'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useTranslations } from 'next-intl'
import { Sparkles } from 'lucide-react'
import { api, API_BASE, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'

type RunState =
  | { phase: 'idle' }
  | { phase: 'running'; progress: number }
  | { phase: 'error'; message: string }

export default function AnalyzeButton({
  listingId,
  hasAnalysis,
}: {
  listingId: string
  hasAnalysis: boolean
}) {
  const t = useTranslations('listingDetail.analyze')
  const router = useRouter()
  const { data: session } = useSession()
  const [state, setState] = useState<RunState>({ phase: 'idle' })
  const sourceRef = useRef<EventSource | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      sourceRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  function finish(error?: string) {
    sourceRef.current?.close()
    sourceRef.current = null
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = null
    if (error) {
      setState({ phase: 'error', message: error })
    } else {
      setState({ phase: 'idle' })
      router.refresh()
    }
  }

  function pollRun(token: string, runId: string) {
    // Fallback when the SSE connection drops: poll the run status
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.agent.run(token, runId)
        if (data.status === 'completed') finish()
        else if (data.status === 'failed' || data.status === 'cancelled') {
          finish(data.error_message ?? t('failed'))
        } else {
          setState({ phase: 'running', progress: data.progress_pct })
        }
      } catch {
        finish(t('failed'))
      }
    }, 2000)
  }

  function listen(token: string, runId: string) {
    const source = new EventSource(
      `${API_BASE}/agent/runs/${runId}/stream?token=${encodeURIComponent(token)}`
    )
    sourceRef.current = source
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data)
      if (payload.type === 'progress') {
        setState({ phase: 'running', progress: payload.progress ?? 0 })
      } else if (payload.type === 'completed') {
        finish()
      } else if (payload.type === 'failed' || payload.type === 'timeout') {
        finish(payload.error ?? t('failed'))
      }
    }
    source.onerror = () => {
      source.close()
      sourceRef.current = null
      if (!pollRef.current) pollRun(token, runId)
    }
  }

  async function start() {
    const token = session?.accessToken
    if (!token) return
    setState({ phase: 'running', progress: 0 })
    try {
      const { data } = await api.seo.analyze(token, listingId)
      listen(token, data.run_id)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'INSUFFICIENT_CREDITS') {
        setState({ phase: 'error', message: t('noCredits') })
      } else if (err instanceof ApiError && err.code === 'DAILY_LIMIT_EXCEEDED') {
        setState({ phase: 'error', message: t('dailyLimit') })
      } else if (err instanceof ApiError && err.code === 'ANALYSIS_IN_PROGRESS') {
        setState({ phase: 'error', message: t('alreadyRunning') })
      } else {
        setState({ phase: 'error', message: t('failed') })
      }
    }
  }

  const running = state.phase === 'running'

  return (
    <div className="flex flex-col items-end gap-1">
      <Button onClick={start} disabled={running || !session?.accessToken}>
        <Sparkles className="h-4 w-4" aria-hidden />
        {running
          ? t('running', { progress: state.phase === 'running' ? state.progress : 0 })
          : hasAnalysis
            ? t('rerun')
            : t('run')}
      </Button>
      {state.phase === 'error' && (
        <p className="text-sm text-red-600">{state.message}</p>
      )}
    </div>
  )
}
