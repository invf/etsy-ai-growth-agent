'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useTranslations } from 'next-intl'
import { RefreshCw } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'

export default function SyncStoreButton({
  storeId,
  syncing,
}: {
  storeId: string
  syncing: boolean
}) {
  const t = useTranslations('stores')
  const router = useRouter()
  const { data: session } = useSession()
  const [queued, setQueued] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const busy = syncing || queued

  async function handleSync() {
    if (!session?.accessToken) return
    setError(null)
    try {
      await api.stores.sync(session.accessToken, storeId)
      setQueued(true)
      router.refresh()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'SYNC_IN_PROGRESS') {
        setQueued(true)
      } else {
        setError(t('errors.syncFailed'))
      }
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={handleSync}
        disabled={busy || !session?.accessToken}
      >
        <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} aria-hidden />
        {busy ? t('sync.syncing') : t('sync.button')}
      </Button>
      {error && <span className="text-sm text-red-600">{error}</span>}
    </div>
  )
}
