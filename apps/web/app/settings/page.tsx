export default function SettingsPage() {
  return (
    <main id="main" className="px-8 py-6 space-y-3">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">Settings</h1>
      <p className="text-sm text-stone-600 dark:text-stone-300">
        Chamber configuration and personal preferences will live here soon. For now, most runtime options are controlled
        via your Consultaion environment variables and team configuration.
      </p>
      <div className="mt-4 rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="text-sm text-stone-600 dark:text-stone-300">
          Tip: you can already adjust debate parameters, models, and quotas in the API configuration. This panel will
          provide a safer UI for those knobs.
        </p>
      </div>
    </main>
  );
}
