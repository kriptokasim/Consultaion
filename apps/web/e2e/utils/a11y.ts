import { Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

export interface A11yOptions {
    skipFailures?: boolean
    includedImpacts?: ('critical' | 'serious' | 'moderate' | 'minor')[]
}

export async function checkA11y(
    page: Page,
    options?: A11yOptions
) {
    const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()

    const impacts = options?.includedImpacts || ['critical', 'serious']
    const violations = results.violations.filter(v =>
        impacts.includes(v.impact as any)
    )

    if (violations.length > 0 && !options?.skipFailures) {
        const message = violations.map(v =>
            `[${v.impact}] ${v.id}: ${v.description}\n` +
            v.nodes.map(n => `  - ${n.failureSummary}`).join('\n')
        ).join('\n\n')

        throw new Error(`Accessibility violations found:\n\n${message}`)
    }

    return { violations, passes: results.passes }
}
