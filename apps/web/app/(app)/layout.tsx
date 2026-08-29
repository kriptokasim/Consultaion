import { Suspense, type ReactNode } from 'react'

import DashboardShell from '@/components/consultaion/consultaion/dashboard-shell'
import { MobileBottomNav } from '@/components/navigation/MobileBottomNav'
import { ReferralClaimBridge } from '@/components/referrals/ReferralClaimBridge'
import { RunStopControl } from '@/components/runs/RunStopControl'
import { getMe } from '@/lib/auth'

export default async function AppLayout({ children }: { children: ReactNode }) {
  let profile = null
  try {
    profile = await getMe()
  } catch {
    profile = null
  }

  return (
    <div className="min-h-screen [--mobile-bottom-nav-height:4rem] pb-[calc(var(--mobile-bottom-nav-height)+env(safe-area-inset-bottom))] sm:pb-0">
      <ReferralClaimBridge enabled={Boolean(profile)} />
      <DashboardShell initialProfile={profile}>{children}</DashboardShell>
      <Suspense fallback={null}>
        <RunStopControl enabled={Boolean(profile)} />
      </Suspense>
      <MobileBottomNav />
    </div>
  )
}
