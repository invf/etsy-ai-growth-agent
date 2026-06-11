import { getTranslations, setRequestLocale } from 'next-intl/server'
import { Link } from '@/i18n/navigation'
import { Button } from '@/components/ui/button'

export default async function HomePage({
  params: { locale },
}: {
  params: { locale: string }
}) {
  setRequestLocale(locale)
  const t = await getTranslations('home')

  return (
    <main className="mx-auto flex max-w-3xl flex-col items-center px-4 py-24 text-center">
      <h1 className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl">
        {t('title')}
      </h1>
      <p className="mt-4 max-w-xl text-lg text-zinc-600">{t('subtitle')}</p>
      <div className="mt-8 flex gap-3">
        <Link href="/register">
          <Button size="lg">{t('getStarted')}</Button>
        </Link>
        <Link href="/login">
          <Button size="lg" variant="outline">
            {t('signIn')}
          </Button>
        </Link>
      </div>
    </main>
  )
}
