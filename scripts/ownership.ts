/**
 * Error Ownership Mapping
 * Maps file paths and stack patterns to component owners
 */

export type Area = 'frontend' | 'backend' | 'infra';
export type Owner = 'dashboard' | 'runs' | 'voting' | 'auth' | 'billing' | 'admin' | 'sse' | 'db' | 'api' | 'marketing' | 'settings';
export type Severity = 'blocker' | 'high' | 'medium' | 'low';

interface OwnershipRule {
    pattern: RegExp;
    area: Area;
    owner: Owner;
}

// File path patterns to owner mapping
export const ownershipRules: OwnershipRule[] = [
    // Frontend - Dashboard
    { pattern: /apps\/web\/app\/\(app\)\/dashboard/, area: 'frontend', owner: 'dashboard' },
    { pattern: /components\/dashboard/, area: 'frontend', owner: 'dashboard' },

    // Frontend - Runs
    { pattern: /apps\/web\/app\/\(app\)\/runs/, area: 'frontend', owner: 'runs' },
    { pattern: /components\/parliament/, area: 'frontend', owner: 'runs' },
    { pattern: /components\/consultaion/, area: 'frontend', owner: 'runs' },

    // Frontend - Auth
    { pattern: /apps\/web\/app\/\(marketing\)\/(login|register)/, area: 'frontend', owner: 'auth' },
    { pattern: /components\/auth/, area: 'frontend', owner: 'auth' },

    // Frontend - Settings & Billing
    { pattern: /apps\/web\/app\/\(app\)\/settings/, area: 'frontend', owner: 'settings' },
    { pattern: /components\/settings/, area: 'frontend', owner: 'settings' },
    { pattern: /components\/billing/, area: 'frontend', owner: 'billing' },

    // Frontend - Admin
    { pattern: /apps\/web\/app\/\(app\)\/admin/, area: 'frontend', owner: 'admin' },

    // Frontend - Marketing
    { pattern: /apps\/web\/app\/\(marketing\)/, area: 'frontend', owner: 'marketing' },
    { pattern: /components\/landing/, area: 'frontend', owner: 'marketing' },

    // Backend - Auth
    { pattern: /apps\/api\/routes\/auth/, area: 'backend', owner: 'auth' },
    { pattern: /apps\/api\/auth/, area: 'backend', owner: 'auth' },

    // Backend - Debates/Runs
    { pattern: /apps\/api\/routes\/debates/, area: 'backend', owner: 'runs' },
    { pattern: /apps\/api\/parliament/, area: 'backend', owner: 'runs' },
    { pattern: /apps\/api\/agents/, area: 'backend', owner: 'runs' },

    // Backend - Voting
    { pattern: /apps\/api\/routes\/votes/, area: 'backend', owner: 'voting' },

    // Backend - Admin
    { pattern: /apps\/api\/routes\/admin/, area: 'backend', owner: 'admin' },

    // Backend - Billing
    { pattern: /apps\/api\/routes\/billing/, area: 'backend', owner: 'billing' },

    // Backend - SSE
    { pattern: /apps\/api\/sse/, area: 'backend', owner: 'sse' },

    // Backend - Database
    { pattern: /apps\/api\/models/, area: 'backend', owner: 'db' },
    { pattern: /apps\/api\/database/, area: 'backend', owner: 'db' },

    // Infra
    { pattern: /docker|Dockerfile|compose/, area: 'infra', owner: 'api' },
    { pattern: /\.github\/workflows/, area: 'infra', owner: 'api' },
];

// Severity classification based on error patterns
export const severityRules: Array<{ pattern: RegExp; severity: Severity }> = [
    // Blockers - Critical auth/create flows
    { pattern: /login.*loop|auth.*fail|session.*invalid/i, severity: 'blocker' },
    { pattern: /debate.*creation.*fail|cannot.*create.*debate/i, severity: 'blocker' },
    { pattern: /SSR.*crash|hydration.*fail|render.*error/i, severity: 'blocker' },

    // High - Important functionality broken
    { pattern: /run.*page.*fail|replay.*error/i, severity: 'high' },
    { pattern: /vote.*fail|voting.*error/i, severity: 'high' },
    { pattern: /5\d{2}.*error|internal.*server/i, severity: 'high' },
    { pattern: /TypeError|ReferenceError/i, severity: 'high' },

    // Medium - UI issues
    { pattern: /layout.*shift|style.*broken/i, severity: 'medium' },
    { pattern: /dark.*mode.*fail/i, severity: 'medium' },
    { pattern: /translation.*missing|i18n.*error/i, severity: 'medium' },

    // Low - Minor issues
    { pattern: /console.*warn|deprecat/i, severity: 'low' },
];

/**
 * Determine area and owner from file path or stack trace
 */
export function classifyOwnership(
    filepath?: string,
    stack?: string[]
): { area: Area; owner: Owner } {
    const textToCheck = [filepath, ...(stack || [])].filter(Boolean).join('\n');

    for (const rule of ownershipRules) {
        if (rule.pattern.test(textToCheck)) {
            return { area: rule.area, owner: rule.owner };
        }
    }

    // Default fallback
    if (textToCheck.includes('apps/web')) {
        return { area: 'frontend', owner: 'dashboard' };
    }
    if (textToCheck.includes('apps/api')) {
        return { area: 'backend', owner: 'api' };
    }

    return { area: 'frontend', owner: 'dashboard' };
}

/**
 * Determine severity from error title/message
 */
export function classifySeverity(title: string, message?: string): Severity {
    const text = [title, message].filter(Boolean).join(' ');

    for (const rule of severityRules) {
        if (rule.pattern.test(text)) {
            return rule.severity;
        }
    }

    return 'medium';
}
