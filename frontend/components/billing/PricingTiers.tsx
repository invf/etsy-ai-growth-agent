'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useLocale, useTranslations } from 'next-intl'
import { Check } from 'lucide-react'
import { useRouter } from '@/i18n/navigation'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { SubscriptionPlan } from '@/types'

declare global {
  interface Window {
    Paddle?: {
      Environment: { set: (env: 'sandbox' | 'production') => void }
      Setup: (options: {
        token: string
        eventCallback?: (event: { name: string }) => void
      }) => void
      Checkout: { open: (options: Record<string, unknown>) => void }
    }
  }
}

const PADDLE_TOKEN = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN
const PADDLE_ENV =
  process.env.NEXT_PUBLIC_PADDLE_ENV === 'production' ? 'production' : 'sandbox'

function usePaddle() {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!PADDLE_TOKEN) return
    if (window.Paddle) {
      setReady(true)
      return
    }
    const script = document.createElement('script')
    script.src = 'https://cdn.paddle.com/paddle/v2/paddle.js'
    script.onload = () => {
      if (!window.Paddle) return
      if (PADDLE_ENV === 'sandbox') window.Paddle.Environment.set('sandbox')
      window.Paddle.Setup({
        token: PADDLE_TOKEN,
        eventCallback: (event) => {
          if (event.name === 'checkout.completed') {
            // The Paddle webhook updates the DB; just send the user back
            window.location.href = '/dashboard?upgraded=true'
          }
        },
      })
      setReady(true)
    }
    document.head.appendChild(script)
  }, [])

  return ready
}

const FEATURE_FLAGS = ['audience', 'monthly_plan', 'ab_testing', 'api_access', 'white_label']

function PlanCard({
  plan,
  isAnnual,
  paddleReady,
  popular,
}: {
  plan: SubscriptionPlan
  isAnnual: boolean
  paddleReady: boolean
  popular: boolean
}) {
  const t = useTranslations('pricing')
  const locale = useLocale()
  const router = useRouter()
  const { data: session } = useSession()

  const price = isAnnual ? plan.price_annual_usd / 12 : plan.price_monthly_usd
  const priceId = isAnnual
    ? plan.paddle_price_id_annual
    : plan.paddle_price_id_monthly
  const checkoutConfigured = Boolean(priceId && PADDLE_TOKEN)

  function subscribe() {
    if (!session) {
      router.push('/register')
      return
    }
    if (!window.Paddle || !priceId) return
    window.Paddle.Checkout.open({
      items: [{ priceId, quantity: 1 }],
      customer: { email: session.user?.email ?? undefined },
      customData: {
        user_id: session.userId,
        tier: plan.name,
        billing_period: isAnnual ? 'annual' : 'monthly',
      },
      settings: { displayMode: 'overlay', theme: 'light', locale },
    })
  }

  const bullets = [
    t('bullets.credits', { count: plan.credits_monthly }),
    t('bullets.stores', { count: plan.max_stores }),
    plan.listing_analysis_cap === null
      ? t('bullets.unlimitedAnalyses')
      : t('bullets.analysisCap', { count: plan.listing_analysis_cap }),
    ...(plan.credits_rollover_pct > 0
      ? [t('bullets.rollover', { pct: plan.credits_rollover_pct })]
      : []),
    ...FEATURE_FLAGS.filter((flag) => Boolean(plan.features[flag])).map((flag) =>
      t(`features.${flag}`)
    ),
  ]

  return (
    <div
      className={cn(
        'relative flex flex-col rounded-2xl border bg-white p-6',
        popular ? 'border-indigo-600 shadow-lg' : 'border-zinc-200'
      )}
    >
      {popular && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-3 py-0.5 text-xs font-semibold text-white">
          {t('popular')}
        </span>
      )}
      <h3 className="text-lg font-semibold text-zinc-900">{plan.display_name}</h3>
      <p className="mt-3">
        <span className="text-4xl font-bold tabular-nums">
          ${price.toFixed(price % 1 === 0 ? 0 : 2)}
        </span>
        <span className="text-sm text-zinc-500"> {t('perMonth')}</span>
      </p>
      {isAnnual && (
        <p className="text-xs text-zinc-500">
          {t('billedAnnually', { total: plan.price_annual_usd })}
        </p>
      )}
      <ul className="mt-5 flex-1 space-y-2 text-sm text-zinc-700">
        {bullets.map((bullet) => (
          <li key={bullet} className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-600" aria-hidden />
            {bullet}
          </li>
        ))}
      </ul>
      <Button
        className="mt-6"
        variant={popular ? 'default' : 'outline'}
        onClick={subscribe}
        disabled={Boolean(session) && (!checkoutConfigured || !paddleReady)}
      >
        {session ? t('subscribe') : t('startTrial')}
      </Button>
      {Boolean(session) && !checkoutConfigured && (
        <p className="mt-2 text-center text-xs text-zinc-400">
          {t('checkoutUnavailable')}
        </p>
      )}
    </div>
  )
}

export default function PricingTiers({ plans }: { plans: SubscriptionPlan[] }) {
  const t = useTranslations('pricing')
  const [isAnnual, setIsAnnual] = useState(false)
  const paddleReady = usePaddle()

  return (
    <div>
      <div className="flex items-center justify-center gap-3">
        <span className={cn('text-sm', !isAnnual && 'font-semibold text-zinc-900')}>
          {t('monthly')}
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={isAnnual}
          aria-label={t('annual')}
          onClick={() => setIsAnnual((v) => !v)}
          className={cn(
            'relative h-6 w-11 rounded-full transition-colors',
            isAnnual ? 'bg-indigo-600' : 'bg-zinc-300'
          )}
        >
          <span
            className={cn(
              'absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all',
              isAnnual ? 'left-[22px]' : 'left-0.5'
            )}
          />
        </button>
        <span className={cn('text-sm', isAnnual && 'font-semibold text-zinc-900')}>
          {t('annual')}{' '}
          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
            {t('annualSave')}
          </span>
        </span>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
        {plans.map((plan) => (
          <PlanCard
            key={plan.name}
            plan={plan}
            isAnnual={isAnnual}
            paddleReady={paddleReady}
            popular={plan.name === 'growth'}
          />
        ))}
      </div>
    </div>
  )
}
