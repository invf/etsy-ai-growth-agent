'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Check, Copy } from 'lucide-react'

export default function CopyableAltText({ text }: { text: string }) {
  const t = useTranslations('listingDetail.analysis.images')
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable (e.g. insecure context) — selection is still possible
    }
  }

  return (
    <div className="flex items-start justify-between gap-2">
      <p className="flex-1 text-sm font-medium text-zinc-900">{text}</p>
      <button
        type="button"
        onClick={copy}
        className="inline-flex shrink-0 items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
      >
        {copied ? (
          <Check className="h-3 w-3" aria-hidden />
        ) : (
          <Copy className="h-3 w-3" aria-hidden />
        )}
        {copied ? t('copied') : t('copy')}
      </button>
    </div>
  )
}
