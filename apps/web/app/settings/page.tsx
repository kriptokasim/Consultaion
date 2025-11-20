export default function SettingsPage() {
  return (
    <main id="main" className="space-y-6">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">Settings</h1>
      <div className="max-w-2xl space-y-3 rounded-2xl border border-stone-200 bg-white p-5 shadow-[0_14px_30px_rgba(112,73,28,0.12)] dark:border-stone-700 dark:bg-stone-900">
        <p className="text-base font-semibold text-stone-800 dark:text-stone-100">Amber cockpit upgrades</p>
        <p className="text-sm text-stone-700 dark:text-stone-200">
          Profile editing now lives under “Profile” so you can tune your display name, avatar, and timezone. Billing and team controls will gradually move here as well.
        </p>
        <p className="text-sm text-stone-700 dark:text-stone-200">
          Chamber configuration and advanced knobs still rely on Consultaion environment variables today. This panel will continue to grow as we productize those toggles.
        </p>
      </div>
    </main>
  )
}
