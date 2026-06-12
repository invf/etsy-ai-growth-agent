import { getTranslations } from 'next-intl/server'
import { Sparkles } from 'lucide-react'
import { auth } from '@/lib/auth'
import { Link } from '@/i18n/navigation'
import LanguageSwitcher from '@/components/layout/LanguageSwitcher'
import SignOutButton from '@/components/layout/SignOutButton'

export default async function Header() {
  const t = await getTranslations('common')
  const tNav = await getTranslations('nav')
  const session = await auth()

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-zinc-900">
          <Sparkles className="h-5 w-5 text-indigo-600" aria-hidden />
          {t('appName')}
        </Link>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          {session ? (
            <>
              <Link
                href="/dashboard"
                className="text-sm font-medium text-zinc-600 hover:text-zinc-900"
              >
                {tNav('dashboard')}
              </Link>
              <Link
                href="/dashboard/stores"
                className="text-sm font-medium text-zinc-600 hover:text-zinc-900"
              >
                {tNav('stores')}
              </Link>
              <SignOutButton />
            </>
          ) : (
            <Link
              href="/login"
              className="text-sm font-medium text-zinc-600 hover:text-zinc-900"
            >
              {tNav('signIn')}
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}
