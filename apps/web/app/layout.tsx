import type { Metadata } from 'next'
import '@/styles/globals.css'
import { I18nProvider, loadMessages, resolveLocale } from '@/lib/i18n/provider'
import { Providers } from './providers';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'),
  title: {
    default: 'Consultaion — Ask Once, Get Answers from Every Top AI',
    template: '%s | Consultaion',
  },
  description: 'Submit one question and get simultaneous answers from GPT-4o, Claude, Gemini, and DeepSeek. Compare AI perspectives side-by-side and get a synthesized final verdict.',
  keywords: ['AI comparison', 'multi-model AI', 'GPT-4o', 'Claude', 'Gemini', 'DeepSeek', 'AI arena', 'LLM comparison'],
  icons: {
    icon: '/icon.png',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'Consultaion',
    title: 'Consultaion — Ask Once, Get Answers from Every Top AI',
  description: 'Submit one question and get simultaneous answers from GPT-4o, Claude, Gemini, and DeepSeek. Compare AI perspectives side-by-side and get a synthesized decision report.',
    images: [
      {
        url: '/api/og?title=Consultaion&models=4',
        width: 1200,
        height: 630,
        alt: 'Consultaion — Multi-model AI Decision Workspace',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Consultaion — Ask Once, Get Answers from Every Top AI',
    description: 'Compare GPT-4o, Claude, Gemini, and DeepSeek answers side-by-side.',
    images: ['/api/og?title=Consultaion&models=4'],
  },
  robots: {
    index: true,
    follow: true,
  },
}

import { AnalyticsProvider } from '@/components/analytics-provider'
import { MobileBottomNav } from '@/components/navigation/MobileBottomNav'

import { ViewTransitions } from 'next-view-transitions'

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await resolveLocale()
  const messages = loadMessages(locale)

  return (
    <ViewTransitions>
      <html lang={locale} suppressHydrationWarning>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        </head>
        <body className="min-h-screen bg-background text-foreground pb-16 sm:pb-0">
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 z-50 rounded bg-primary px-3 py-1 text-primary-foreground"
          >
            Skip to content
          </a>
          <Providers>
            <AnalyticsProvider />
            <I18nProvider locale={locale} messages={messages}>
              {children}
              <MobileBottomNav />
            </I18nProvider>
          </Providers>
        </body>
      </html>
    </ViewTransitions>
  )
}
