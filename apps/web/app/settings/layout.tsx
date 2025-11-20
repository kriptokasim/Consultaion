import type { ReactNode } from "react"

import SettingsNav from "@/components/settings/settings-nav"

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="px-6 py-6 lg:px-10">
      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <SettingsNav />
        <div className="space-y-6">{children}</div>
      </div>
    </div>
  )
}
