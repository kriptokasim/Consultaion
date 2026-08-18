import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const PUBLIC_CONTACT_EMAIL = "info@consultaion.com";

// These are the site-facing surfaces where users can discover or invoke a
// Consultaion contact address. Transactional sender identities and test fixture
// users intentionally live outside this policy because they are not public
// contact channels.
const SITE_CONTACT_FILES = [
  "app/(marketing)/contact/page.tsx",
  "app/(marketing)/security/page.tsx",
  "app/(marketing)/privacy/page.tsx",
  "app/(marketing)/pricing/page.tsx",
  "app/(app)/settings/team/page.tsx",
  "app/(app)/settings/data-retention/page.tsx",
  "public/.well-known/security.txt",
];

function consultaionEmails(source: string): string[] {
  const matches = source.match(/[A-Z0-9._%+-]+@consultaion\.com/gi) ?? [];
  return matches.map((email) => email.toLowerCase());
}

describe("public contact email policy", () => {
  it.each(SITE_CONTACT_FILES)("uses only info@consultaion.com in %s", (relativePath) => {
    const absolutePath = resolve(process.cwd(), relativePath);
    const source = readFileSync(absolutePath, "utf8");
    const emails = consultaionEmails(source);

    expect(emails.length).toBeGreaterThan(0);
    expect(new Set(emails)).toEqual(new Set([PUBLIC_CONTACT_EMAIL]));
  });
});
