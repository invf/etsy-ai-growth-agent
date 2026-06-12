'use client'

import { useState } from 'react'
import { useSession } from 'next-auth/react'
import { useTranslations } from 'next-intl'
import { Plug } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'

export default function ConnectStoreButton() {
  const t = useTranslations('stores')
  const { data: session } = useSession()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConnect() {
    if (!session?.accessToken) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.stores.connectInitiate(session.accessToken)
      window.location.href = res.data.oauth_url
    } catch (err) {
      setLoading(false)
      if (err instanceof ApiError && err.code === 'STORE_LIMIT_REACHED') {
        setError(t('errors.storeLimit'))
      } else {
        setError(t('errors.connectFailed'))
      }
    }
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <Button onClick={handleConnect} disabled={loading || !session?.accessToken}>
        <Plug className="h-4 w-4" aria-hidden />
        {loading ? t('connect.redirecting') : t('connect.button')}
      </Button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
