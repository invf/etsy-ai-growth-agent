'use client'

import { useState } from 'react'
import { signIn } from 'next-auth/react'
import { useTranslations } from 'next-intl'
import { Link, useRouter } from '@/i18n/navigation'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function RegisterPage() {
  const t = useTranslations('auth.register')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      await api.auth.register({
        name,
        email,
        password,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      })

      // Account created — sign in through NextAuth to establish the session
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
      })

      if (result?.error) {
        setError(tCommon('error'))
        return
      }

      router.push('/dashboard')
      router.refresh()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'EMAIL_ALREADY_EXISTS') {
        setError(t('emailExists'))
      } else if (err instanceof ApiError && err.status === 422) {
        setError(t('passwordHint'))
      } else {
        setError(tCommon('error'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto flex max-w-md flex-col px-4 py-16">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{t('title')}</CardTitle>
          <CardDescription>{t('subtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">{t('name')}</Label>
              <Input
                id="name"
                autoComplete="name"
                required
                minLength={2}
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">{t('email')}</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">{t('password')}</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="text-xs text-zinc-500">{t('passwordHint')}</p>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? t('submitting') : t('submit')}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-zinc-500">
            {t('haveAccount')}{' '}
            <Link href="/login" className="font-medium text-zinc-900 hover:underline">
              {t('loginLink')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  )
}
