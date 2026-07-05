import path from 'path'
import type { NextConfig } from 'next'
import { withSentryConfig } from '@sentry/nextjs'
import bundleAnalyzer from '@next/bundle-analyzer'

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
})

const workspaceRoot = path.join(__dirname, '..', '..')

const nextConfig: NextConfig = {
  output: 'standalone',
  // Patchset 112: Optimize package imports to reduce bundle size
  experimental: {
    optimizePackageImports: [
      'lucide-react',
      'date-fns',
      '@radix-ui/react-icons',
    ],
  },
  eslint: {
    // Re-enable ESLint during production builds to maintain code quality
    ignoreDuringBuilds: false,
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
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
  async headers() {
    const apiOrigin = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
    const posthogHost = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://app.posthog.com";
    const { hostname } = new URL(appUrl);

    // Patchset 148 D2: Content-Security-Policy
    // Conservative starter policy — allows Next.js, Sentry, PostHog, SSE.
    // TODO: Follow-up for nonce-based strict CSP to remove unsafe-inline/unsafe-eval.
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'self'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      `connect-src 'self' ${apiOrigin} ${posthogHost} https: wss:`,
      "form-action 'self'",
      "upgrade-insecure-requests",
    ].join("; ");

    return [
      {
        // Security headers for all routes
        source: "/(.*)",
        headers: [
          { key: "X-DNS-Prefetch-Control", value: "on" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: csp },
        ],
      },
      {
        source: "/api/:path*",
        headers: [
          { key: "X-Forwarded-Host", value: hostname },
          { key: "X-Forwarded-Proto", value: "https" },
        ],
      },
    ];
  },
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