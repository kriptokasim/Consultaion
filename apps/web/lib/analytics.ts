import posthog from 'posthog-js'

let _initialized = false

export function initPosthog() {
    if (_initialized) return

    const apiKey = process.env.NEXT_PUBLIC_POSTHOG_API_KEY
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST

    const enabled = process.env.NEXT_PUBLIC_ENABLE_POSTHOG === '1'

    if (!enabled || !apiKey || !host) {
        return
    }

    posthog.init(apiKey, {
        api_host: host,
        autocapture: true,
    })

    _initialized = true
}

export function track(eventName: string, properties?: Record<string, any>) {
    if (!_initialized) return
    posthog.capture(eventName, properties)
}

/**
 * Simple event tracking wrapper - safe to use even if PostHog isn't initialized.
 * Logs to console in development, uses PostHog in production when available.
 * Never throws - analytics must not break UX.
 */
export function trackEvent(name: string, payload?: Record<string, any>): void {
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
            posthog.capture(name, payload)
        } else if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
            // Fallback: send to /api/events if PostHog not available
            const data = JSON.stringify({
                event: name,
                timestamp: new Date().toISOString(),
                ...payload
            })
            // navigator.sendBeacon('/api/events', data)
        }
    } catch (e) {
        // Ignore analytics errors
    }
}

export function setAnalyticsOptOut(optOut: boolean) {
    if (typeof window === 'undefined') return

    if (optOut) {
        localStorage.setItem('analytics_opt_out', 'true')
        if (_initialized) posthog.opt_out_capturing()
    } else {
        localStorage.removeItem('analytics_opt_out')
        if (_initialized) posthog.opt_in_capturing()
    }
}

function isOptedOut(): boolean {
    if (typeof window === 'undefined') return false
    return localStorage.getItem('analytics_opt_out') === 'true'
}
