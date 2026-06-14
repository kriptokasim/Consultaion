export default function LiveLoading() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-6 w-32 bg-slate-200 dark:bg-slate-800 rounded-md" />
          <div className="h-4 w-64 bg-slate-100 dark:bg-slate-900 rounded-md" />
        </div>
      </div>

      {/* Mode cards skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="h-32 bg-slate-100 dark:bg-slate-900/60 rounded-2xl" />
        <div className="h-32 bg-slate-100 dark:bg-slate-900/60 rounded-2xl" />
      </div>

      {/* Composer skeleton */}
      <div className="h-40 bg-slate-100 dark:bg-slate-900/60 rounded-3xl" />
    </div>
  )
}
