export default function SettingsPage() {
  return (
    <main id="main" className="px-8 py-6 space-y-6">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">Settings</h1>
      <div className="max-w-2xl space-y-3 rounded-2xl border border-stone-200 bg-white p-5 shadow-[0_14px_30px_rgba(112,73,28,0.12)] dark:border-stone-700 dark:bg-stone-900">
        <p className="text-base font-semibold text-stone-800 dark:text-stone-100">Coming soon</p>
        <p className="text-sm text-stone-700 dark:text-stone-200">
          Chamber configuration and personal preferences will live here. For now, most runtime options are handled via Consultaion environment variables and team configuration.
        </p>
        <p className="text-sm text-stone-700 dark:text-stone-200">
          Tip: you can already adjust debate parameters, models, and quotas in the API configuration. This panel will provide a safer UI for those knobs.
        </p>
      </div>
    </main>
  );
}
