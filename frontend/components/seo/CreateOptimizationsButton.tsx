'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useTranslations } from 'next-intl'
import { ListPlus } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

export default function CreateOptimizationsButton({ listingId }: { listingId: string }) {
  const t = useTranslations('listingDetail.createOptimizations')
  const router = useRouter()
  const { data: session } = useSession()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create() {
    const token = session?.accessToken
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await api.seo.apply(token, listingId, ['title', 'tags', 'description'])
      router.refresh()
    } catch {
      setError(t('failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <Button variant="outline" onClick={create} disabled={busy || !session?.accessToken}>
        <ListPlus className="h-4 w-4" aria-hidden />
        {busy ? t('creating') : t('button')}
      </Button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
