/**
 * Playwright Failure Normalizer
 * Converts Playwright test failures into PatchTask JSON format
 * 
 * Usage: npx ts-node scripts/normalize_playwright_failures.ts
 * 
 * Reads: Playwright JSON report or test results
 * Outputs: out/playwright_patchtasks.json
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
import { join } from 'path';
import { classifyOwnership, classifySeverity, type Area, type Owner, type Severity } from './ownership';

interface PlaywrightTestResult {
    title: string;
    file: string;
    line?: number;
    status: 'passed' | 'failed' | 'timedOut' | 'skipped';
    duration: number;
    error?: {
        message: string;
        stack?: string;
    };
    attachments?: Array<{
        name: string;
        path: string;
        contentType: string;
    }>;
    retry: number;
}

interface PlaywrightReport {
    suites: Array<{
        title: string;
        file: string;
        specs: Array<{
            title: string;
            file: string;
            line: number;
            tests: Array<{
                results: PlaywrightTestResult[];
            }>;
        }>;
    }>;
}

interface PatchTask {
    id: string;
    title: string;
    area: Area;
    owner: Owner;
    severity: Severity;
    frequency: number;
    lastSeen: string;
    evidence: {
        playwrightTest: string;
        testFile: string;
        stack: string[];
        attachments: Array<{
            name: string;
            path: string;
        }>;
    };
    expectedFix: {
        kind: 'guardrail' | 'bugfix' | 'refactor' | 'test' | 'docs';
        filesHint: string[];
        notes: string;
    };
}

function extractFailedTests(report: PlaywrightReport): PlaywrightTestResult[] {
    const failures: PlaywrightTestResult[] = [];

    for (const suite of report.suites) {
        for (const spec of suite.specs) {
            for (const test of spec.tests) {
                for (const result of test.results) {
                    if (result.status === 'failed' || result.status === 'timedOut') {
                        failures.push({
                            ...result,
                            title: spec.title,
                            file: spec.file,
                            line: spec.line,
                        });
                    }
                }
            }
        }
    }

    return failures;
}

function normalizeFailures(failures: PlaywrightTestResult[]): PatchTask[] {
    const tasks: PatchTask[] = [];

    for (const failure of failures) {
        const stackLines = failure.error?.stack?.split('\n').slice(0, 10) || [];
        const { area, owner } = classifyOwnership(failure.file, stackLines);

        // E2E failures are typically high severity
        const severity: Severity = failure.status === 'timedOut' ? 'high' : 'medium';

        const task: PatchTask = {
            id: `playwright-${failure.file.replace(/[^a-z0-9]/gi, '-')}-${failure.title.replace(/[^a-z0-9]/gi, '-')}`.toLowerCase(),
            title: `E2E Test Failed: ${failure.title}`,
            area,
            owner,
            severity,
            frequency: 1,
            lastSeen: new Date().toISOString(),
            evidence: {
                playwrightTest: failure.title,
                testFile: failure.file,
                stack: stackLines,
                attachments: (failure.attachments || []).map(a => ({
                    name: a.name,
                    path: a.path,
                })),
            },
            expectedFix: {
                kind: 'bugfix',
                filesHint: [failure.file],
                notes: failure.error?.message || 'Test failed without error message',
            },
        };

        tasks.push(task);
    }

    return tasks;
}

function findLatestReport(): string | null {
    const possiblePaths = [
        'playwright-report/report.json',
        'test-results/report.json',
        '.playwright-artifacts/report.json',
        'apps/web/playwright-report/report.json',
        'apps/web/test-results/report.json',
    ];

    for (const path of possiblePaths) {
        const fullPath = join(process.cwd(), path);
        if (existsSync(fullPath)) {
            return fullPath;
        }
    }

    return null;
}

async function main() {
    console.log('\n🎭 Normalizing Playwright Failures\n');

    const reportPath = process.argv[2] || findLatestReport();

    if (!reportPath || !existsSync(reportPath)) {
        console.log('ℹ️  No Playwright report found. Run tests first:');
        console.log('   pnpm test:e2e --reporter=json > playwright-report/report.json');
        console.log('\n   Or specify a report path:');
        console.log('   npx ts-node scripts/normalize_playwright_failures.ts <path-to-report.json>');
        process.exit(0);
    }

    console.log(`📖 Reading report from: ${reportPath}`);

    const report: PlaywrightReport = JSON.parse(readFileSync(reportPath, 'utf-8'));
    const failures = extractFailedTests(report);

    console.log(`   Found ${failures.length} failed tests`);

    if (failures.length === 0) {
        console.log('\n✅ No test failures to normalize!');
        process.exit(0);
    }

    const tasks = normalizeFailures(failures);

    const outputDir = join(process.cwd(), 'out');
    mkdirSync(outputDir, { recursive: true });

    const outputPath = join(outputDir, 'playwright_patchtasks.json');
    writeFileSync(outputPath, JSON.stringify(tasks, null, 2));

    console.log(`\n📁 Output written to: ${outputPath}`);
    console.log(`   ${tasks.length} PatchTasks created`);

    // Summary
    console.log('\n📊 Summary:');
    tasks.forEach(t => {
        console.log(`   ❌ ${t.severity.toUpperCase()}: ${t.evidence.playwrightTest}`);
    });
}

main();
