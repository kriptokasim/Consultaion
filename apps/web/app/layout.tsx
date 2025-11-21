import type { Metadata } from 'next'
import DashboardShell from '@/components/consultaion/consultaion/dashboard-shell'
import '@/styles/globals.css'

export const metadata: Metadata = {
  title: 'Consultaion',
  description: 'AI Parliament for multi-agent deliberation',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
      </head>
      <body className="min-h-screen bg-background text-foreground">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 z-50 rounded bg-primary px-3 py-1 text-primary-foreground"
        >
          Skip to content
        </a>
        <DashboardShell>{children}</DashboardShell>
      </body>
    </html>
  )
}
