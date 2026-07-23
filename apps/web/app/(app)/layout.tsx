import type { ReactNode } from 'react'

import DashboardShell from '@/components/consultaion/consultaion/dashboard-shell'
import { MobileBottomNav } from '@/components/navigation/MobileBottomNav'
import { getMe } from '@/lib/auth'

export default async function AppLayout({ children }: { children: ReactNode }) {
  let profile = null
  try {
    profile = await getMe()
  } catch {
    profile = null
  }

  return (
    <div className="min-h-screen pb-[calc(4rem+env(safe-area-inset-bottom))] sm:pb-0">
      <DashboardShell initialProfile={profile}>{children}</DashboardShell>
      <MobileBottomNav />
    </div>
  )
}
