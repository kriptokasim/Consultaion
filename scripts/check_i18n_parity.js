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

function readJsonFile(filePath) {
  try {
    const rawData = fs.readFileSync(filePath, "utf8");
    return JSON.parse(rawData);
  } catch (error) {
    console.error(`Error reading or parsing file at ${filePath}:`, error.message);
    process.exit(1);
  }
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
  process.exit(1);
} else {
  console.log(`\n✅ i18n parity check passed. Both files have the exact same ${enKeys.length} keys.`);
  process.exit(0);
}
