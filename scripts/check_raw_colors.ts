#!/usr/bin/env tsx
/**
 * check_raw_colors.ts — Ratcheted semantic-token guard for Patchset 106
 *
 * Scans pilot surface files for raw Tailwind color classes (stone-*, amber-*,
 * slate-*, hex literals) that should be replaced with semantic tokens.
 *
 * Usage:  npx tsx scripts/check_raw_colors.ts
 * Exit:   1 when a new raw-color use is added or the baseline is stale
 */

import { readFileSync, existsSync, writeFileSync } from "fs";
import { resolve } from "path";

const PILOT_FILES = [
    "apps/web/components/settings/theme-toggle.tsx",
    "apps/web/components/ui/button.tsx",
    "apps/web/components/ui/card.tsx",
    "apps/web/app/(app)/dashboard/DashboardClient.tsx",
    "apps/web/components/parliament/ParliamentHome.tsx",
    "apps/web/components/debate/DebateArena.tsx",
    "apps/web/components/parliament/DebateView.tsx",
    "apps/web/components/parliament/VotingSection.tsx",
    "apps/web/components/parliament/LeaderboardTable.tsx",
    "apps/web/components/ui/LLMSelector.tsx",
    "apps/web/components/dashboard/ModelSelector.tsx",
    "apps/web/components/parliament/StatusPill.tsx",
    "apps/web/components/parliament/CIPill.tsx",
    "apps/web/app/(app)/runs/[id]/RunDetailClient.tsx",
];

/**
 * Patterns that indicate raw color usage. Each regex is tested per-line.
 * NOTE: We intentionally allow certain semantic status colors (emerald, rose, red)
 * in controlled contexts like StatusPill and DebateArena status indicators.
 */
const RAW_COLOR_PATTERNS: Array<{ pattern: RegExp; label: string }> = [
    { pattern: /\bstone-\d+/, label: "stone-*" },
    { pattern: /\bamber-\d+/, label: "amber-*" },
    { pattern: /\bslate-\d+/, label: "slate-*" },
    { pattern: /\btext-\[#[0-9a-fA-F]/, label: "text-[#hex]" },
    { pattern: /\bbg-\[#[0-9a-fA-F]/, label: "bg-[#hex]" },
    { pattern: /\bborder-\[#[0-9a-fA-F]/, label: "border-[#hex]" },
    { pattern: /#[0-9a-fA-F]{3,8}/, label: "inline hex" },
];

const ROOT = resolve(import.meta.dirname || __dirname, "..");
const BASELINE_PATH = resolve(ROOT, "scripts/raw_color_baseline.json");
let totalWarnings = 0;
type Finding = { file: string; line: number; label: string; source: string };
const findings: Finding[] = [];

for (const relPath of PILOT_FILES) {
    const absPath = resolve(ROOT, relPath);
    if (!existsSync(absPath)) {
        console.warn(`⚠  File not found: ${relPath}`);
        continue;
    }

    const lines = readFileSync(absPath, "utf8").split("\n");
    const fileWarnings: string[] = [];

    lines.forEach((line, i) => {
        // Skip comments and import lines
        if (line.trim().startsWith("//") || line.trim().startsWith("*") || line.trim().startsWith("import")) return;

        for (const { pattern, label } of RAW_COLOR_PATTERNS) {
            if (pattern.test(line)) {
                const source = line.trim();
                fileWarnings.push(`  L${i + 1}: [${label}] ${source.slice(0, 100)}`);
                findings.push({ file: relPath, line: i + 1, label, source });
            }
        }
    });

    if (fileWarnings.length > 0) {
        console.warn(`\n📁 ${relPath} (${fileWarnings.length} warning${fileWarnings.length > 1 ? "s" : ""})`);
        fileWarnings.forEach((w) => console.warn(w));
        totalWarnings += fileWarnings.length;
    }
}

if (totalWarnings === 0) {
    console.log("\n✅ No raw color usage detected in pilot surface files.\n");
} else {
    console.warn(`\n⚠  ${totalWarnings} raw color warning(s) detected across pilot surfaces.`);
    console.warn("   Consider replacing with semantic tokens (see docs/THEME_MIGRATION.md).\n");
}

function groupBaseline(items: Finding[]) {
    const entries: Record<string, string[]> = {};
    for (const finding of items) {
        entries[finding.file] ??= [];
        entries[finding.file].push(`${finding.label}\u0000${finding.source}`);
    }
    for (const values of Object.values(entries)) values.sort();
    return { version: 1, entries };
}

if (process.argv.includes("--update-baseline")) {
    writeFileSync(BASELINE_PATH, `${JSON.stringify(groupBaseline(findings), null, 2)}\n`);
    console.log(`✅ Updated raw-color baseline with ${findings.length} existing finding(s).`);
    process.exit(0);
}

if (!existsSync(BASELINE_PATH)) {
    console.error(`❌ Missing raw-color baseline: ${BASELINE_PATH}`);
    process.exit(1);
}

const baseline = JSON.parse(readFileSync(BASELINE_PATH, "utf8")) as {
    version: number;
    entries: Record<string, string[]>;
};
const expectedCounts = new Map<string, number>();

for (const [file, entries] of Object.entries(baseline.entries ?? {})) {
    for (const entry of entries) {
        const key = `${file}\u0000${entry}`;
        expectedCounts.set(key, (expectedCounts.get(key) ?? 0) + 1);
    }
}

const regressions: Finding[] = [];
for (const finding of findings) {
    const key = `${finding.file}\u0000${finding.label}\u0000${finding.source}`;
    const remaining = expectedCounts.get(key) ?? 0;
    if (remaining > 0) {
        expectedCounts.set(key, remaining - 1);
    } else {
        regressions.push(finding);
    }
}

const staleEntries = [...expectedCounts.values()].reduce((total, count) => total + count, 0);
if (regressions.length > 0) {
    console.error(`❌ Raw-color guard found ${regressions.length} new violation(s):`);
    regressions.forEach(({ file, line, label, source }) => {
        console.error(`  - ${file}:${line} [${label}] ${source.slice(0, 120)}`);
    });
}
if (staleEntries > 0) {
    console.error(`❌ Raw-color baseline has ${staleEntries} stale entr${staleEntries === 1 ? "y" : "ies"}.`);
}

if (regressions.length > 0 || staleEntries > 0) {
    console.error("   Replace the raw color, or intentionally refresh with: npm run lint:colors -- --update-baseline");
    process.exit(1);
}

console.log("✅ Raw-color guard passed: no new pilot-surface violations.");
process.exit(0);
