import type { ReactNode } from 'react'
import { BroadsheetMarketingNav } from '@/components/marketing/broadsheet/BroadsheetMarketingNav'

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen new-ux-marketing">
      <BroadsheetMarketingNav />
      <div id="main-content">{children}</div>
    </div>
  )
}
