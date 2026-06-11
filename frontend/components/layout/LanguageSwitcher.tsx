'use client'

import { useTransition } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Globe } from 'lucide-react'
import { usePathname, useRouter } from '@/i18n/navigation'
import { routing, type Locale } from '@/i18n/routing'

export default function LanguageSwitcher() {
  const t = useTranslations('language')
  const locale = useLocale()
  const router = useRouter()
  const pathname = usePathname()
  const [isPending, startTransition] = useTransition()

  function onChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const nextLocale = event.target.value as Locale
    startTransition(() => {
      router.replace(pathname, { locale: nextLocale })
    })
  }

  return (
    <label className="flex items-center gap-1.5 text-sm text-zinc-600">
      <Globe className="h-4 w-4" aria-hidden />
      <span className="sr-only">{t('label')}</span>
      <select
        value={locale}
        onChange={onChange}
        disabled={isPending}
        className="cursor-pointer rounded-md border border-zinc-200 bg-white px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-zinc-950 disabled:opacity-50"
      >
        {routing.locales.map((loc) => (
          <option key={loc} value={loc}>
            {t(loc)}
          </option>
        ))}
      </select>
    </label>
  )
}
