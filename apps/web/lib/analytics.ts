let _initialized = false
let _posthog: typeof import('posthog-js')['default'] | null = null

async function getPosthog() {
  if (_posthog) return _posthog
  try {
    const mod = await import('posthog-js')
    _posthog = mod.default
    return _posthog
  } catch {
    return null
  }
}

export async function initPosthog() {
    if (_initialized) return

    const apiKey = process.env.NEXT_PUBLIC_POSTHOG_API_KEY
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST

    const enabled = process.env.NEXT_PUBLIC_ENABLE_POSTHOG === '1'

    if (!enabled || !apiKey || !host) {
        return
    }

    const posthog = await getPosthog()
    if (!posthog) return

    posthog.init(apiKey, {
        api_host: host,
        autocapture: true,
    })

    _initialized = true
}

export async function track(eventName: string, properties?: Record<string, any>) {
    if (!_initialized) return
    const posthog = await getPosthog()
    posthog?.capture(eventName, properties)
}

/**
 * Simple event tracking wrapper - safe to use even if PostHog isn't initialized.
 * Logs to console in development, uses PostHog in production when available.
 * Never throws - analytics must not break UX.
 */
export async function trackEvent(name: string, payload?: Record<string, any>): Promise<void> {
    // Development: Console logging
    if (process.env.NODE_ENV === 'development') {
        console.info('[analytics]', name, payload || {})
    }

    // Production: Try PostHog, fall back to beacon
    try {
        if (isOptedOut()) {
            return
        }

        if (_initialized) {
            const posthog = await getPosthog()
            posthog?.capture(name, payload)
        }
    } catch (e) {
        // Ignore analytics errors
    }
}

export async function setAnalyticsOptOut(optOut: boolean) {
    if (typeof window === 'undefined') return

    if (optOut) {
        localStorage.setItem('analytics_opt_out', 'true')
        if (_initialized) {
            const posthog = await getPosthog()
            posthog?.opt_out_capturing()
        }
    } else {
        localStorage.removeItem('analytics_opt_out')
        if (_initialized) {
            const posthog = await getPosthog()
            posthog?.opt_in_capturing()
        }
    }
}

function isOptedOut(): boolean {
    if (typeof window === 'undefined') return false
    return localStorage.getItem('analytics_opt_out') === 'true'
}
