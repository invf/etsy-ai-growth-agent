'use client'

import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string }
}) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <html>
      <body>
        <div
          style={{
            display: 'flex',
            minHeight: '100vh',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            fontFamily: 'system-ui, sans-serif',
          }}
        >
          <h2>Something went wrong</h2>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      </body>
    </html>
  )
}
