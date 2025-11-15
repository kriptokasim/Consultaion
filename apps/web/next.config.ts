import type { NextConfig } from 'next'
import { withSentryConfig } from '@sentry/nextjs'

const nextConfig: NextConfig = {
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve = config.resolve || {}
      config.resolve.fallback = {
        ...(config.resolve.fallback || {}),
        fs: false,
        path: false,
        os: false,
        crypto: false,
      }
    }
    return config
  },
}

const sentryWebpackPluginOptions = {
  silent: true,
}

export default withSentryConfig(nextConfig, sentryWebpackPluginOptions)
