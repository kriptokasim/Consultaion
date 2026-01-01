/**
 * Agent Patch PR Creator
 * Creates GitHub PRs automatically from normalized PatchTasks
 * 
 * Usage: npx ts-node scripts/agent_patch_pr.ts [--dry-run]
 * 
 * Environment variables:
 * - GITHUB_TOKEN: GitHub personal access token with repo scope
 * - GITHUB_OWNER: Repository owner (e.g., "username" or "org")
 * - GITHUB_REPO: Repository name (e.g., "consultaion")
 * 
 * Workflow:
 * 1. Read PatchTasks from out/patchtasks.json
 * 2. Filter for high-severity, actionable items
 * 3. Create a branch and draft PR for each
 * 4. Include Sentry link, evidence, and suggested fix
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

interface PatchTask {
    id: string;
    title: string;
    area: string;
    owner: string;
    severity: string;
    frequency: number;
    lastSeen: string;
    evidence: {
        sentryUrl?: string;
        stack?: string[];
        playwrightTest?: string;
        testFile?: string;
    };
    expectedFix: {
        kind: string;
        filesHint: string[];
        notes: string;
    };
}

interface GitHubPR {
    title: string;
    body: string;
    head: string;
    base: string;
    draft: boolean;
}

const GITHUB_API = 'https://api.github.com';

async function createBranch(owner: string, repo: string, branchName: string, token: string): Promise<boolean> {
    // Get default branch SHA
    const repoRes = await fetch(`${GITHUB_API}/repos/${owner}/${repo}`, {
        headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/vnd.github.v3+json',
        },
    });

    if (!repoRes.ok) {
        console.error(`Failed to get repo info: ${repoRes.status}`);
        return false;
    }

    const repoData = await repoRes.json();
    const defaultBranch = repoData.default_branch;

    // Get SHA of default branch
    const refRes = await fetch(`${GITHUB_API}/repos/${owner}/${repo}/git/refs/heads/${defaultBranch}`, {
        headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/vnd.github.v3+json',
        },
    });

    if (!refRes.ok) {
        console.error(`Failed to get ref: ${refRes.status}`);
        return false;
    }

    const refData = await refRes.json();
    const sha = refData.object.sha;

    // Create new branch
    const createRes = await fetch(`${GITHUB_API}/repos/${owner}/${repo}/git/refs`, {
        method: 'POST',
        headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            ref: `refs/heads/${branchName}`,
            sha,
        }),
    });

    if (!createRes.ok) {
        const error = await createRes.text();
        if (error.includes('Reference already exists')) {
            console.log(`  Branch ${branchName} already exists`);
            return true;
        }
        console.error(`Failed to create branch: ${createRes.status} - ${error}`);
        return false;
    }

    return true;
}

async function createPullRequest(
    owner: string,
    repo: string,
    pr: GitHubPR,
    token: string
): Promise<{ url: string; number: number } | null> {
    const response = await fetch(`${GITHUB_API}/repos/${owner}/${repo}/pulls`, {
        method: 'POST',
        headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(pr),
    });

    if (!response.ok) {
        const error = await response.text();
        console.error(`Failed to create PR: ${response.status} - ${error}`);
        return null;
    }

    const data = await response.json();
    return { url: data.html_url, number: data.number };
}

function generatePRBody(task: PatchTask): string {
    const lines: string[] = [
        `## 🔧 Auto-generated Fix for: ${task.title}`,
        '',
        `**Severity:** ${task.severity.toUpperCase()}`,
        `**Area:** ${task.area}`,
        `**Owner:** ${task.owner}`,
        `**Occurrences:** ${task.frequency}`,
        `**Last Seen:** ${task.lastSeen}`,
        '',
    ];

    if (task.evidence.sentryUrl) {
        lines.push(`### 🔗 Sentry Issue`);
        lines.push(`[View in Sentry](${task.evidence.sentryUrl})`);
        lines.push('');
    }

    if (task.evidence.playwrightTest) {
        lines.push(`### 🎭 Playwright Test`);
        lines.push(`Test: \`${task.evidence.playwrightTest}\``);
        if (task.evidence.testFile) {
            lines.push(`File: \`${task.evidence.testFile}\``);
        }
        lines.push('');
    }

    if (task.evidence.stack && task.evidence.stack.length > 0) {
        lines.push(`### 📚 Stack Trace`);
        lines.push('```');
        lines.push(...task.evidence.stack.slice(0, 5));
        lines.push('```');
        lines.push('');
    }

    lines.push(`### 💡 Suggested Fix`);
    lines.push(`**Kind:** ${task.expectedFix.kind}`);
    lines.push(`**Notes:** ${task.expectedFix.notes}`);
    lines.push('');

    if (task.expectedFix.filesHint.length > 0) {
        lines.push(`### 📁 Files to Check`);
        task.expectedFix.filesHint.forEach(f => lines.push(`- \`${f}\``));
        lines.push('');
    }

    lines.push('---');
    lines.push('*This PR was auto-generated by the self-healing pipeline. Please review carefully before merging.*');

    return lines.join('\n');
}

function sanitizeBranchName(id: string): string {
    return `fix/${id.replace(/[^a-z0-9-]/gi, '-').toLowerCase().slice(0, 50)}`;
}

async function main() {
    const args = process.argv.slice(2);
    const dryRun = args.includes('--dry-run');
    const severityFilter = args.includes('--all') ? null : ['blocker', 'high'];

    const token = process.env.GITHUB_TOKEN;
    const owner = process.env.GITHUB_OWNER;
    const repo = process.env.GITHUB_REPO;

    if (!dryRun && (!token || !owner || !repo)) {
        console.error('Missing required environment variables:');
        console.error('  GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO');
        console.error('\nUse --dry-run to preview without GitHub access');
        process.exit(1);
    }

    const inputPath = join(process.cwd(), 'out', 'patchtasks.json');

    if (!existsSync(inputPath)) {
        console.error(`❌ PatchTasks not found: ${inputPath}`);
        console.error('   Run the Sentry or Playwright normalization scripts first');
        process.exit(1);
    }

    console.log('\n🤖 Self-Healing Agent PR Creator\n');
    if (dryRun) {
        console.log('🔍 DRY RUN MODE - No PRs will be created\n');
    }

    const tasks: PatchTask[] = JSON.parse(readFileSync(inputPath, 'utf-8'));

    // Filter by severity
    const actionable = severityFilter
        ? tasks.filter(t => severityFilter.includes(t.severity))
        : tasks;

    console.log(`📊 Found ${tasks.length} total tasks, ${actionable.length} actionable\n`);

    if (actionable.length === 0) {
        console.log('✅ No high-severity issues to process');
        process.exit(0);
    }

    const results: Array<{ task: PatchTask; pr?: { url: string; number: number }; error?: string }> = [];

    for (const task of actionable.slice(0, 5)) { // Limit to 5 PRs at a time
        console.log(`\n📝 Processing: ${task.title}`);
        console.log(`   Severity: ${task.severity}, Owner: ${task.owner}`);

        const branchName = sanitizeBranchName(task.id);
        const prBody = generatePRBody(task);

        if (dryRun) {
            console.log(`   Branch: ${branchName}`);
            console.log(`   PR Title: [${task.severity.toUpperCase()}] ${task.title.slice(0, 60)}`);
            console.log('   ---');
            console.log(prBody.split('\n').slice(0, 10).map(l => `   ${l}`).join('\n'));
            console.log('   ...');
            results.push({ task });
            continue;
        }

        // Create branch
        console.log(`   Creating branch: ${branchName}`);
        const branchCreated = await createBranch(owner!, repo!, branchName, token!);

        if (!branchCreated) {
            results.push({ task, error: 'Failed to create branch' });
            continue;
        }

        // Create PR
        console.log(`   Creating draft PR...`);
        const pr = await createPullRequest(owner!, repo!, {
            title: `[${task.severity.toUpperCase()}] ${task.title.slice(0, 60)}`,
            body: prBody,
            head: branchName,
            base: 'main',
            draft: true,
        }, token!);

        if (pr) {
            console.log(`   ✅ Created: ${pr.url}`);
            results.push({ task, pr });
        } else {
            results.push({ task, error: 'Failed to create PR' });
        }
    }

    // Summary
    console.log('\n' + '─'.repeat(50));
    console.log('\n📊 Summary:\n');

    const created = results.filter(r => r.pr);
    const failed = results.filter(r => r.error);

    if (dryRun) {
        console.log(`   ${results.length} PRs would be created`);
    } else {
        console.log(`   ✅ Created: ${created.length}`);
        console.log(`   ❌ Failed: ${failed.length}`);

        if (created.length > 0) {
            console.log('\n   Created PRs:');
            created.forEach(r => console.log(`   - ${r.pr!.url}`));
        }
    }

    console.log('');
}

main();
