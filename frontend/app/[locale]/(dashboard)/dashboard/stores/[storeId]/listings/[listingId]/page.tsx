import Image from 'next/image'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { ArrowLeft, Eye, Heart, ImageOff, ShoppingBag } from 'lucide-react'
import { auth } from '@/lib/auth'
import { api, ApiError } from '@/lib/api'
import { Link } from '@/i18n/navigation'
import { cn } from '@/lib/utils'
import type { ListingDetail, Optimization, SeoAnalysis } from '@/types'
import AnalyzeButton from '@/components/seo/AnalyzeButton'
import CreateOptimizationsButton from '@/components/seo/CreateOptimizationsButton'
import SeoAnalysisPanel from '@/components/seo/SeoAnalysisPanel'
import OptimizationCard from '@/components/optimizations/OptimizationCard'

function scoreColor(score: number | null) {
  if (score === null) return 'bg-zinc-100 text-zinc-500'
  if (score >= 80) return 'bg-green-100 text-green-700'
  if (score >= 50) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-700'
}

export default async function ListingDetailPage({
  params: { locale, storeId, listingId },
}: {
  params: { locale: string; storeId: string; listingId: string }
}) {
  setRequestLocale(locale)
  const session = await auth()
  if (!session?.accessToken) {
    redirect(`/${locale}/login`)
  }
  const token = session.accessToken

  const t = await getTranslations('listingDetail')

  let listing: ListingDetail
  try {
    const res = await api.listings.get(token, storeId, listingId)
    listing = res.data
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
      redirect(`/${locale}/dashboard/stores`)
    }
    redirect(`/${locale}/login`)
  }

  let analysis: SeoAnalysis | null = null
  try {
    const res = await api.seo.get(token, listingId)
    analysis = res.data
  } catch (err) {
    if (!(err instanceof ApiError && err.status === 404)) throw err
  }

  let optimizations: Optimization[] = []
  try {
    const res = await api.optimizations.list(token, storeId, 'all')
    optimizations = res.data.filter((opt) => opt.listing_id === listingId)
  } catch {
    // non-fatal: the page still renders without the optimization list
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <Link
        href={{ pathname: '/dashboard/stores', query: { store: storeId } }}
        className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t('back')}
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          {listing.main_image_url ? (
            <Image
              src={listing.main_image_url}
              alt=""
              width={96}
              height={96}
              className="h-24 w-24 rounded-xl object-cover"
            />
          ) : (
            <div className="flex h-24 w-24 items-center justify-center rounded-xl bg-zinc-100">
              <ImageOff className="h-8 w-8 text-zinc-400" aria-hidden />
            </div>
          )}
          <div className="min-w-0">
            <h1 className="text-xl font-semibold text-zinc-900">
              {listing.title ?? '—'}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-zinc-500">
              <span className="inline-flex items-center gap-1">
                <Eye className="h-4 w-4" aria-hidden />
                {listing.views_count}
              </span>
              <span className="inline-flex items-center gap-1">
                <Heart className="h-4 w-4" aria-hidden />
                {listing.favorites_count}
              </span>
              <span className="inline-flex items-center gap-1">
                <ShoppingBag className="h-4 w-4" aria-hidden />
                {listing.sales_count}
              </span>
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums',
                  scoreColor(listing.seo_score)
                )}
              >
                {t('seoScore', { score: listing.seo_score ?? '—' })}
              </span>
            </div>
          </div>
        </div>
        <AnalyzeButton listingId={listingId} hasAnalysis={analysis !== null} />
      </div>

      <section className="mt-8">
        <h2 className="text-lg font-semibold text-zinc-900">{t('analysisHeading')}</h2>
        {analysis ? (
          <div className="mt-4 space-y-4">
            <SeoAnalysisPanel analysis={analysis} />
            <CreateOptimizationsButton listingId={listingId} />
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-10 text-center text-sm text-zinc-500">
            {t('noAnalysis')}
          </div>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold text-zinc-900">
          {t('optimizationsHeading')}
        </h2>
        {optimizations.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-10 text-center text-sm text-zinc-500">
            {t('noOptimizations')}
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {optimizations.map((opt) => (
              <OptimizationCard key={opt.id} optimization={opt} />
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
