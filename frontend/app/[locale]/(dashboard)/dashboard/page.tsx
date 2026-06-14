import { getLocale, getTranslations, setRequestLocale } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { Zap } from 'lucide-react'
import { auth } from '@/lib/auth'
import { api } from '@/lib/api'
import type { UserProfile } from '@/types'
import { Link } from '@/i18n/navigation'
import { buttonVariants } from '@/components/ui/button'

export default async function DashboardPage({
  params: { locale },
}: {
  params: { locale: string }
}) {
  setRequestLocale(locale)
  const session = await auth()

  if (!session?.accessToken) {
    redirect(`/${locale}/login`)
  }

  const t = await getTranslations('dashboard')

  let user: UserProfile | null = null
  try {
    const res = await api.auth.me(session.accessToken)
    user = res.data
  } catch {
    // Backend token expired or invalid — force re-login
    redirect(`/${locale}/login`)
  }

  // New users go through the onboarding wizard first.
  if (user && !user.onboarding_completed) {
    redirect(`/${locale}/onboarding`)
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-zinc-900">
        {t('welcome', { name: user?.name ?? session.user?.email ?? '' })}
      </h1>
      <p className="mt-1 text-sm text-zinc-500">{t('subtitle')}</p>

      {/* Plan / credits / trial stats hidden during the Etsy API review so the
          dashboard doesn't present a paid-subscription model. Restore alongside
          the billing UI when SaaS framing returns. */}

      <div className="mt-10 flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white py-16 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100">
          <Zap className="h-8 w-8 text-indigo-600" aria-hidden />
        </div>
        <h2 className="mt-4 text-xl font-semibold text-zinc-900">
          {t('connectStore.title')}
        </h2>
        <p className="mt-1 max-w-sm text-zinc-500">{t('connectStore.description')}</p>
        <Link href="/dashboard/stores" className={buttonVariants({ className: 'mt-4' })}>
          {t('connectStore.button')}
        </Link>
      </div>
    </main>
  )
}
