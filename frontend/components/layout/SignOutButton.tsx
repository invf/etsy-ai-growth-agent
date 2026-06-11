'use client'

import { signOut } from 'next-auth/react'
import { useLocale, useTranslations } from 'next-intl'
import { LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function SignOutButton() {
  const t = useTranslations('nav')
  const locale = useLocale()

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => signOut({ callbackUrl: `/${locale}/login` })}
    >
      <LogOut className="h-4 w-4" />
      {t('signOut')}
    </Button>
  )
}
