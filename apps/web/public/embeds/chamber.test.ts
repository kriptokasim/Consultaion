import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The chamber embed is plain HTML with an inline script, outside the bundler and
 * outside type checking, so nothing catches a typo in it until it reaches a
 * browser. It reached one: `C.alabaster` was referenced three times and never
 * defined, so `undefined` flowed into shade() and threw on every affected face,
 * every frame -- thousands of exceptions and a blank hero on the landing page.
 *
 * These tests are cheap and they close that exact class.
 */

const SOURCE = readFileSync(
  join(__dirname, "consultaion-chamber.html"),
  "utf8",
);

function script(): string {
  const match = SOURCE.match(/<script>([\s\S]*)<\/script>/);
  expect(match, "embed has an inline script block").toBeTruthy();
  return match![1];
}

describe("consultaion-chamber embed", () => {
  it("defines every palette key it uses", () => {
    const src = script();
    const paletteBlock = src.match(/const C = isDark \? \{([\s\S]*?)\};/);
    expect(paletteBlock, "palette object is recognisable").toBeTruthy();

    const defined = new Set(
      [...paletteBlock![1].matchAll(/([a-zA-Z_]+)\s*:/g)].map((m) => m[1]),
    );
    const used = new Set(
      [...src.matchAll(/C\.([a-zA-Z_]+)/g)].map((m) => m[1]),
    );

    const missing = [...used].filter((key) => !defined.has(key));
    expect(
      missing,
      `palette keys used but never defined: ${missing.join(", ")}`,
    ).toEqual([]);
  });

  it("defines the same keys in light and dark", () => {
    // A key present in only one branch fails for half the users and looks like
    // a theme bug rather than a missing colour.
    const src = script();
    const both = src.match(
      /const C = isDark \? \{([\s\S]*?)\} : \{([\s\S]*?)\};/,
    );
    expect(both).toBeTruthy();

    const keys = (block: string) =>
      [...block.matchAll(/([a-zA-Z_]+)\s*:/g)].map((m) => m[1]).sort();

    expect(keys(both![1])).toEqual(keys(both![2]));
  });

  it("parses as valid JavaScript", () => {
    // The file was corrupted by a previous commit and shipped unparseable,
    // leaving the hero blank for every desktop visitor.
    expect(() => new Function(script())).not.toThrow();
  });

  it("keeps a noscript fallback so the hero is never empty", () => {
    expect(SOURCE).toMatch(/<noscript/i);
  });
});
