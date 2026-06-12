import Image from 'next/image'
import { useLocale, useTranslations } from 'next-intl'
import { ArrowDown, ArrowUp, ImageOff } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { cn } from '@/lib/utils'
import type { ListingsMeta, ListingSummary } from '@/types'

const SORTABLE = {
  price: 'price',
  views: 'views',
  favorites: 'favorites',
  sales: 'sales',
  seoScore: 'seo_score',
} as const

type Query = Record<string, string>

function scoreColor(score: number | null) {
  if (score === null) return 'bg-zinc-100 text-zinc-500'
  if (score >= 80) return 'bg-green-100 text-green-700'
  if (score >= 50) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-700'
}

export default function ListingsTable({
  listings,
  meta,
  query,
  sort,
}: {
  listings: ListingSummary[]
  meta: ListingsMeta
  query: Query
  sort: string
}) {
  const t = useTranslations('stores.listings')
  const locale = useLocale()

  const descending = sort.startsWith('-')
  const sortKey = sort.replace(/^-/, '')

  function sortHref(column: string): { pathname: '/dashboard/stores'; query: Query } {
    // Clicking the active column flips direction; a new column starts descending
    const next = sortKey === column && descending ? column : `-${column}`
    return { pathname: '/dashboard/stores', query: { ...query, sort: next, page: '1' } }
  }

  function pageHref(page: number): { pathname: '/dashboard/stores'; query: Query } {
    return { pathname: '/dashboard/stores', query: { ...query, page: String(page) } }
  }

  function formatPrice(listing: ListingSummary) {
    if (listing.price_usd === null) return '—'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: listing.currency_code || 'USD',
    }).format(Number(listing.price_usd))
  }

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500">
            <th className="px-4 py-3 font-medium">{t('columns.listing')}</th>
            <th className="px-4 py-3 font-medium">{t('columns.state')}</th>
            {(Object.keys(SORTABLE) as (keyof typeof SORTABLE)[]).map((key) => (
              <th key={key} className="px-4 py-3 font-medium">
                <Link
                  href={sortHref(SORTABLE[key])}
                  className="inline-flex items-center gap-1 hover:text-zinc-900"
                >
                  {t(`columns.${key}`)}
                  {sortKey === SORTABLE[key] &&
                    (descending ? (
                      <ArrowDown className="h-3 w-3" aria-hidden />
                    ) : (
                      <ArrowUp className="h-3 w-3" aria-hidden />
                    ))}
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {listings.map((listing) => (
            <tr key={listing.id} className="border-b border-zinc-100 last:border-0">
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  {listing.main_image_url ? (
                    <Image
                      src={listing.main_image_url}
                      alt=""
                      width={40}
                      height={40}
                      className="h-10 w-10 shrink-0 rounded-md object-cover"
                    />
                  ) : (
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-zinc-100">
                      <ImageOff className="h-4 w-4 text-zinc-400" aria-hidden />
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="truncate font-medium text-zinc-900" title={listing.title ?? ''}>
                      {listing.title ?? '—'}
                    </p>
                    <p className="truncate text-xs text-zinc-500">
                      {listing.tags.slice(0, 3).join(' · ')}
                    </p>
                  </div>
                </div>
              </td>
              <td className="px-4 py-3 capitalize text-zinc-600">{listing.state}</td>
              <td className="px-4 py-3 tabular-nums">{formatPrice(listing)}</td>
              <td className="px-4 py-3 tabular-nums">{listing.views_count}</td>
              <td className="px-4 py-3 tabular-nums">{listing.favorites_count}</td>
              <td className="px-4 py-3 tabular-nums">{listing.sales_count}</td>
              <td className="px-4 py-3">
                <span
                  className={cn(
                    'inline-flex min-w-9 justify-center rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums',
                    scoreColor(listing.seo_score)
                  )}
                >
                  {listing.seo_score ?? '—'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex items-center justify-between border-t border-zinc-200 px-4 py-3 text-sm text-zinc-500">
        <span>
          {t('pagination', {
            page: meta.page,
            totalPages: meta.total_pages,
            total: meta.total,
          })}
        </span>
        <div className="flex gap-2">
          {meta.page > 1 && (
            <Link
              href={pageHref(meta.page - 1)}
              className="rounded-md border border-zinc-200 px-3 py-1 hover:bg-zinc-50"
            >
              {t('prev')}
            </Link>
          )}
          {meta.page < meta.total_pages && (
            <Link
              href={pageHref(meta.page + 1)}
              className="rounded-md border border-zinc-200 px-3 py-1 hover:bg-zinc-50"
            >
              {t('next')}
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
