// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(fileURLToPath(new URL("../index.css", import.meta.url)), "utf8");

function themeColours(source) {
  const colours = {};
  for (const match of source.matchAll(/--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    colours[match[1]] = match[2];
  }
  return colours;
}

function channel(value) {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

const colours = themeColours(css);

const pairs = [
  ["text", "bg", 4.5],
  ["text-muted", "bg", 4.5],
  ["on-primary", "primary", 4.5],
  ["primary", "bg", 4.5],
  ["success", "success-soft", 4.5],
  ["warning", "warning-soft", 4.5],
  ["danger", "danger-soft", 4.5],
  ["border-strong", "surface", 3.0],
  ["border-strong", "bg", 3.0],
];

describe("design token contrast (WCAG 2.2)", () => {
  it("computes the reference ratio for black on white", () => {
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
  });

  it("keeps white on primary as pure white", () => {
    expect(colours["on-primary"]).toBe("#FFFFFF");
  });

  it.each(pairs)("%s on %s is at least %s:1", (foreground, background, minimum) => {
    expect(colours[foreground], `missing --color-${foreground}`).toBeDefined();
    expect(colours[background], `missing --color-${background}`).toBeDefined();
    const ratio = contrast(colours[foreground], colours[background]);
    expect(ratio).toBeGreaterThanOrEqual(minimum);
  });
});
