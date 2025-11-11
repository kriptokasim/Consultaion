import type { ReactNode } from 'react'
import '../styles/globals.css'

export const metadata = {
  title: 'Consultaion',
  description: 'AI Consultation by Multi-Agent Deliberation'
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900">{children}</body>
    </html>
  )
}
