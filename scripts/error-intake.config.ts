/**
 * Error Intake Pipeline Configuration
 * Centralized configuration for tuning error filtering behavior
 * 
 * Environment variable overrides:
 * - SENTRY_ERROR_MIN_FREQUENCY: Minimum error occurrences to include (default: 2)
 * - SENTRY_ERROR_LIMIT: Default Sentry fetch limit (default: 10)
 */

export interface ErrorIntakeConfig {
    /** Minimum occurrences required to include an error (filters out one-offs) */
    minFrequency: number;
    /** Default limit for Sentry API fetch */
    defaultLimit: number;
    /** Severity levels that trigger PR creation */
    defaultSeverities: Array<'blocker' | 'high' | 'medium' | 'low'>;
}

function parseEnvInt(key: string, defaultValue: number): number {
    const value = process.env[key];
    if (!value) return defaultValue;
    const parsed = parseInt(value, 10);
    return isNaN(parsed) ? defaultValue : parsed;
}

export const config: ErrorIntakeConfig = {
    minFrequency: parseEnvInt('SENTRY_ERROR_MIN_FREQUENCY', 2),
    defaultLimit: parseEnvInt('SENTRY_ERROR_LIMIT', 10),
    defaultSeverities: ['blocker', 'high'],
};

export default config;
