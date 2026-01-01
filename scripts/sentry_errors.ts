/**
 * Sentry Error Fetcher
 * Fetches recent issues from Sentry for analysis and normalization
 * 
 * Usage: npx ts-node scripts/sentry_errors.ts --limit 50
 * 
 * Environment variables:
 * - SENTRY_AUTH_TOKEN: Sentry API auth token
 * - SENTRY_ORG: Sentry organization slug
 * - SENTRY_PROJECT: Sentry project slug
 * - SENTRY_ENV: Environment filter (default: production)
 */

import { writeFileSync } from 'fs';
import { join } from 'path';

interface SentryIssue {
    id: string;
    title: string;
    culprit: string;
    count: string;
    firstSeen: string;
    lastSeen: string;
    level: string;
    status: string;
    platform: string;
    project: { slug: string };
    metadata: {
        type?: string;
        value?: string;
        filename?: string;
        function?: string;
    };
    shortId: string;
    permalink: string;
}

interface SentryEvent {
    eventID: string;
    message?: string;
    title: string;
    platform: string;
    entries?: Array<{
        type: string;
        data: unknown;
    }>;
    tags?: Array<{ key: string; value: string }>;
    contexts?: Record<string, unknown>;
    request?: {
        url?: string;
        method?: string;
        headers?: Record<string, string>;
    };
}

interface RawSentryError {
    issue: SentryIssue;
    latestEvent?: SentryEvent;
}

async function fetchSentryIssues(limit: number): Promise<SentryIssue[]> {
    const token = process.env.SENTRY_AUTH_TOKEN;
    const org = process.env.SENTRY_ORG;
    const project = process.env.SENTRY_PROJECT;
    const env = process.env.SENTRY_ENV || 'production';

    if (!token || !org || !project) {
        console.error('Missing required environment variables:');
        console.error('  SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT');
        process.exit(1);
    }

    const baseUrl = 'https://sentry.io/api/0';
    const url = `${baseUrl}/projects/${org}/${project}/issues/?query=is:unresolved environment:${env}&statsPeriod=7d&limit=${limit}`;

    console.log(`Fetching issues from Sentry: ${org}/${project} (env: ${env})`);

    const response = await fetch(url, {
        headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
    });

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`Sentry API error: ${response.status} - ${text}`);
    }

    return response.json();
}

async function fetchLatestEvent(issueId: string): Promise<SentryEvent | null> {
    const token = process.env.SENTRY_AUTH_TOKEN;

    if (!token) return null;

    try {
        const response = await fetch(`https://sentry.io/api/0/issues/${issueId}/events/latest/`, {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) return null;
        return response.json();
    } catch {
        return null;
    }
}

async function main() {
    const args = process.argv.slice(2);
    const limitIndex = args.indexOf('--limit');
    const limit = limitIndex !== -1 && args[limitIndex + 1]
        ? parseInt(args[limitIndex + 1], 10)
        : 25;

    const fetchEvents = args.includes('--with-events');

    console.log(`\n🔍 Fetching up to ${limit} issues from Sentry...\n`);

    try {
        const issues = await fetchSentryIssues(limit);
        console.log(`✅ Found ${issues.length} issues`);

        const results: RawSentryError[] = [];

        for (const issue of issues) {
            const item: RawSentryError = { issue };

            if (fetchEvents) {
                console.log(`  Fetching event for: ${issue.shortId}`);
                item.latestEvent = await fetchLatestEvent(issue.id) || undefined;
            }

            results.push(item);
        }

        const outputPath = join(process.cwd(), 'out', 'sentry_errors.json');

        // Ensure output directory exists
        const { mkdirSync } = await import('fs');
        mkdirSync(join(process.cwd(), 'out'), { recursive: true });

        writeFileSync(outputPath, JSON.stringify(results, null, 2));
        console.log(`\n📁 Output written to: ${outputPath}`);
        console.log(`\n   Run 'npx ts-node scripts/normalize_errors.ts' to generate PatchTasks`);

    } catch (error) {
        console.error('❌ Error fetching Sentry issues:', error);
        process.exit(1);
    }
}

main();
