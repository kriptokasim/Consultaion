import path from 'path'
import type { NextConfig } from 'next'
import { withSentryConfig } from '@sentry/nextjs'
import bundleAnalyzer from '@next/bundle-analyzer'

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
})

const workspaceRoot = path.join(__dirname, '..', '..')

const nextConfig: NextConfig = {
  eslint: {
    // Allow production builds to complete even with ESLint errors
    // This prevents the circular JSON structure error during Vercel builds
    ignoreDuringBuilds: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
      {
        protocol: 'https',
        hostname: 'api.dicebear.com',
      },
    ],
  },
  outputFileTracingRoot: workspaceRoot,
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

const configWithAnalyzer = withBundleAnalyzer(nextConfig)

export default withSentryConfig(configWithAnalyzer, sentryWebpackPluginOptions)
