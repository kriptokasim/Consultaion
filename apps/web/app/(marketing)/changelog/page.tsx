import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Changelog - Consultaion',
  description: 'Product updates, improvements, and fixes.',
}

const entries = [
  {
    slug: 'staged-pipeline-continuation',
    title: 'Staged Pipeline & Continuation',
    published_at: '2025-01-15',
    category: 'Product',
    summary: 'Reliable staged pipeline with resume, idempotent continuation, and stage-level retry safety.',
  },
  {
    slug: 'mobile-workspace',
    title: 'Mobile-First Unified Workspace',
    published_at: '2025-01-10',
    category: 'Mobile',
    summary: 'Fluid decision workspace with progressive perspective cards, compact stage bar, and mobile-optimized composer.',
  },
  {
    slug: 'decision-report-focus-mode',
    title: 'Decision Report Focus Mode',
    published_at: '2025-01-05',
    category: 'Product',
    summary: 'Focus Mode for distraction-free report reading with section navigation and safe-area support.',
  },
]

const categoryColors: Record<string, string> = {
  Product: 'bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-300',
  Mobile: 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300',
  Reliability: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300',
  Security: 'bg-red-100 text-red-800 dark:bg-red-950/40 dark:text-red-300',
  API: 'bg-purple-100 text-purple-800 dark:bg-purple-950/40 dark:text-purple-300',
  Models: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-950/40 dark:text-cyan-300',
}

export default function ChangelogPage() {
  return (
    <main className="container mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-bold text-foreground mb-2">Changelog</h1>
      <p className="text-muted-foreground mb-10">Product updates, improvements, and fixes.</p>

      <div className="space-y-8">
        {entries.map((entry) => (
          <article key={entry.slug} className="border-l-2 border-border pl-6 pb-2">
            <div className="flex items-center gap-3 mb-2">
              <time className="text-xs text-muted-foreground font-mono">{entry.published_at}</time>
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${categoryColors[entry.category] || ''}`}>
                {entry.category}
              </span>
            </div>
            <h2 className="text-lg font-semibold text-foreground">{entry.title}</h2>
            <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{entry.summary}</p>
          </article>
        ))}
      </div>

      <div className="mt-12 text-center text-sm text-muted-foreground">
        RSS feed coming soon.
      </div>
    </main>
  )
}
