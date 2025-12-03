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
