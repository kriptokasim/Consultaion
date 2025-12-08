import type { ReactNode } from 'react'
import { MarketingNavbar } from '@/components/landing/MarketingNavbar'

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <MarketingNavbar />
      <div id="main-content" className="pt-20">{children}</div>
    </div>
  )
}
