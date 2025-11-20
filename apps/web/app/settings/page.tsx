export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-600">Account</p>
        <h1 className="heading-serif text-3xl font-semibold text-amber-950">Settings overview</h1>
        <p className="text-sm text-amber-900/70 dark:text-amber-100/70">
          Tune your cockpit preferences, manage billing, and update profile details.
        </p>
      </div>
      <div className="card-elevated max-w-2xl space-y-3 p-6">
        <p className="text-base font-semibold text-amber-950 dark:text-amber-50">Amber cockpit upgrades</p>
        <p className="text-sm text-amber-900/80 dark:text-amber-100/80">
          Profile editing now lives under “Profile” so you can tune your display name, avatar, and timezone. Billing and team controls will gradually move here as well.
        </p>
        <p className="text-sm text-amber-900/80 dark:text-amber-100/80">
          Chamber configuration and advanced knobs still rely on Consultaion environment variables today. This panel will continue to grow as we productize those toggles.
        </p>
      </div>
    </div>
  )
}
