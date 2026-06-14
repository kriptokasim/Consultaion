export default function SettingsLoading() {
  return (
    <div className="container mx-auto max-w-4xl p-6 space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-slate-200 dark:bg-slate-800 rounded-md" />
      <div className="h-4 w-80 bg-slate-100 dark:bg-slate-900 rounded-md" />
      <div className="grid gap-6 lg:grid-cols-[1.6fr_0.9fr]">
        <div className="h-64 bg-slate-100 dark:bg-slate-900/60 rounded-2xl" />
        <div className="h-48 bg-slate-100 dark:bg-slate-900/60 rounded-2xl" />
      </div>
    </div>
  )
}
