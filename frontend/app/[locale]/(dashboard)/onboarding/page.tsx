import { setRequestLocale } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { api } from '@/lib/api'
import type { UserProfile } from '@/types'
import OnboardingWizard from '@/components/onboarding/OnboardingWizard'

export default async function OnboardingPage({
  params: { locale },
}: {
  params: { locale: string }
}) {
  setRequestLocale(locale)
  const session = await auth()
  if (!session?.accessToken) {
    redirect(`/${locale}/login`)
  }

  let user: UserProfile | null = null
  try {
    const res = await api.auth.me(session.accessToken)
    user = res.data
  } catch {
    redirect(`/${locale}/login`)
  }

  // Already onboarded — no reason to be here.
  if (user?.onboarding_completed) {
    redirect(`/${locale}/dashboard`)
  }

  return (
    <main>
      <OnboardingWizard
        initialStep={user?.onboarding_step ?? 0}
        hasStore={(user?.store_count ?? 0) > 0}
      />
    </main>
  )
}
