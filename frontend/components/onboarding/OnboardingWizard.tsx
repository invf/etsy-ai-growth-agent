'use client'

import { useState } from 'react'
import { useSession } from 'next-auth/react'
import { useTranslations } from 'next-intl'
import { CheckCircle2, Plug, Rocket, Sparkles } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useRouter } from '@/i18n/navigation'
import { Button } from '@/components/ui/button'

const TOTAL_STEPS = 3

export default function OnboardingWizard({
  initialStep,
  hasStore,
}: {
  initialStep: number
  hasStore: boolean
}) {
  const t = useTranslations('onboarding')
  const { data: session } = useSession()
  const router = useRouter()
  const [step, setStep] = useState(Math.min(Math.max(initialStep, 0), TOTAL_STEPS - 1))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const token = session?.accessToken

  // Persist progress; ignore failures so the user is never trapped in the wizard.
  async function persist(nextStep: number, completed = false) {
    if (!token) return
    try {
      await api.auth.updateOnboarding(token, nextStep, completed)
    } catch {
      // best-effort — progress is non-critical
    }
  }

  async function goNext() {
    const next = step + 1
    setStep(next)
    await persist(next)
  }

  async function finish() {
    setBusy(true)
    await persist(TOTAL_STEPS, true)
    router.push('/dashboard')
    router.refresh()
  }

  async function connectStore() {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await persist(1)
      const res = await api.stores.connectInitiate(token)
      window.location.href = res.data.oauth_url
    } catch (err) {
      setBusy(false)
      setError(
        err instanceof ApiError && err.code === 'STORE_LIMIT_REACHED'
          ? t('connect.limit')
          : t('connect.error')
      )
    }
  }

  const steps = [
    { icon: Sparkles, title: t('steps.welcome') },
    { icon: Plug, title: t('steps.connect') },
    { icon: Rocket, title: t('steps.analyze') },
  ]

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      {/* Progress bar */}
      <div className="mb-10">
        <div className="flex items-center justify-between">
          {steps.map((s, i) => {
            const Icon = i < step ? CheckCircle2 : s.icon
            const active = i <= step
            return (
              <div key={i} className="flex flex-1 flex-col items-center">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full border-2 ${
                    active
                      ? 'border-indigo-600 bg-indigo-600 text-white'
                      : 'border-zinc-300 bg-white text-zinc-400'
                  }`}
                >
                  <Icon className="h-5 w-5" aria-hidden />
                </div>
                <span
                  className={`mt-2 text-center text-xs ${
                    active ? 'font-medium text-indigo-700' : 'text-zinc-400'
                  }`}
                >
                  {s.title}
                </span>
              </div>
            )
          })}
        </div>
        <div className="mt-4 h-1.5 w-full rounded-full bg-zinc-100">
          <div
            className="h-1.5 rounded-full bg-indigo-600 transition-all"
            style={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%` }}
          />
        </div>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
        {step === 0 && (
          <>
            <h1 className="text-2xl font-semibold text-zinc-900">{t('welcome.title')}</h1>
            <p className="mx-auto mt-3 max-w-md text-zinc-500">{t('welcome.body')}</p>
            <Button className="mt-8" onClick={goNext} disabled={busy}>
              {t('welcome.cta')}
            </Button>
          </>
        )}

        {step === 1 && (
          <>
            <h1 className="text-2xl font-semibold text-zinc-900">{t('connect.title')}</h1>
            <p className="mx-auto mt-3 max-w-md text-zinc-500">{t('connect.body')}</p>
            {hasStore ? (
              <div className="mx-auto mt-6 flex max-w-sm items-center justify-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
                <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden />
                {t('connect.done')}
              </div>
            ) : null}
            <div className="mt-8 flex flex-col items-center gap-3">
              {!hasStore && (
                <Button onClick={connectStore} disabled={busy || !token}>
                  <Plug className="h-4 w-4" aria-hidden />
                  {busy ? t('connect.redirecting') : t('connect.cta')}
                </Button>
              )}
              <Button variant="ghost" onClick={goNext} disabled={busy}>
                {hasStore ? t('common.continue') : t('connect.skip')}
              </Button>
            </div>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          </>
        )}

        {step === 2 && (
          <>
            <h1 className="text-2xl font-semibold text-zinc-900">{t('analyze.title')}</h1>
            <p className="mx-auto mt-3 max-w-md text-zinc-500">{t('analyze.body')}</p>
            <div className="mt-8 flex flex-col items-center gap-3">
              <Button
                onClick={() => {
                  setBusy(true)
                  void persist(TOTAL_STEPS, true)
                  router.push('/dashboard/stores')
                }}
                disabled={busy}
              >
                <Rocket className="h-4 w-4" aria-hidden />
                {t('analyze.cta')}
              </Button>
              <Button variant="ghost" onClick={finish} disabled={busy}>
                {t('analyze.finish')}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
