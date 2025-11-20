import type { ReactNode } from "react"

import SettingsNav from "@/components/settings/settings-nav"

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <main className="app-surface min-h-screen px-4 py-8 lg:px-10">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[260px_1fr]">
        <SettingsNav />
        <div className="space-y-6">{children}</div>
      </div>
    </main>
  )
}
