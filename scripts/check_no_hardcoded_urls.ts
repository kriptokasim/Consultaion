#!/usr/bin/env npx tsx
/**
 * CI Guard: Detect hardcoded domains/URLs in app code.
 *
 * Profiles:
 *   default  – scans apps/web/** only, blocks onrender.com | vercel.app | localhost:
 *   full     – scans entire repo, blocks onrender.com | vercel.app only (localhost: allowed)
 *
 * Usage:
 *   npx tsx scripts/check_no_hardcoded_urls.ts                  # default profile
 *   npx tsx scripts/check_no_hardcoded_urls.ts --profile full   # full profile
 *
 * Exit: 0 = clean, 1 = violations found
 */

import { readFileSync, readdirSync, statSync } from "fs";
import { join, relative } from "path";

const REPO_ROOT = join(__dirname, "..");

// ── CLI args ───────────────────────────────────────────────────────────────
type Profile = "default" | "full";
const profileArg = process.argv.find((_, i) => process.argv[i - 1] === "--profile");
const PROFILE: Profile = profileArg === "full" ? "full" : "default";

// ── Disallowed patterns (per profile) ──────────────────────────────────────
interface PatternRule { label: string; regex: RegExp }

const PROD_DOMAINS: PatternRule[] = [
    { label: "onrender.com", regex: /onrender\.com/gi },
    { label: "vercel.app", regex: /vercel\.app/gi },
];

const LOCALHOST: PatternRule[] = [
    { label: "localhost:", regex: /localhost:/gi },
];

const PATTERNS: Record<Profile, PatternRule[]> = {
    default: [...PROD_DOMAINS, ...LOCALHOST],
    full: [...PROD_DOMAINS],  // localhost: is allowed in full mode
};

// ── Universal skip list (both profiles) ────────────────────────────────────
const SKIP_DIRS = new Set([
    "node_modules", ".git", ".venv", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", "test-results", "out", ".next", "__pycache__",
    "dist", ".gemini",
]);

const BINARY_EXTS = new Set([
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".svg", ".webp", ".mp4", ".webm", ".pack",
]);

function isUniversalSkip(relPath: string, segments: string[], base: string): boolean {
    // Skip dirs that should never be scanned
    if (segments.some((s) => SKIP_DIRS.has(s))) return true;

    // Skip non-text files
    if (BINARY_EXTS.has(base.slice(base.lastIndexOf(".")))) return true;
    if (base.endsWith(".lock")) return true;
    if (base.endsWith(".db")) return true;

    // Skip env files
    if (base === ".env" || base === ".env.local" || base === ".env.example") return true;

    // Skip markdown and READMEs
    if (base.endsWith(".md")) return true;
    if (base.startsWith("README")) return true;

    // Skip docs directory
    if (segments[0] === "docs") return true;

    // Skip coverage / test output artifacts
    if (base === "coverage.xml") return true;
    if (base.startsWith("test_output")) return true;

    // Skip the scanner itself
    if (relPath === "scripts/check_no_hardcoded_urls.ts") return true;

    return false;
}

// ── Default profile: only scan apps/web, skip tests/runtime.ts ─────────────
function isDefaultSkip(relPath: string, segments: string[], base: string): boolean {
    // Only scan apps/web
    if (!(segments[0] === "apps" && segments[1] === "web")) return true;

    // Skip test / e2e files (they legitimately use localhost for test runs)
    if (segments.some((s) => s === "e2e" || s === "tests" || s === "__tests__")) return true;
    if (base.endsWith(".spec.ts") || base.endsWith(".spec.tsx")) return true;
    if (base.endsWith(".test.ts") || base.endsWith(".test.tsx")) return true;
    if (base.startsWith("test_")) return true;

    // Skip the runtime config single-source-of-truth and layout.tsx metadataBase
    if (relPath === "apps/web/lib/config/runtime.ts") return true;
    if (relPath === "apps/web/app/layout.tsx") return true;

    return false;
}

// ── Full profile: scan everything, skip only client SDK examples ───────────
function isFullSkip(relPath: string, segments: string[], base: string): boolean {
    // Skip client SDK examples (they are documentation)
    if (segments.some((s) => s === "clients")) return true;

    // Skip the runtime config and layout.tsx
    if (relPath === "apps/web/lib/config/runtime.ts") return true;
    if (relPath === "apps/web/app/layout.tsx") return true;

    return false;
}

// ── Combined allowlist ─────────────────────────────────────────────────────
function isAllowlisted(relPath: string): boolean {
    const segments = relPath.split("/");
    const base = segments[segments.length - 1];

    if (isUniversalSkip(relPath, segments, base)) return true;

    return PROFILE === "default"
        ? isDefaultSkip(relPath, segments, base)
        : isFullSkip(relPath, segments, base);
}

// ── Walk the file tree ─────────────────────────────────────────────────────
function walk(dir: string): string[] {
    const results: string[] = [];
    for (const entry of readdirSync(dir)) {
        const full = join(dir, entry);
        const rel = relative(REPO_ROOT, full);
        if (isAllowlisted(rel)) continue;
        let stat: ReturnType<typeof statSync>;
        try { stat = statSync(full); } catch { continue; }
        if (stat.isDirectory()) {
            results.push(...walk(full));
        } else if (stat.isFile()) {
            results.push(full);
        }
    }
    return results;
}

// ── Main ───────────────────────────────────────────────────────────────────
interface Violation {
    file: string;
    line: number;
    pattern: string;
    snippet: string;
}

const disallowed = PATTERNS[PROFILE];
const violations: Violation[] = [];

console.log(`\n🔍  Profile: ${PROFILE}  |  Patterns: ${disallowed.map((p) => p.label).join(", ")}\n`);

for (const filePath of walk(REPO_ROOT)) {
    const rel = relative(REPO_ROOT, filePath);
    let content: string;
    try {
        content = readFileSync(filePath, "utf-8");
    } catch {
        continue;
    }

    const lines = content.split("\n");
    for (let i = 0; i < lines.length; i++) {
        for (const { label, regex } of disallowed) {
            regex.lastIndex = 0;
            if (regex.test(lines[i])) {
                violations.push({
                    file: rel,
                    line: i + 1,
                    pattern: label,
                    snippet: lines[i].trim().substring(0, 120),
                });
            }
        }
    }
}

if (violations.length > 0) {
    console.error(`❌  Found ${violations.length} hardcoded URL violation(s):\n`);
    for (const v of violations) {
        console.error(`  ${v.file}:${v.line}  [${v.pattern}]`);
        console.error(`    ${v.snippet}\n`);
    }
    console.error("Fix: use environment variables and the runtime config module.\n");
    process.exit(1);
} else {
    console.log("✅  No hardcoded URL violations found.\n");
    process.exit(0);
}
