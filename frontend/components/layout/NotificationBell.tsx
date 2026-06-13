'use client'

import { useEffect, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useLocale, useTranslations } from 'next-intl'
import { Bell } from 'lucide-react'
import { api } from '@/lib/api'
import { useRouter } from '@/i18n/navigation'
import type { AppNotification } from '@/types'

export default function NotificationBell() {
  const t = useTranslations('notifications')
  const locale = useLocale()
  const router = useRouter()
  const { data: session } = useSession()
  const token = session?.accessToken

  const [items, setItems] = useState<AppNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  async function load() {
    if (!token) return
    try {
      const res = await api.notifications.list(token)
      setItems(res.data)
      setUnread(res.meta?.unread_count ?? 0)
    } catch {
      // ignore — the bell is non-critical
    }
  }

  // Load on mount and poll every 60s while the tab is open.
  useEffect(() => {
    if (!token) return
    void load()
    const id = setInterval(() => void load(), 60_000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  // Close the dropdown on outside click.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  async function handleClick(n: AppNotification) {
    if (!n.is_read && token) {
      setItems((prev) =>
        prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x))
      )
      setUnread((u) => Math.max(0, u - 1))
      try {
        await api.notifications.markRead(token, n.id)
      } catch {
        // ignore
      }
    }
    if (n.action_url) {
      setOpen(false)
      router.push(n.action_url)
    }
  }

  if (!token) return null

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t('title')}
        className="relative flex h-9 w-9 items-center justify-center rounded-md text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-lg">
          <div className="border-b border-zinc-100 px-4 py-2.5 text-sm font-semibold text-zinc-900">
            {t('title')}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-zinc-400">
                {t('empty')}
              </p>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleClick(n)}
                  className={`flex w-full flex-col gap-0.5 border-b border-zinc-50 px-4 py-3 text-left hover:bg-zinc-50 ${
                    n.is_read ? '' : 'bg-indigo-50/40'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {!n.is_read && (
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-600" />
                    )}
                    <span className="text-sm font-medium text-zinc-900">
                      {n.title}
                    </span>
                  </div>
                  <span className="text-xs text-zinc-500">{n.message}</span>
                  <span className="mt-0.5 text-[11px] text-zinc-400">
                    {new Date(n.created_at).toLocaleString(locale)}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
