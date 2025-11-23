import type { ReactNode } from 'react'

import DashboardShell from '@/components/consultaion/consultaion/dashboard-shell'
import { getMe } from '@/lib/auth'

export default async function AppLayout({ children }: { children: ReactNode }) {
  let profile = null
  try {
    profile = await getMe()
  } catch {
    profile = null
  }

  return <DashboardShell initialProfile={profile}>{children}</DashboardShell>
}
