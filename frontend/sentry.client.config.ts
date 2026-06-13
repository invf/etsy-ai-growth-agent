import * as Sentry from '@sentry/nextjs'

// Init only when a DSN is configured, so local/dev and DSN-less builds are no-ops.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENV ?? 'production',
    tracesSampleRate: 0.1,
    // Keep the client bundle lean — no session replay for the MVP.
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
  })
}
