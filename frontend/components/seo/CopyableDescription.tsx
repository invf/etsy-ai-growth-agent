'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Check, Copy } from 'lucide-react'

export default function CopyableDescription({ text }: { text: string }) {
  const t = useTranslations('listingDetail.analysis.description')
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
    <div className="mt-2">
      <div className="mb-1 flex items-center justify-between">
        <p className="text-xs text-zinc-500">{t('generated')}</p>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
        >
          {copied ? (
            <Check className="h-3 w-3" aria-hidden />
          ) : (
            <Copy className="h-3 w-3" aria-hidden />
          )}
          {copied ? t('copied') : t('copy')}
        </button>
      </div>
      <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-3 font-sans text-sm text-zinc-800">
        {text}
      </pre>
    </div>
  )
}
