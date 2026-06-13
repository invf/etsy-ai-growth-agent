import createNextIntlPlugin from 'next-intl/plugin'
import { withSentryConfig } from '@sentry/nextjs'

const withNextIntl = createNextIntlPlugin('./i18n/request.ts')

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Required on Next 14 to load instrumentation.ts (stable in Next 15).
    instrumentationHook: true,
  },
  images: {
    remotePatterns: [{ protocol: 'https', hostname: 'i.etsystatic.com' }],
  },
}

export default withSentryConfig(withNextIntl(nextConfig), {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  // Source-map upload runs only when an auth token is present (CI/Vercel);
  // without it the build still succeeds, just without uploaded source maps.
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: !process.env.CI,
  widenClientFileUpload: true,
})
