#!/usr/bin/env node

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// Set up __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rootDir = path.resolve(__dirname, "..");
const enPath = path.join(rootDir, "apps/web/locales/en.json");
const trPath = path.join(rootDir, "apps/web/locales/tr.json");
const literalBaselinePath = path.join(rootDir, "scripts/i18n_literal_baseline.json");
const literalScanRoots = [
  "apps/web/app/(app)",
  "apps/web/components/parliament",
  "apps/web/components/prompt",
];

function readJsonFile(filePath) {
  try {
    const rawData = fs.readFileSync(filePath, "utf8");
    return JSON.parse(rawData);
  } catch (error) {
    console.error(`Error reading or parsing file at ${filePath}:`, error.message);
    process.exit(1);
  }
}

function walkTsxFiles(directory) {
  if (!fs.existsSync(directory)) return [];

  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) return walkTsxFiles(absolutePath);
    if (!entry.name.endsWith(".tsx") || /\.(?:test|spec)\.tsx$/.test(entry.name)) return [];
    return [absolutePath];
  });
}

function normalizeLiteral(value) {
  return value.replace(/&[a-z]+;/gi, " ").replace(/\s+/g, " ").trim();
}

function isLongUiLiteral(value) {
  const normalized = normalizeLiteral(value);
  const words = normalized.match(/[\p{L}\p{N}][\p{L}\p{N}'’./+-]*/gu) ?? [];
  return /^\p{Lu}/u.test(normalized) && words.length >= 4;
}

function findUiLiterals(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const findings = [];
  const seen = new Set();

  source.split("\n").forEach((line, index) => {
    const trimmed = line.trim();
    if (
      !trimmed ||
      trimmed.startsWith("//") ||
      trimmed.startsWith("/*") ||
      trimmed.startsWith("*") ||
      trimmed.startsWith("import ") ||
      trimmed.includes("console.")
    ) {
      return;
    }

    const candidates = [];
    for (const match of line.matchAll(/>([^<>{}]+)</g)) candidates.push(match[1]);
    for (const match of line.matchAll(/(["'`])([^"'`]+)\1/g)) candidates.push(match[2]);

    for (const candidate of candidates) {
      const literal = normalizeLiteral(candidate);
      if (!isLongUiLiteral(literal)) continue;

      const fingerprint = `${index + 1}:${literal}`;
      if (seen.has(fingerprint)) continue;
      seen.add(fingerprint);
      findings.push({ line: index + 1, literal });
    }
  });

  return findings;
}

function collectUiLiteralFindings() {
  return literalScanRoots.flatMap(relativeRoot => {
    const absoluteRoot = path.join(rootDir, relativeRoot);
    return walkTsxFiles(absoluteRoot).flatMap(filePath => {
      const relativePath = path.relative(rootDir, filePath).split(path.sep).join("/");
      return findUiLiterals(filePath).map(finding => ({ file: relativePath, ...finding }));
    });
  });
}

function groupLiteralBaseline(findings) {
  const literals = {};
  for (const finding of findings) {
    literals[finding.file] ??= [];
    literals[finding.file].push(finding.literal);
  }
  for (const values of Object.values(literals)) values.sort();
  return { version: 1, literals };
}

function compareLiteralBaseline(findings, baseline) {
  const expectedCounts = new Map();
  for (const [file, literals] of Object.entries(baseline.literals ?? {})) {
    for (const literal of literals) {
      const key = `${file}\u0000${literal}`;
      expectedCounts.set(key, (expectedCounts.get(key) ?? 0) + 1);
    }
  }

  const regressions = [];
  for (const finding of findings) {
    const key = `${finding.file}\u0000${finding.literal}`;
    const remaining = expectedCounts.get(key) ?? 0;
    if (remaining > 0) {
      expectedCounts.set(key, remaining - 1);
    } else {
      regressions.push(finding);
    }
  }

  const staleEntries = [...expectedCounts.values()].reduce((total, count) => total + count, 0);
  return { regressions, staleEntries };
}

console.log("Checking translation keys parity between English and Turkish...");

const enJson = readJsonFile(enPath);
const trJson = readJsonFile(trPath);

const enKeys = Object.keys(enJson);
const trKeys = Object.keys(trJson);

const enKeysSet = new Set(enKeys);
const trKeysSet = new Set(trKeys);

const missingInTr = enKeys.filter(key => !trKeysSet.has(key));
const missingInEn = trKeys.filter(key => !enKeysSet.has(key));

let hasDrift = false;

if (missingInTr.length > 0) {
  console.error(`\n❌ Found ${missingInTr.length} keys present in EN but missing in TR:`);
  missingInTr.forEach(key => console.error(`  - ${key}`));
  hasDrift = true;
}

if (missingInEn.length > 0) {
  console.error(`\n❌ Found ${missingInEn.length} keys present in TR but missing in EN:`);
  missingInEn.forEach(key => console.error(`  - ${key}`));
  hasDrift = true;
}

if (hasDrift) {
  console.error("\n❌ i18n parity check failed. Please ensure both translation files have the exact same keys.");
} else {
  console.log(`\n✅ i18n parity check passed. Both files have the exact same ${enKeys.length} keys.`);
}

const literalFindings = collectUiLiteralFindings();
if (process.argv.includes("--update-literal-baseline")) {
  fs.writeFileSync(literalBaselinePath, `${JSON.stringify(groupLiteralBaseline(literalFindings), null, 2)}\n`);
  console.log(`\n✅ Updated i18n literal baseline with ${literalFindings.length} existing finding(s).`);
  process.exit(hasDrift ? 1 : 0);
}

const literalBaseline = readJsonFile(literalBaselinePath);
const { regressions, staleEntries } = compareLiteralBaseline(literalFindings, literalBaseline);

if (regressions.length > 0) {
  console.error(`\n❌ Found ${regressions.length} new long-form JSX literal(s). Use useI18n()/t() instead:`);
  regressions.forEach(({ file, line, literal }) => console.error(`  - ${file}:${line} — ${literal}`));
  hasDrift = true;
} else {
  console.log(`\n✅ i18n literal guard passed across ${literalScanRoots.length} guarded surface roots.`);
}

if (staleEntries > 0) {
  console.error(`\n❌ i18n literal baseline has ${staleEntries} stale entr${staleEntries === 1 ? "y" : "ies"}.`);
  console.error("   Run: node scripts/check_i18n_parity.js --update-literal-baseline");
  hasDrift = true;
}

process.exit(hasDrift ? 1 : 0);
