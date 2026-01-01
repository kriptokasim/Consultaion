/**
 * Error Normalizer
 * Converts raw Sentry errors into PatchTask JSON format
 * 
 * Usage: npx ts-node scripts/normalize_errors.ts
 * 
 * Reads: out/sentry_errors.json
 * Outputs: out/patchtasks.json
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { classifyOwnership, classifySeverity, type Area, type Owner, type Severity } from './ownership';

interface SentryIssue {
    id: string;
    title: string;
    culprit: string;
    count: string;
    firstSeen: string;
    lastSeen: string;
    level: string;
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
    entries?: Array<{
        type: string;
        data: {
            values?: Array<{
                stacktrace?: {
                    frames?: Array<{
                        filename?: string;
                        function?: string;
                        lineNo?: number;
                    }>;
                };
            }>;
        };
    }>;
    request?: {
        url?: string;
        method?: string;
    };
}

interface RawSentryError {
    issue: SentryIssue;
    latestEvent?: SentryEvent;
}

interface PatchTask {
    id: string;
    title: string;
    area: Area;
    owner: Owner;
    severity: Severity;
    frequency: number;
    lastSeen: string;
    firstSeen?: string;
    evidence: {
        sentryUrl: string;
        stack: string[];
        breadcrumbs: string[];
        request?: {
            url: string;
            method: string;
        };
    };
    expectedFix: {
        kind: 'guardrail' | 'bugfix' | 'refactor' | 'test' | 'docs';
        filesHint: string[];
        notes: string;
    };
}

function extractStackFrames(event?: SentryEvent): string[] {
    if (!event?.entries) return [];

    const frames: string[] = [];

    for (const entry of event.entries) {
        if (entry.type === 'exception' && entry.data?.values) {
            for (const value of entry.data.values) {
                if (value.stacktrace?.frames) {
                    for (const frame of value.stacktrace.frames.slice(-10)) {
                        if (frame.filename && frame.function) {
                            frames.push(`${frame.filename}:${frame.lineNo || '?'} in ${frame.function}`);
                        }
                    }
                }
            }
        }
    }

    return frames;
}

function suggestFixKind(title: string, severity: Severity): 'guardrail' | 'bugfix' | 'refactor' | 'test' | 'docs' {
    if (/undefined|null|cannot read/i.test(title)) {
        return 'guardrail';
    }
    if (severity === 'blocker' || severity === 'high') {
        return 'bugfix';
    }
    return 'guardrail';
}

function suggestFilesHint(culprit: string, stack: string[]): string[] {
    const hints = new Set<string>();

    // Extract from culprit
    if (culprit && culprit.includes('/')) {
        hints.add(culprit.split(':')[0]);
    }

    // Extract from stack
    for (const frame of stack) {
        const match = frame.match(/^([^:]+):/);
        if (match && match[1].includes('/')) {
            hints.add(match[1]);
        }
    }

    return Array.from(hints).slice(0, 5);
}

function normalizeSentryErrors(raw: RawSentryError[]): PatchTask[] {
    const tasks: PatchTask[] = [];
    const seen = new Set<string>();

    for (const { issue, latestEvent } of raw) {
        // Dedupe by title + culprit
        const fingerprint = `${issue.title}:${issue.culprit}`;
        if (seen.has(fingerprint)) continue;
        seen.add(fingerprint);

        const stack = extractStackFrames(latestEvent);
        const { area, owner } = classifyOwnership(issue.culprit, stack);
        const severity = classifySeverity(issue.title, issue.metadata?.value);
        const fixKind = suggestFixKind(issue.title, severity);
        const filesHint = suggestFilesHint(issue.culprit, stack);

        const task: PatchTask = {
            id: `sentry-${issue.id}`,
            title: issue.title,
            area,
            owner,
            severity,
            frequency: parseInt(issue.count, 10) || 1,
            lastSeen: issue.lastSeen,
            firstSeen: issue.firstSeen,
            evidence: {
                sentryUrl: issue.permalink,
                stack,
                breadcrumbs: [],
                request: latestEvent?.request ? {
                    url: latestEvent.request.url || '',
                    method: latestEvent.request.method || 'GET',
                } : undefined,
            },
            expectedFix: {
                kind: fixKind,
                filesHint,
                notes: `Auto-classified: ${severity} severity ${fixKind} in ${owner}`,
            },
        };

        tasks.push(task);
    }

    // Sort by severity and frequency
    const severityOrder = { blocker: 0, high: 1, medium: 2, low: 3 };
    tasks.sort((a, b) => {
        const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
        if (severityDiff !== 0) return severityDiff;
        return b.frequency - a.frequency;
    });

    return tasks;
}

async function main() {
    const inputPath = join(process.cwd(), 'out', 'sentry_errors.json');
    const outputPath = join(process.cwd(), 'out', 'patchtasks.json');

    if (!existsSync(inputPath)) {
        console.error(`❌ Input file not found: ${inputPath}`);
        console.error(`   Run 'npx ts-node scripts/sentry_errors.ts' first`);
        process.exit(1);
    }

    console.log(`\n📖 Reading Sentry errors from: ${inputPath}`);

    const raw: RawSentryError[] = JSON.parse(readFileSync(inputPath, 'utf-8'));
    console.log(`   Found ${raw.length} raw errors`);

    const tasks = normalizeSentryErrors(raw);
    console.log(`   Normalized to ${tasks.length} PatchTasks (after deduplication)`);

    // Summary by severity
    const bySeverity = tasks.reduce((acc, t) => {
        acc[t.severity] = (acc[t.severity] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    console.log(`\n📊 Severity breakdown:`);
    console.log(`   Blocker: ${bySeverity.blocker || 0}`);
    console.log(`   High: ${bySeverity.high || 0}`);
    console.log(`   Medium: ${bySeverity.medium || 0}`);
    console.log(`   Low: ${bySeverity.low || 0}`);

    mkdirSync(join(process.cwd(), 'out'), { recursive: true });
    writeFileSync(outputPath, JSON.stringify(tasks, null, 2));

    console.log(`\n📁 Output written to: ${outputPath}`);
    console.log(`\n✅ PatchTasks ready for agent consumption!`);
}

main();
