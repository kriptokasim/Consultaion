#!/usr/bin/env tsx
/**
 * check_raw_colors.ts — Warning-mode lint script for Patchset 106
 *
 * Scans pilot surface files for raw Tailwind color classes (stone-*, amber-*,
 * slate-*, hex literals) that should be replaced with semantic tokens.
 *
 * Usage:  npx tsx scripts/check_raw_colors.ts
 * Exit:   0 (warning mode only, never fails CI)
 */

import { readFileSync, existsSync } from "fs";
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
let totalWarnings = 0;

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
                fileWarnings.push(`  L${i + 1}: [${label}] ${line.trim().slice(0, 100)}`);
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

// Always exit 0 — this is warning-mode only
process.exit(0);
