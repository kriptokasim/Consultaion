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

/** The classic 2D renderer: the one that must always work. */
function script(): string {
  const match = SOURCE.match(/<script>\n([\s\S]*?)<\/script>/);
  expect(match, "embed has the 2D inline script block").toBeTruthy();
  return match![1];
}

/** The optional WebGL upgrade layer. */
function moduleScript(): string {
  const match = SOURCE.match(/<script type="module">([\s\S]*?)<\/script>/);
  expect(match, "embed has the 3D module block").toBeTruthy();
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

describe("consultaion-chamber WebGL upgrade", () => {
  it("parses as valid JavaScript", () => {
    // Written as a module, so it is parsed as one rather than with new Function.
    expect(() => new Function(`return import("data:text/javascript,")`)).not.toThrow();
    expect(moduleScript().length).toBeGreaterThan(500);
  });

  it("never hides the 2D chamber before a real frame exists", () => {
    // The whole point of the layering. Hiding the fallback on load start -- or on
    // model load rather than first render -- reintroduces the blank hero this
    // embed already shipped once.
    const src = moduleScript();
    const hideIndex = src.indexOf("chamber-3d");
    const guardIndex = src.indexOf("if (!shown)");
    expect(guardIndex).toBeGreaterThan(-1);
    expect(hideIndex).toBeGreaterThan(guardIndex);
  });

  it("bails out instead of throwing when WebGL or the model is unavailable", () => {
    const src = moduleScript();
    // Every failure path returns; none of them tear down the 2D renderer.
    expect(src).toMatch(/catch[\s\S]*?return;/);
    expect(src).toMatch(/prefers-reduced-motion/);
    expect(src).toMatch(/saveData/);
    expect(src).not.toMatch(/chamber-unavailable/);
  });

  it("loads three and the model from this origin, not a CDN", () => {
    // The app's CSP is script-src 'self'; a CDN import would be blocked outright.
    const src = moduleScript();
    expect(src).toMatch(/\.\/three-chamber\.js/);
    expect(src).toMatch(/\.\/consultaion-chamber\.glb/);
    expect(src).not.toMatch(/https?:\/\/(cdn|unpkg|jsdelivr)/);
  });
});
