import type { ReactNode } from 'react'
import LanguageSwitcher from '@/components/LanguageSwitcher'

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <div className="flex justify-end px-6 pt-4">
        <LanguageSwitcher />
      </div>
      <div id="main-content">{children}</div>
    </div>
  )
}
