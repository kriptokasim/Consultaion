import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sub-processors - Consultaion',
  description: 'Third-party sub-processors that handle data on behalf of Consultaion.',
}

const subprocessors = [
  {
    vendor: 'Stripe, Inc.',
    purpose: 'Payment processing and subscription management',
    data_categories: ['Billing email', 'Payment method metadata', 'Subscription status'],
    region: 'United States',
    dpa_status: 'Standard DPA in place',
    updated: '2025-01-01',
  },
  {
    vendor: 'OpenAI, LLC',
    purpose: 'AI model inference for decision analysis',
    data_categories: ['Prompt text', 'Model responses (temporarily)'],
    region: 'United States',
    dpa_status: 'Data Processing Addendum signed',
    updated: '2025-01-01',
  },
  {
    vendor: 'Anthropic, PBC',
    purpose: 'AI model inference for decision analysis',
    data_categories: ['Prompt text', 'Model responses (temporarily)'],
    region: 'United States',
    dpa_status: 'Data Processing Addendum signed',
    updated: '2025-01-01',
  },
  {
    vendor: 'Google LLC',
    purpose: 'AI model inference for decision analysis',
    data_categories: ['Prompt text', 'Model responses (temporarily)'],
    region: 'United States',
    dpa_status: 'Data Processing Addendum signed',
    updated: '2025-01-01',
  },
  {
    vendor: 'PostHog, Inc.',
    purpose: 'Product analytics (anonymized)',
    data_categories: ['Anonymous usage events', 'Feature flag evaluations'],
    region: 'United States / EU',
    dpa_status: 'Standard DPA in place',
    updated: '2025-01-01',
  },
  {
    vendor: 'Redis Ltd.',
    purpose: 'Caching, rate limiting, and real-time messaging',
    data_categories: ['Session tokens (ephemeral)', 'Rate-limit counters'],
    region: 'Configurable',
    dpa_status: 'Standard DPA in place',
    updated: '2025-01-01',
  },
  {
    vendor: 'Vercel Inc.',
    purpose: 'Frontend hosting and edge network',
    data_categories: ['Request logs (anonymized)', 'Static assets'],
    region: 'Global CDN',
    dpa_status: 'Standard DPA in place',
    updated: '2025-01-01',
  },
]

export default function SubProcessorsPage() {
  return (
    <main className="container mx-auto max-w-4xl px-4 py-12">
      <h1 className="text-3xl font-bold text-foreground mb-2">Sub-processors</h1>
      <p className="text-muted-foreground mb-8 max-w-2xl">
        Third-party services that process data on behalf of Consultaion to deliver our service.
      </p>

      <div className="space-y-4">
        {subprocessors.map((sp) => (
          <div key={sp.vendor} className="border border-border rounded-xl p-5 bg-card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold text-foreground">{sp.vendor}</h3>
                <p className="text-sm text-muted-foreground mt-1">{sp.purpose}</p>
              </div>
              <span className="text-[10px] font-mono text-muted-foreground shrink-0">Updated: {sp.updated}</span>
            </div>
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <span className="font-medium text-muted-foreground">Data categories</span>
                <p className="text-foreground mt-0.5">{sp.data_categories.join(', ')}</p>
              </div>
              <div>
                <span className="font-medium text-muted-foreground">Processing region</span>
                <p className="text-foreground mt-0.5">{sp.region}</p>
              </div>
              <div>
                <span className="font-medium text-muted-foreground">DPA status</span>
                <p className="text-foreground mt-0.5">{sp.dpa_status}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-8 text-xs text-muted-foreground">
        We notify customers of material changes to our sub-processor list at least 30 days before any new sub-processor begins processing personal data.
      </p>
    </main>
  )
}
