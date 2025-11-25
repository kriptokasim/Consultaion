import type { Metadata } from 'next'
import '@/styles/globals.css'
import { I18nProvider, loadMessages, resolveLocale } from '@/lib/i18n/provider'
import { Providers } from './providers';

export const metadata: Metadata = {
  title: 'Consultaion',
  description: 'AI Parliament for multi-agent deliberation',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await resolveLocale()
  const messages = loadMessages(locale)

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
      </head>
      <body className="min-h-screen bg-background text-foreground">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 z-50 rounded bg-primary px-3 py-1 text-primary-foreground"
        >
          Skip to content
        </a>
        <Providers>
          <I18nProvider locale={locale} messages={messages}>
            {children}
          </I18nProvider>
        </Providers>
      </body>
    </html>
  )
}
