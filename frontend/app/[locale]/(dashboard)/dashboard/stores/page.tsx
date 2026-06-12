import { getTranslations, setRequestLocale } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { CheckCircle2, Search, Store as StoreIcon, XCircle } from 'lucide-react'
import { auth } from '@/lib/auth'
import { api } from '@/lib/api'
import { Link } from '@/i18n/navigation'
import { cn } from '@/lib/utils'
import type { ListingsMeta, ListingSummary, Store } from '@/types'
import ConnectStoreButton from '@/components/stores/ConnectStoreButton'
import SyncStoreButton from '@/components/stores/SyncStoreButton'
import ListingsTable from '@/components/listings/ListingsTable'

const OAUTH_ERROR_CODES = new Set(['OAUTH_STATE_MISMATCH', 'OAUTH_FAILED'])

export default async function StoresPage({
  params: { locale },
  searchParams,
}: {
  params: { locale: string }
  searchParams: {
    connected?: string
    shop_name?: string
    error?: string
    store?: string
    page?: string
    sort?: string
    q?: string
  }
}) {
  setRequestLocale(locale)
  const session = await auth()
  if (!session?.accessToken) {
    redirect(`/${locale}/login`)
  }

  const t = await getTranslations('stores')

  let stores: Store[] = []
  try {
    const res = await api.stores.list(session.accessToken)
    stores = res.data
  } catch {
    redirect(`/${locale}/login`)
  }

  const selectedStore =
    stores.find((s) => s.id === searchParams.store) ?? stores[0] ?? null

  const sort = searchParams.sort ?? '-views'
  const page = Math.max(1, Number(searchParams.page) || 1)
  const q = searchParams.q?.trim() || undefined

  let listings: ListingSummary[] = []
  let meta: ListingsMeta | null = null
  let listingsError = false
  if (selectedStore) {
    try {
      const res = await api.listings.list(session.accessToken, selectedStore.id, {
        page,
        per_page: 20,
        sort,
        q,
      })
      listings = res.data
      meta = res.meta ?? null
    } catch {
      listingsError = true
    }
  }

  // Query params shared by table sort/pagination links
  const baseQuery: Record<string, string> = {}
  if (selectedStore) baseQuery.store = selectedStore.id
  if (q) baseQuery.q = q
  if (searchParams.sort) baseQuery.sort = searchParams.sort

  const oauthError = searchParams.error
  const connectedShop =
    searchParams.connected === 'true' ? searchParams.shop_name ?? '' : null

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900">{t('title')}</h1>
          <p className="mt-1 text-sm text-zinc-500">{t('subtitle')}</p>
        </div>
        {stores.length > 0 && <ConnectStoreButton />}
      </div>

      {connectedShop !== null && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden />
          {t('connectedBanner', { shopName: connectedShop })}
        </div>
      )}
      {oauthError && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <XCircle className="h-4 w-4 shrink-0" aria-hidden />
          {OAUTH_ERROR_CODES.has(oauthError)
            ? t(`oauthErrors.${oauthError}`)
            : t('oauthErrors.generic')}
        </div>
      )}

      {stores.length === 0 ? (
        <div className="mt-10 flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white py-16 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100">
            <StoreIcon className="h-8 w-8 text-indigo-600" aria-hidden />
          </div>
          <h2 className="mt-4 text-xl font-semibold text-zinc-900">
            {t('empty.title')}
          </h2>
          <p className="mb-4 mt-1 max-w-sm text-zinc-500">{t('empty.description')}</p>
          <ConnectStoreButton />
        </div>
      ) : (
        <>
          {stores.length > 1 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {stores.map((store) => (
                <Link
                  key={store.id}
                  href={{ pathname: '/dashboard/stores', query: { store: store.id } }}
                  className={cn(
                    'rounded-full border px-4 py-1.5 text-sm font-medium',
                    store.id === selectedStore?.id
                      ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                      : 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50'
                  )}
                >
                  {store.shop_name}
                </Link>
              ))}
            </div>
          )}

          {selectedStore && (
            <>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-zinc-200 bg-white px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-100">
                    <StoreIcon className="h-5 w-5 text-indigo-600" aria-hidden />
                  </div>
                  <div>
                    <p className="font-semibold text-zinc-900">
                      {selectedStore.shop_name}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {t('storeMeta', { count: selectedStore.listing_count })}
                      {' · '}
                      {selectedStore.last_synced_at
                        ? t('sync.lastSynced', {
                            date: new Date(
                              selectedStore.last_synced_at
                            ).toLocaleString(locale),
                          })
                        : t('sync.never')}
                    </p>
                  </div>
                </div>
                <SyncStoreButton
                  storeId={selectedStore.id}
                  syncing={selectedStore.sync_status === 'syncing'}
                />
              </div>

              <form
                method="get"
                className="mt-6 flex max-w-md items-center gap-2"
              >
                <input type="hidden" name="store" value={selectedStore.id} />
                {searchParams.sort && (
                  <input type="hidden" name="sort" value={searchParams.sort} />
                )}
                <div className="relative flex-1">
                  <Search
                    className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
                    aria-hidden
                  />
                  <input
                    type="search"
                    name="q"
                    defaultValue={q ?? ''}
                    placeholder={t('listings.search')}
                    className="h-9 w-full rounded-md border border-zinc-200 bg-white pl-9 pr-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
                  />
                </div>
              </form>

              <div className="mt-4">
                {listingsError ? (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-red-800">
                    {t('errors.listingsFailed')}
                  </div>
                ) : listings.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-12 text-center text-sm text-zinc-500">
                    {q ? t('listings.noResults') : t('listings.empty')}
                  </div>
                ) : (
                  meta && (
                    <ListingsTable
                      listings={listings}
                      meta={meta}
                      query={baseQuery}
                      sort={sort}
                    />
                  )
                )}
              </div>
            </>
          )}
        </>
      )}
    </main>
  )
}
