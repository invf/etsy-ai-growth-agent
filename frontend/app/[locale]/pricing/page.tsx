import { notFound } from 'next/navigation'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import { api } from '@/lib/api'
import type { SubscriptionPlan } from '@/types'
import PricingTiers from '@/components/billing/PricingTiers'

// Public pricing is hidden during the Etsy API review so the app presents a
// single-shop use case (not a third-party SaaS). The billing infrastructure
// stays intact; only the public entry point is gated. Restore by reverting
// the `hide-pricing-for-etsy-review` branch.
const PRICING_HIDDEN = true

// Mirrors the migration seed — used when the API is unreachable (e.g. at
// build time) so the page always renders
const FALLBACK_PLANS: SubscriptionPlan[] = [
  {
    name: 'starter',
    display_name: 'Starter',
    price_monthly_usd: 19,
    price_annual_usd: 182,
    max_stores: 1,
    credits_monthly: 100,
    credits_rollover_pct: 0,
    listing_analysis_cap: 20,
    features: { audience: false, monthly_plan: false, ab_testing: false },
    paddle_price_id_monthly: null,
    paddle_price_id_annual: null,
  },
  {
    name: 'growth',
    display_name: 'Growth',
    price_monthly_usd: 49,
    price_annual_usd: 470,
    max_stores: 2,
    credits_monthly: 300,
    credits_rollover_pct: 50,
    listing_analysis_cap: 50,
    features: { audience: true, monthly_plan: true, ab_testing: true },
    paddle_price_id_monthly: null,
    paddle_price_id_annual: null,
  },
  {
    name: 'pro',
    display_name: 'Pro',
    price_monthly_usd: 99,
    price_annual_usd: 950,
    max_stores: 5,
    credits_monthly: 750,
    credits_rollover_pct: 50,
    listing_analysis_cap: null,
    features: {
      audience: true,
      monthly_plan: true,
      ab_testing: true,
      api_access: 'read',
    },
    paddle_price_id_monthly: null,
    paddle_price_id_annual: null,
  },
]

const PAID_TIERS = new Set(['starter', 'growth', 'pro'])

export default async function PricingPage({
  params: { locale },
}: {
  params: { locale: string }
}) {
  setRequestLocale(locale)
  if (PRICING_HIDDEN) notFound()
  const t = await getTranslations('pricing')

  let plans = FALLBACK_PLANS
  try {
    const res = await api.billing.plans()
    const paid = res.data.filter((plan) => PAID_TIERS.has(plan.name))
    if (paid.length > 0) plans = paid
  } catch {
    // keep the fallback catalog
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-12">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-zinc-900">{t('title')}</h1>
        <p className="mx-auto mt-2 max-w-xl text-zinc-500">{t('subtitle')}</p>
      </div>
      <div className="mt-10">
        <PricingTiers plans={plans} />
      </div>
      <p className="mt-8 text-center text-xs text-zinc-400">{t('footnote')}</p>
    </main>
  )
}
